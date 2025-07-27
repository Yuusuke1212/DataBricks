import logging
import sys
import time
import traceback
import pythoncom
import win32com.client
import os
from enum import Enum
from typing import Optional, Dict, Any

from PyQt5.QtCore import QObject, pyqtSignal as Signal, QRunnable, pyqtSlot as Slot, QThreadPool

# JV-Link状態管理


class JVLinkState(Enum):
    """JV-Linkの接続状態を表す列挙型"""
    UNINITIALIZED = "UNINITIALIZED"     # 未初期化
    INITIALIZING = "INITIALIZING"       # 初期化中
    INITIALIZED = "INITIALIZED"         # 初期化完了
    OPEN_FOR_READ = "OPEN_FOR_READ"    # データ読み込み中
    WATCHING_EVENTS = "WATCHING_EVENTS"  # 速報監視中
    ERROR = "ERROR"                     # エラー状態
    CLOSED = "CLOSED"                   # 終了済み

# カスタム例外


class JVLinkStateError(Exception):
    """JV-Linkの状態が不正な場合の例外"""
    pass


class JVLinkNotInitializedError(Exception):
    """JV-Linkが初期化されていない場合の例外"""
    pass


class WorkerSignals(QObject):
    """
    ワーカースレッドからのシグナルを定義します。
    """
    finished = Signal()
    error = Signal(tuple)
    result = Signal(list)
    progress = Signal(int)


class JvDataWorker(QRunnable):
    """
    JV-Linkのデータ取得処理をバックグラウンドで実行するワーカー。
    """

    def __init__(self, jvlink, option: int, from_date: str, data_spec_list: list):
        super().__init__()
        self.jvlink = jvlink
        self.option = option
        self.from_date = from_date
        self.data_spec_list = data_spec_list
        self.signals = WorkerSignals()
        self.is_cancelled = False

    @Slot()
    def run(self):
        """ワーカーのメイン処理 - 複数のデータ種別を順番に処理"""
        try:
            pythoncom.CoInitialize()  # スレッドごとにCOMを初期化

            total_data_specs = len(self.data_spec_list)
            all_result_data = []

            for i, data_spec in enumerate(self.data_spec_list):
                if self.is_cancelled:
                    logging.info("データ取得処理がキャンセルされました。")
                    break

                logging.info(
                    f"データ種別 '{data_spec}' の処理を開始します ({i+1}/{total_data_specs})")

                # データ取得処理
                read_count_str = self.jvlink.JVOpen(
                    data_spec, self.from_date, self.option)
                read_count = int(
                    read_count_str) if read_count_str.isdigit() else 0

                if read_count < 0:
                    # エラーコードを処理
                    error_msg = f"JVOpenエラー: data_spec={data_spec}, code={read_count}"
                    logging.error(error_msg)
                    self.signals.error.emit((RuntimeError, error_msg, ""))
                    continue

                if read_count == 0:
                    logging.info(f"データ種別 '{data_spec}' には新しいデータがありません。")
                    continue

                result_data, is_error = self._read_loop(
                    read_count, data_spec, i, total_data_specs)
                if is_error:
                    error_msg = f"JVReadでエラーが発生しました: data_spec={data_spec}"
                    logging.error(error_msg)
                    self.signals.error.emit((RuntimeError, error_msg, ""))
                    continue

                # 各データ種別のデータをタプルで追加（データ種別も含める）
                for data in result_data:
                    all_result_data.append((data_spec, data))

                logging.info(
                    f"データ種別 '{data_spec}' の処理が完了しました。取得件数: {len(result_data)}")

            # 全てのデータを一度に送信
            if all_result_data:
                self.signals.result.emit(all_result_data)

        except Exception as e:
            logging.error(f"JvDataWorkerでエラーが発生: {e}")
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            try:
                self.jvlink.JVClose()
            except:
                pass
            pythoncom.CoUninitialize()  # COMを解放
            self.signals.finished.emit()

    def _read_loop(self, read_count: int, data_spec: str, current_spec_index: int, total_specs: int) -> tuple[list, bool]:
        """JVReadをループして全データを読み込む"""
        raw_data = []
        if read_count == 0:
            logging.info(f"データ種別 '{data_spec}': 読み込み対象データが0件です。")
            return raw_data, False

        read_counter = 0
        current_file_name = ""
        file_read_count = 0
        total_bytes_read = 0

        logging.info(f"データ種別 '{data_spec}': データ読み込み開始 (予想件数: {read_count})")

        while True:
            if self.is_cancelled:
                logging.info(f"データ種別 '{data_spec}': 読み込み処理がキャンセルされました。")
                break

            # 256KBのバッファとファイル名バッファ
            buff = " " * 256 * 1024
            filename = " " * 256

            rtn_code = self.jvlink.JVRead(buff, 256 * 1024, filename)

            # 全体の進捗を計算（データ種別間 + 種別内の進捗）
            spec_progress = (read_counter * 100 //
                             read_count) if read_count > 0 else 0
            overall_progress = ((current_spec_index * 100) +
                                spec_progress) // total_specs
            self.signals.progress.emit(overall_progress)

            if rtn_code > 0:
                # 正常に読み込めたデータを追加
                raw_data.append(buff[:rtn_code])
                read_counter += 1
                total_bytes_read += rtn_code

                # ファイル名が変わった場合はログ出力
                file_name = filename.strip()
                if file_name and file_name != current_file_name:
                    if current_file_name:
                        logging.info(f"データ種別 '{data_spec}': ファイル '{current_file_name}' 完了 "
                                     f"({file_read_count} レコード)")
                    current_file_name = file_name
                    file_read_count = 0
                    logging.info(
                        f"データ種別 '{data_spec}': ファイル '{current_file_name}' 処理開始")

                file_read_count += 1

                # 100レコードごとに進捗ログを出力
                if read_counter % 100 == 0:
                    logging.debug(f"データ種別 '{data_spec}': {read_counter}/{read_count} レコード読み込み済み "
                                  f"({total_bytes_read:,} bytes)")

            elif rtn_code == 0:
                # 全て読み込み完了
                if current_file_name:
                    logging.info(f"データ種別 '{data_spec}': ファイル '{current_file_name}' 完了 "
                                 f"({file_read_count} レコード)")
                logging.info(f"データ種別 '{data_spec}': 読み込み完了 - 総レコード数: {read_counter}, "
                             f"総データサイズ: {total_bytes_read:,} bytes")
                break
            elif rtn_code == -1:
                # ファイル切り替わり。次のJVReadを呼ぶ
                logging.debug(f"データ種別 '{data_spec}': ファイル切り替わり")
                continue
            else:
                # エラー発生
                logging.error(f"データ種別 '{data_spec}': JVReadエラー - code={rtn_code}, "
                              f"読み込み済みレコード数: {read_counter}")
                return raw_data, True

        return raw_data, False

    def cancel(self):
        """処理のキャンセルを要求する"""
        self.is_cancelled = True


class JvRealtimeWorker(QRunnable):
    """
    JVWatchEventを呼び出し、リアルタイムイベントを監視するワーカー。
    """

    def __init__(self, jvlink):
        super().__init__()
        self.jvlink = jvlink
        self.signals = WorkerSignals()  # 既存のシグナルを流用
        self.is_running = True

    @Slot()
    def run(self):
        """ワーカーのメイン処理"""
        try:
            pythoncom.CoInitialize()
            logging.info("リアルタイムイベントの監視を開始します...")

            while self.is_running:
                # JVWatchEventはイベントが発生するか、JVWatchEventCloseが呼ばれるまでブロックする
                rtn_code = self.jvlink.JVWatchEvent()

                if not self.is_running:
                    break

                if rtn_code < 0:
                    logging.error(f"JVWatchEventエラー: code={rtn_code}")
                    self.signals.error.emit(
                        (RuntimeError, f"JVWatchEventエラー: code={rtn_code}", traceback.format_exc()))
                    break

                # イベントデータがあればJVReadで読み込む
                buff = " " * 256 * 1024
                filename = " " * 256
                read_size = self.jvlink.JVRead(buff, 256 * 1024, filename)

                if read_size > 0:
                    # 最初の4バイトがイベント種別
                    event_id = buff[:4]
                    logging.info(f"速報イベント受信: ID={event_id}, Size={read_size}")
                    self.signals.result.emit([buff[:read_size]])  # データはリストで渡す
                elif read_size < 0 and read_size != -1:  # -1はファイル切り替わりなので正常
                    logging.error(f"速報データ読み込みエラー: JVRead code={read_size}")

        except Exception as e:
            logging.error(f"JvRealtimeWorkerでエラーが発生: {e}")
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            logging.info("リアルタイムイベントの監視ループを終了します。")
            pythoncom.CoUninitialize()
            self.signals.finished.emit()

    def stop(self):
        """監視を停止する"""
        logging.info("JvRealtimeWorkerの停止を要求します。")
        self.is_running = False
        # JVWatchEventのブロックを解除するためにJVWatchEventCloseを呼ぶ
        if self.jvlink:
            self.jvlink.JVWatchEventClose()


class JvLinkManager(QObject):
    """
    JRA-VANサーバーとの通信に関わる全ての処理をカプセル化する。
    JV-Link COMコンポーネントのラッパーとして機能する。
    非同期処理の結果はシグナルを通じて通知される。

    シングルトンパターンにより、アプリケーション全体で単一のインスタンスを保証。
    状態管理により、不正な順序での操作を防止。
    """

    # シングルトンインスタンス
    _instance = None
    _initialized = False

    # シグナル定義
    initialization_finished = Signal(bool, str)  # success, message
    data_received = Signal(list)
    progress_updated = Signal(int)
    error_occurred = Signal(str)
    operation_finished = Signal(str)  # 最終タイムスタンプを返す

    realtime_event_received = Signal(list)
    realtime_watch_started = Signal()
    realtime_watch_stopped = Signal()
    state_changed = Signal(str)  # 状態変更通知

    def __new__(cls, *args, **kwargs):
        """シングルトンパターンの実装"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, parent=None):
        """コンストラクタ - シングルトンのため初期化は一度だけ"""
        if JvLinkManager._initialized:
            return

        super().__init__(parent)

        # JV-Link状態管理
        self._current_state = JVLinkState.UNINITIALIZED
        self.jvlink = None
        self.last_timestamp = ""

        # スレッド管理
        self.threadpool = QThreadPool()
        self.realtime_worker = None
        self.current_data_worker = None
        self.is_operation_active = False

        # ロギング設定
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')
        logging.info(
            f"JvLinkManager初期化 - 最大スレッド数: {self.threadpool.maxThreadCount()}")

        JvLinkManager._initialized = True

    @classmethod
    def get_instance(cls):
        """シングルトンインスタンスを取得"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def current_state(self) -> JVLinkState:
        """現在の状態を取得"""
        return self._current_state

    def _change_state(self, new_state: JVLinkState):
        """状態を変更し、シグナルで通知"""
        if self._current_state != new_state:
            old_state = self._current_state
            self._current_state = new_state
            logging.info(
                f"JV-Link状態変更: {old_state.value} -> {new_state.value}")
            self.state_changed.emit(new_state.value)

    def _validate_state(self, required_states: list, operation_name: str):
        """指定された操作に必要な状態かチェック"""
        if self._current_state not in required_states:
            error_msg = f"{operation_name}を実行するには、状態が{[s.value for s in required_states]}である必要があります。現在の状態: {self._current_state.value}"
            logging.error(error_msg)
            raise JVLinkStateError(error_msg)

    def is_initialized(self) -> bool:
        """JV-Linkが初期化されているかチェック"""
        return self._current_state in [JVLinkState.INITIALIZED, JVLinkState.OPEN_FOR_READ, JVLinkState.WATCHING_EVENTS]

    def can_start_data_operation(self) -> bool:
        """データ操作を開始できる状態かチェック"""
        return self._current_state == JVLinkState.INITIALIZED

    def can_start_realtime_watch(self) -> bool:
        """速報監視を開始できる状態かチェック"""
        return self._current_state == JVLinkState.INITIALIZED

    def initialize(self):
        """
        JV-Linkを初期化し、認証を行う。
        処理結果は initialization_finished シグナルで通知される。

        設定（サービスキー等）はJVSetUIProperties()で事前に設定され、
        Windowsレジストリに保存された値が自動的に使用されます。
        """
        self._validate_state([JVLinkState.UNINITIALIZED], "initialize")
        self._change_state(JVLinkState.INITIALIZING)

        logging.info("JV-Linkの初期化を開始します...")

        # JV-Linkファイルの存在確認
        jvlink_path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.dirname(__file__))), "JV-Link", "JV-Link.exe")
        if os.path.exists(jvlink_path):
            logging.info(f"JV-Linkファイルが見つかりました: {jvlink_path}")
        else:
            logging.warning(f"JV-Linkファイルが見つかりません: {jvlink_path}")

        # 複数のCOMオブジェクト名を試行（JRA-VAN公式仕様）
        com_names = [
            "JVDTLab.JVLink",       # 最も一般的
            "JVDTLAB.JVLink.1",     # バージョン指定
            "JVDTLAB.JVLink",       # バージョン無し
            "JVLink.Application",   # 代替名
            "JVLink.JVLink.1",      # 旧形式
            "JVLink.JVLink"         # 旧形式バージョン無し
        ]

        try:
            pythoncom.CoInitialize()

            for com_name in com_names:
                try:
                    logging.info(f"COMオブジェクト '{com_name}' を試行中...")
                    self.jvlink = win32com.client.Dispatch(com_name)
                    logging.info(f"COMオブジェクト '{com_name}' の作成に成功")
                    break
                except Exception as com_ex:
                    logging.warning(f"COMオブジェクト '{com_name}' の作成に失敗: {com_ex}")
                    continue
            else:
                # すべてのCOMオブジェクト名で失敗
                raise Exception(
                    "有効なJV-Link COMオブジェクトが見つかりません。JV-Linkが正しくインストール・登録されているか確認してください。")

            # JV-Linkの初期化（レジストリから設定を自動読み込み）
            ret = self.jvlink.JVInit("")  # 空文字列でレジストリから設定読み込み
            if ret != 0:
                error_msg = self._get_jvlink_error_message(ret)
                logging.error(f"JV-Linkの認証に失敗しました。エラーコード: {ret} - {error_msg}")
                if ret == -301:
                    detailed_msg = f"認証エラー ({ret}): {error_msg}\n\nJVSetUIProperties()で正しいサービスキーを設定してください。"
                else:
                    detailed_msg = f"認証エラー ({ret}): {error_msg}"
                self.initialization_finished.emit(False, detailed_msg)
            else:
                logging.info("JV-Linkの認証に成功しました。")
                self.initialization_finished.emit(True, "認証に成功しました。")

        except Exception as e:
            logging.error(f"JV-Linkの初期化中に例外が発生しました: {e}")
            self.initialization_finished.emit(False, f"初期化例外: {e}")
        finally:
            pythoncom.CoUninitialize()
            if self._current_state == JVLinkState.INITIALIZING:
                if self.jvlink is not None:
                    self._change_state(JVLinkState.INITIALIZED)
                else:
                    self._change_state(JVLinkState.ERROR)

    def _get_jvlink_error_message(self, error_code: int) -> str:
        """JV-Linkエラーコードを解釈してユーザーフレンドリーなメッセージを返す"""
        error_messages = {
            -1: "JV-Linkサービスが開始されていません。JV-Linkアプリケーションを起動してください。",
            -2: "サービスIDが未登録または無効です。JV-LinkアプリケーションでサービスIDを登録してください。",
            -3: "サービスIDの認証に失敗しました。正しいサービスIDを確認してください。",
            -4: "JRA-VANサーバーとの通信エラーです。ネットワーク接続を確認してください。",
            -5: "JV-Linkの内部エラーです。JV-Linkアプリケーションを再起動してください。",
            -101: "ファイルが見つかりません。",
            -102: "ファイルの読み込みエラーです。",
            -103: "ファイルの書き込みエラーです。",
            -201: "メモリ不足エラーです。",
            -202: "JV-Linkが使用中です。しばらく待ってから再試行してください。"
        }

        if error_code in error_messages:
            return error_messages[error_code]
        elif error_code < 0:
            return f"JV-Linkエラー（未定義エラーコード: {error_code}）"
        else:
            return f"不明なエラー（コード: {error_code}）"

    def get_data_async(self, option: int, from_date: str, data_spec_list: list):
        """
        データ取得処理を非同期で開始する。
        """
        self._validate_state([JVLinkState.INITIALIZED], "get_data_async")

        logging.info(
            f"データ取得を開始します: option={option}, from_date={from_date}, data_spec_list={data_spec_list}")

        # 操作開始フラグを設定
        self.is_operation_active = True

        worker = JvDataWorker(
            jvlink=self.jvlink,
            option=option,
            from_date=from_date,
            data_spec_list=data_spec_list
        )

        # 現在のワーカーを保持（キャンセル用）
        self.current_data_worker = worker

        # ワーカーからのシグナルをマネージャーのシグナルに中継
        worker.signals.result.connect(self.data_received)
        worker.signals.progress.connect(self.progress_updated)
        worker.signals.error.connect(
            lambda e: self.error_occurred.emit(str(e)))
        worker.signals.finished.connect(self._on_worker_finished)

        self.threadpool.start(worker)

    def cancel_current_operation(self):
        """
        現在実行中のデータ取得処理をキャンセルする
        """
        if not self.is_operation_active:
            logging.info("キャンセル要求がありましたが、実行中の処理がありません。")
            return

        logging.info("データ取得処理のキャンセルを要求します。")

        try:
            # JV-Linkの処理をキャンセル
            if self.jvlink:
                cancel_result = self.jvlink.JVCancel()
                logging.info(f"JVCancel実行結果: {cancel_result}")

            # ワーカーにキャンセル要求を送信
            if self.current_data_worker:
                self.current_data_worker.cancel()

        except Exception as e:
            logging.error(f"キャンセル処理中にエラーが発生: {e}")

        # 操作状態をリセット
        self._reset_operation_state()

    def _reset_operation_state(self):
        """操作状態をリセットする"""
        self.is_operation_active = False
        self.current_data_worker = None
        logging.info("操作状態をリセットしました。")

    def watch_realtime_events_async(self):
        """速報イベントの監視を非同期で開始する"""
        self._validate_state([JVLinkState.INITIALIZED],
                             "watch_realtime_events_async")

        if self.realtime_worker and self.realtime_worker.is_running:
            logging.warning("既に速報イベントを監視中です。")
            return

        try:
            logging.info("速報イベント監視ワーカーを起動します。")
            self.realtime_worker = JvRealtimeWorker(self.jvlink)
            self.realtime_worker.signals.result.connect(
                self.realtime_event_received)
            self.realtime_worker.signals.error.connect(
                lambda e: self.error_occurred.emit(f"リアルタイム監視エラー: {e}"))
            self.realtime_worker.signals.finished.connect(
                self._on_realtime_worker_finished)

            self._change_state(JVLinkState.WATCHING_EVENTS)
            self.threadpool.start(self.realtime_worker)
            self.realtime_watch_started.emit()

        except Exception as e:
            logging.error(f"リアルタイム監視開始エラー: {e}")
            self._change_state(JVLinkState.ERROR)
            self.error_occurred.emit(f"リアルタイム監視開始エラー: {e}")

    def stop_watching_events(self):
        """速報イベントの監視を停止する"""
        if self.realtime_worker and self.realtime_worker.is_running:
            logging.info("速報イベントの監視停止を開始します。")
            self.realtime_worker.stop()

            # 状態をINITIALIZEDに戻す
            if self._current_state == JVLinkState.WATCHING_EVENTS:
                self._change_state(JVLinkState.INITIALIZED)
        else:
            logging.warning("速報イベントは監視されていません。")

    def _on_realtime_worker_finished(self):
        """リアルタイムワーカー終了時の処理"""
        logging.info("リアルタイムワーカーが終了しました。")
        self.realtime_worker = None

        # 状態をINITIALIZEDに戻す（エラー状態でない場合）
        if self._current_state == JVLinkState.WATCHING_EVENTS:
            self._change_state(JVLinkState.INITIALIZED)

        self.realtime_watch_stopped.emit()

    def _on_worker_finished(self):
        """ワーカー処理完了後、最終タイムスタンプを添えて通知"""
        try:
            if self.jvlink and not self.current_data_worker.is_cancelled:
                self.last_timestamp = self.jvlink.JVGetLastTimestamp()
                self.operation_finished.emit(self.last_timestamp)
                logging.info(
                    f"データ取得処理が完了しました。最終タイムスタンプ: {self.last_timestamp}")
            else:
                logging.info("データ取得処理がキャンセルされました。")
                self.operation_finished.emit("キャンセル")
        except Exception as e:
            logging.error(f"ワーカー終了処理中にエラーが発生: {e}")
        finally:
            # 操作状態をリセット
            self._reset_operation_state()

    def close(self):
        """JV-Linkを解放する"""
        # 実行中の処理をキャンセル
        if self.is_operation_active:
            self.cancel_current_operation()

        # リアルタイム監視を停止
        if self.realtime_worker and self.realtime_worker.is_running:
            self.stop_watching_events()

        if self.jvlink:
            try:
                self.jvlink.JVClose()
                logging.info("JV-Linkを解放しました。")
            except Exception as e:
                logging.error(f"JV-Link解放中にエラーが発生: {e}")
        self.jvlink = None
        self._change_state(JVLinkState.CLOSED)

# ファクトリー関数


def create_jvlink_manager() -> JvLinkManager:
    """
    JvLinkManagerのシングルトンインスタンスを取得するファクトリー関数

    Returns:
        JvLinkManager: シングルトンインスタンス
    """
    return JvLinkManager.get_instance()


def get_jvlink_manager() -> JvLinkManager:
    """
    既存のJvLinkManagerインスタンスを取得（存在しない場合は作成）

    Returns:
        JvLinkManager: シングルトンインスタンス
    """
    return JvLinkManager.get_instance()
