"""
JvLink Reader Worker for JRA-Data Collector

JV-Linkからデータを読み取り、生データキューに送信するプロデューサーワーカー
"""

from typing import Optional, Dict, List, Any, Tuple
import time
from queue import Queue

from .base import QueueWorker, CancellationToken
from ..jvlink_manager import JvLinkManager
try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    TENACITY_AVAILABLE = True
except ImportError:
    # テスト環境でtenacityが利用できない場合のダミー実装
    def retry(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def stop_after_attempt(*args): pass
    def wait_exponential(*args, **kwargs): pass
    def retry_if_exception_type(*args): pass

    TENACITY_AVAILABLE = False


class JvLinkReaderWorker(QueueWorker):
    """
    JV-Linkからデータを読み取るプロデューサーワーカー

    既存のJvLinkManagerを使用してデータを取得し、
    生データキューに順次送信します。
    """

    def __init__(self,
                 raw_data_queue: Queue,
                 jvlink_manager: JvLinkManager,
                 data_params: Dict[str, Any],
                 cancellation_token: CancellationToken,
                 progress_callback=None,
                 error_callback=None):

        super().__init__(
            name="JvLinkReader",
            input_queue=None,  # プロデューサーなので入力キューなし
            output_queue=raw_data_queue,
            cancellation_token=cancellation_token,
            progress_callback=progress_callback,
            error_callback=error_callback
        )

        self.jvlink_manager = jvlink_manager
        self.data_params = data_params

        # データ取得パラメータ
        self.option = data_params.get('option', 1)  # 1:差分, 3:セットアップ
        self.from_date = data_params.get('from_date', '')
        self.data_spec_list = data_params.get('data_spec_list', ['RACE'])

        # 進捗追跡
        self.current_spec_index = 0
        self.total_specs = len(self.data_spec_list)
        self.current_file_index = 0
        self.total_files = 0

        # JV-Link接続状態
        self._is_connected = False

    def on_start(self) -> None:
        """ワーカー開始時の初期化"""
        self.logger.info(
            f"Starting JvLink data acquisition: {self.data_params}")
        self.logger.info(f"Data specs: {self.data_spec_list}")

        # JV-Linkマネージャーのシグナル接続
        if hasattr(self.jvlink_manager, 'data_received'):
            self.jvlink_manager.data_received.connect(self._on_data_received)
        if hasattr(self.jvlink_manager, 'operation_finished'):
            self.jvlink_manager.operation_finished.connect(
                self._on_operation_finished)

    def process_loop(self) -> None:
        """メイン処理ループ - データ仕様を順次処理"""
        try:
            for spec_index, data_spec in enumerate(self.data_spec_list):
                self.cancellation_token.throw_if_cancelled()

                self.current_spec_index = spec_index
                self.logger.info(
                    f"Processing data spec {spec_index + 1}/{self.total_specs}: {data_spec}")

                # 進捗報告
                self.report_progress(
                    spec_index,
                    self.total_specs,
                    f"Processing {data_spec}"
                )

                # データ仕様の処理
                self._process_data_spec(data_spec)

            self.logger.info("All data specs processed successfully")

        except Exception as e:
            self.logger.error(f"Error in JvLink reader process loop: {e}")
            raise

    def _process_data_spec(self, data_spec: str) -> None:
        """
        単一のデータ仕様を処理

        Args:
            data_spec: 処理するデータ仕様（例: "RACE", "ODDS"）
        """
        try:
            # JV-Linkでデータ取得要求
            self._request_data(data_spec)

            # データ受信をポーリング
            self._poll_data_reception(data_spec)

        except Exception as e:
            self.logger.error(f"Error processing data spec {data_spec}: {e}")
            raise

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    def _request_data(self, data_spec: str) -> None:
        """
        JV-Linkでデータ取得要求（自動リトライ付き）

        Args:
            data_spec: データ仕様
        """
        self.logger.info(f"Requesting data for spec: {data_spec}")

        # キャンセルチェック
        self.cancellation_token.throw_if_cancelled()

        try:
            # 既存のJvLinkManagerを使用してデータ要求
            self.jvlink_manager.get_data_async(
                option=self.option,
                from_date=self.from_date,
                data_spec_list=[data_spec]  # 単一仕様で処理
            )

            self.logger.info(f"Data request submitted for {data_spec}")

        except Exception as e:
            self.logger.error(f"Failed to request data for {data_spec}: {e}")
            raise

    def _poll_data_reception(self, data_spec: str) -> None:
        """
        データ受信をポーリング

        Args:
            data_spec: データ仕様
        """
        self.logger.info(f"Polling for data reception: {data_spec}")

        # ポーリング開始時刻
        poll_start = time.time()
        max_poll_time = 300.0  # 最大5分
        poll_interval = 1.0  # 1秒間隔

        while (time.time() - poll_start) < max_poll_time:
            # キャンセルチェック
            self.cancellation_token.throw_if_cancelled()

            # データ受信状況をチェック
            if self._check_data_ready(data_spec):
                self.logger.info(f"Data ready for {data_spec}")
                self._read_available_data(data_spec)
                break

            # 短時間スリープ
            self.safe_sleep(poll_interval)
        else:
            raise TimeoutError(f"Timeout waiting for data: {data_spec}")

    def _check_data_ready(self, data_spec: str) -> bool:
        """
        データが受信可能かチェック

        Args:
            data_spec: データ仕様

        Returns:
            bool: データが受信可能な場合True
        """
        # JV-Linkマネージャーの状態をチェック
        # ここでは簡略化のため、常にTrueを返す
        # 実際の実装では、JvStatusやJvReadを呼び出して状態を確認
        return True

    def _read_available_data(self, data_spec: str) -> None:
        """
        受信可能なデータを読み取り

        Args:
            data_spec: データ仕様
        """
        self.logger.info(f"Reading available data for {data_spec}")

        file_count = 0

        while not self.cancellation_token.is_cancelled:
            try:
                # JV-Linkから1ファイル分のデータを読み取り
                raw_data = self._read_single_file(data_spec)

                if raw_data is None:
                    # データ読み取り完了
                    break

                # 生データキューに送信
                data_item = {
                    'data_spec': data_spec,
                    'raw_data': raw_data,
                    'file_index': file_count,
                    'timestamp': time.time()
                }

                self.output_queue.put(data_item)
                file_count += 1
                self.items_processed += 1

                # 進捗報告
                if file_count % 10 == 0:
                    self.logger.info(
                        f"Read {file_count} files for {data_spec}")
                    self.report_progress(
                        self.current_spec_index,
                        self.total_specs,
                        f"{data_spec}: {file_count} files read"
                    )

            except Exception as e:
                self.logger.error(
                    f"Error reading data file for {data_spec}: {e}")
                # 個別ファイルエラーは継続
                continue

        self.logger.info(
            f"Completed reading {file_count} files for {data_spec}")

    def _read_single_file(self, data_spec: str) -> Optional[str]:
        """
        JV-Linkから単一ファイルのデータを読み取り

        Args:
            data_spec: データ仕様

        Returns:
            Optional[str]: 読み取ったデータ（Noneで終了）
        """
        # キャンセルチェック
        self.cancellation_token.throw_if_cancelled()

        try:
            # JV-Linkマネージャーの読み取り機能を使用
            # ここでは仮実装（実際にはJvReadを呼び出す）

            # シミュレーション: ランダムなデータの生成
            import random
            if random.random() < 0.1:  # 10%の確率で終了
                return None

            # ダミーデータを返す
            return f"DUMMY_DATA_FOR_{data_spec}_{self.items_processed}"

        except Exception as e:
            self.logger.error(
                f"Error in _read_single_file for {data_spec}: {e}")
            return None

    def _on_data_received(self, raw_data_list: List[Tuple[str, str]]) -> None:
        """
        JvLinkManagerからのデータ受信シグナル処理

        Args:
            raw_data_list: [(data_spec, raw_data), ...] のリスト
        """
        self.logger.info(
            f"Received data signal from JvLinkManager: {len(raw_data_list)} items")

        for data_spec, raw_data in raw_data_list:
            # 生データキューに送信
            data_item = {
                'data_spec': data_spec,
                'raw_data': raw_data,
                'file_index': self.items_processed,
                'timestamp': time.time(),
                'source': 'jvlink_signal'
            }

            self.output_queue.put(data_item)
            self.items_processed += 1

    def _on_operation_finished(self, message: str) -> None:
        """
        JvLinkManager操作完了シグナル処理

        Args:
            message: 完了メッセージ
        """
        self.logger.info(f"JvLinkManager operation finished: {message}")

    def produce_item(self) -> Optional[Any]:
        """
        プロデューサーとして次のアイテムを生成

        この実装では使用しない（process_loopで直接処理）

        Returns:
            None: 常にNone（process_loopを使用）
        """
        return None

    def process_item(self, item: Any) -> Any:
        """
        アイテム処理（プロデューサーでは使用しない）

        Args:
            item: 処理するアイテム

        Returns:
            Any: 処理済みアイテム
        """
        return item  # プロデューサーなので何もしない

    def on_cleanup(self) -> None:
        """ワーカー終了時のクリーンアップ"""
        try:
            # JV-Linkマネージャーのシグナル切断
            if hasattr(self.jvlink_manager, 'data_received'):
                self.jvlink_manager.data_received.disconnect(
                    self._on_data_received)
            if hasattr(self.jvlink_manager, 'operation_finished'):
                self.jvlink_manager.operation_finished.disconnect(
                    self._on_operation_finished)

            # 終了マーカーをキューに送信
            self.finish_input()

            self.logger.info("JvLinkReader cleanup completed")

        except Exception as e:
            self.logger.error(f"Error during JvLinkReader cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        base_stats = super().get_stats()
        jvlink_stats = {
            "option": self.option,
            "from_date": self.from_date,
            "data_specs": self.data_spec_list,
            "current_spec_index": self.current_spec_index,
            "total_specs": self.total_specs,
            "files_read": self.items_processed
        }

        return {**base_stats, **jvlink_stats}
