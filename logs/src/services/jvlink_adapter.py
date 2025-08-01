#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JV-Link 堅牢性アダプター
静的ディスパッチとカスタム例外階層による堅牢なJV-Link連携

Clean Architecture原則に従ったモダンな実装
"""

import logging
import subprocess
import time
import os
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

# カスタム定数のインポート
from ..constants import ApplicationConstants

# psutilによるプロセス管理
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    logging.warning(
        "psutil not available. Process management will be limited.")

# 静的ディスパッチでCOMオブジェクト操作
try:
    import win32com.client
    import win32com.client.gencache
    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False
    logging.warning(
        "win32com not available. JV-Link functionality will be limited.")

# カスタム例外階層
from ..exceptions import (
    JVLinkError, JVLinkAuthError, JVLinkNetworkError,
    JVLinkParameterError, JVLinkStateError, JVLinkDataError,
    JVLinkResourceError, JVLinkTimeoutError,
    create_jvlink_error, is_retryable_error, get_retry_delay
)

# 設定管理
from .settings_manager import get_config_manager


logger = logging.getLogger(__name__)


def check_jvlink_result(result: int, operation: str = "JV-Link操作",
                        context: Optional[Dict[str, Any]] = None) -> None:
    """
    JV-Linkメソッドの戻り値をチェックし、エラーの場合は適切な例外を送出

    Args:
        result: JV-Linkメソッドの戻り値
        operation: 実行していた操作名
        context: エラーのコンテキスト情報

    Raises:
        JVLinkError: エラーコードに応じた適切な例外
    """
    if result < 0:
        error_message = f"{operation}でエラーが発生しました"
        exception = create_jvlink_error(result, error_message, context)
        logger.error(f"JV-Linkエラー: {exception}")
        raise exception
    elif result > 0:
        # 正の値は警告やステータス情報の場合がある
        logger.info(f"{operation}が成功しました (戻り値: {result})")


class JVLinkAdapter:
    """
    JV-Linkとの通信を管理するアダプタークラス

    静的ディスパッチとカスタム例外階層による堅牢な実装
    Clean Architecture原則に従った設計
    """

    def __init__(self, jvlink_path: Optional[str] = None):
        """
        JVLinkAdapterを初期化

        Args:
            jvlink_path: JV-Link実行ファイルのパス（省略時は設定から取得）
        """
        self.logger = logging.getLogger(__name__)

        # 設定管理
        self.config_manager = get_config_manager()
        self.jvlink_path = jvlink_path or self.config_manager.get_jvlink_exe_path()

        # COMオブジェクト
        self.jvlink_com_obj = None
        self.is_initialized = False

        # 接続設定（レジストリベース）
        # JV-Link設定はJVSetUIProperties()でレジストリに保存され、
        # JVInit()時に自動的に読み込まれるため、プログラムでの管理は不要
        self.connection_timeout = 30  # デフォルト値
        self.read_timeout = 60        # デフォルト値

        self.logger.info(f"JVLinkAdapter初期化完了: {self.jvlink_path}")

    def _is_jvlink_running(self) -> bool:
        """
        JV-Link (JVDTLab.exe) が実行中か確認する
        """
        if not PSUTIL_AVAILABLE:
            self.logger.warning("psutilが利用できません。プロセス確認をスキップします。")
            return False

        try:
            for proc in psutil.process_iter(['name', 'pid']):
                if proc.info['name'].lower() in ['jvdtlab.exe', 'jv-link.exe']:
                    self.logger.info(
                        f"JV-Link (PID: {proc.info['pid']}) が既に実行中です。")
                    return True

            self.logger.info("JV-Linkプロセスは実行されていません。")
            return False

        except Exception as e:
            self.logger.error(f"プロセス確認エラー: {e}")
            return False

    def _start_jvlink_process(self) -> None:
        """
        JV-Linkプロセスを起動

        Raises:
            JVLinkResourceError: プロセス起動に失敗した場合
        """
        try:
            if not Path(self.jvlink_path).exists():
                raise JVLinkResourceError(
                    f"JV-Link実行ファイルが見つかりません: {self.jvlink_path}",
                    error_code=-16,
                    context={'file_path': self.jvlink_path}
                )

            self.logger.info(f"JV-Linkを起動します: {self.jvlink_path}")
            subprocess.Popen([self.jvlink_path])

            # ★重要★: 効率的なポーリング処理に変更（固定的な待機を廃止）
            max_wait_time = ApplicationConstants.JVLINK_MAX_WAIT_TIME  # 最大5秒待機
            poll_interval = ApplicationConstants.JVLINK_PROCESS_CHECK_INTERVAL  # 0.2秒ごとに確認
            start_time = time.time()
            
            self.logger.info(f"COMオブジェクトの準備完了をポーリング中（最大{max_wait_time}秒）...")
            
            while time.time() - start_time < max_wait_time:
                try:
                    # COMオブジェクトのディスパッチを試行してプロセス準備完了を確認
                    test_com = win32com.client.Dispatch("JVDTLab.JVLink")
                    self.logger.info(f"COMオブジェクトの準備完了を確認しました（{time.time() - start_time:.2f}秒後）")
                    return True
                except Exception:
                    # まだ準備ができていない場合は短時間待機して再試行
                    time.sleep(poll_interval)
            
            # タイムアウトした場合
            self.logger.warning(f"JV-LinkのCOMサーバー準備完了の確認がタイムアウトしました（{max_wait_time}秒）")
            return False

        except FileNotFoundError:
            raise JVLinkResourceError(
                f"JV-Link実行ファイルが見つかりません: {self.jvlink_path}",
                error_code=-16,
                context={'file_path': self.jvlink_path}
            )
        except Exception as e:
            raise JVLinkResourceError(
                f"JV-Linkの起動に失敗しました: {e}",
                error_code=-15,
                context={'error': str(e), 'file_path': self.jvlink_path}
            )

    def _create_com_object(self) -> None:
        """
        静的ディスパッチでCOMオブジェクトを作成

        Raises:
            JVLinkStateError: COM初期化に失敗した場合
        """
        if not WIN32COM_AVAILABLE:
            raise JVLinkStateError(
                "win32comが利用できません。JV-Link機能は制限されます。",
                error_code=-10
            )

        try:
            self.logger.info("JV-Link COMオブジェクトを静的ディスパッチで初期化します...")

            # 静的ディスパッチを使用（パフォーマンスと型安全性の向上）
            self.jvlink_com_obj = win32com.client.gencache.EnsureDispatch(
                "JVDTLab.JVLink")

            if self.jvlink_com_obj is None:
                raise JVLinkStateError(
                    "JV-Link COMオブジェクトの作成に失敗しました",
                    error_code=-10
                )

            self.logger.info("JV-Link COMオブジェクト作成成功")

        except Exception as e:
            self.logger.error(f"COMオブジェクト作成エラー: {e}")
            raise JVLinkStateError(
                f"JV-Link COMオブジェクトの初期化に失敗しました: {e}",
                error_code=-10,
                context={'error': str(e)}
            )

    def _initialize_jvlink(self) -> None:
        """
        JV-Linkの初期化処理

        Raises:
            JVLinkAuthError: 認証に失敗した場合
            JVLinkError: その他の初期化エラー
        """
        try:
            # サービスキーはJVSetUIProperties()で設定されるため、JVInit()時には不要

            self.logger.info("JV-Linkの初期化を開始します...")

            # ワーキングディレクトリの一時変更（重要なバグ修正）
            original_cwd = Path.cwd()
            jvlink_dir = Path(self.jvlink_path).parent.resolve()
            
            try:
                # JV-Link.exeがあるディレクトリに一時的に移動
                if jvlink_dir.exists():
                    os.chdir(jvlink_dir)
                    self.logger.info(f"ワーキングディレクトリを一時的に変更: {jvlink_dir}")
                else:
                    self.logger.warning(f"JV-Linkディレクトリが存在しません: {jvlink_dir}")
                
                # JVInit実行（仕様準拠：ソフトウェアIDを明示的に設定）
                software_id = "DataBricks/1.0.0"  # アプリケーションを識別するユニークなID
                self.logger.info(f"JV-Linkを初期化します。ソフトウェアID: {software_id}")
                
                init_result = self.jvlink_com_obj.JVInit(software_id)

                # 結果チェック
                check_jvlink_result(
                    init_result,
                    "JVInit",
                    {'software_id': software_id}
                )

                self.logger.info("JV-Linkの初期化に成功しました")

            finally:
                # 必ずワーキングディレクトリを元に戻す
                os.chdir(original_cwd)
                self.logger.info(f"ワーキングディレクトリを元に戻しました: {original_cwd}")

        except JVLinkError:
            # 既知のJV-Linkエラーはそのまま再送出
            raise
        except Exception as e:
            # 予期しないエラーはJVLinkErrorに変換
            self.logger.error(f"JV-Link初期化中の予期しないエラー: {e}")
            raise JVLinkError(
                f"JV-Link初期化中にエラーが発生しました: {e}",
                context={'error': str(e)}
            )

    def initialize(self, max_retries: int = 3) -> bool:
        """
        JV-Linkの堅牢な初期化処理
        1. プロセスの存在確認
        2. 必要であればプロセス起動
        3. COMオブジェクト初期化
        4. JV-Link初期化

        Args:
            max_retries: 最大リトライ回数

        Returns:
            初期化成功の場合True

        Raises:
            JVLinkError: 致命的なエラーの場合
        """
        if self.is_initialized:
            self.logger.info("JV-Linkは既に初期化されています。")
            return True

        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                self.logger.info(
                    f"JV-Link初期化試行 {attempt + 1}/{max_retries + 1}")

                # ステップ1 & 2: プロセスの確認と条件付き起動
                if not self._is_jvlink_running():
                    self._start_jvlink_process()

                # ステップ3: COMオブジェクトの初期化
                self._create_com_object()

                # ステップ4: JV-Link初期化
                self._initialize_jvlink()

                self.is_initialized = True
                self.logger.info("JV-Linkの初期化に成功しました")
                return True

            except (JVLinkNetworkError, JVLinkTimeoutError) as e:
                # リトライ可能なエラー
                last_exception = e
                if attempt < max_retries:
                    delay = get_retry_delay(attempt)
                    self.logger.warning(
                        f"リトライ可能なエラー: {e}. {delay}秒後にリトライします...")
                    time.sleep(delay)
                    continue
                else:
                    self.logger.error(f"最大リトライ回数に達しました: {e}")
                    break

            except (JVLinkAuthError, JVLinkParameterError) as e:
                # 致命的なエラー（リトライしても無意味）
                self.logger.error(f"致命的なエラーのため初期化を中止します: {e}")
                raise

            except Exception as e:
                # 予期しないエラー
                last_exception = e
                if attempt < max_retries:
                    self.logger.warning(f"予期しないエラー: {e}. リトライします...")
                    time.sleep(get_retry_delay(attempt))
                    continue
                else:
                    self.logger.error(f"予期しないエラーのため初期化に失敗しました: {e}")
                    break

        # 全てのリトライが失敗した場合
        if last_exception:
            if isinstance(last_exception, JVLinkError):
                raise last_exception
            else:
                raise JVLinkError(
                    f"JV-Link初期化に失敗しました: {last_exception}",
                    context={'retries': max_retries,
                             'error': str(last_exception)}
                )

        return False

    def close(self) -> None:
        """
        JV-Linkの終了処理
        """
        try:
            if self.jvlink_com_obj:
                # COMオブジェクトの解放処理
                # (実際のCOM呼び出しは後で実装)
                # self.jvlink_com_obj.JVClose()
                self.jvlink_com_obj = None
                self.logger.info("JV-Link COMオブジェクトを解放しました")

            self.is_initialized = False
            self.logger.info("JV-Link接続をクローズしました")

        except Exception as e:
            self.logger.error(f"JV-Link終了処理エラー: {e}")

    def get_status_info(self) -> Dict[str, Any]:
        """
        アダプターの状態情報を取得

        Returns:
            状態情報の辞書
        """
        return {
            "initialized": self.is_initialized,
            "jvlink_path": self.jvlink_path,
            "process_running": self._is_jvlink_running(),
            "service_key_configured": False,  # サービスキーはレジストリに保存されるため、ここではFalse
            "com_object_available": self.jvlink_com_obj is not None,
            "psutil_available": PSUTIL_AVAILABLE,
            "win32com_available": WIN32COM_AVAILABLE,
        }

    def execute_with_retry(self, operation_func, operation_name: str,
                           max_retries: int = 3, **kwargs) -> Any:
        """
        リトライ機能付きでJV-Link操作を実行

        Args:
            operation_func: 実行する関数
            operation_name: 操作名（ログ用）
            max_retries: 最大リトライ回数
            **kwargs: operation_funcに渡す引数

        Returns:
            operation_funcの戻り値

        Raises:
            JVLinkError: 致命的なエラーまたは最大リトライ回数到達
        """
        last_exception = None

        for attempt in range(max_retries + 1):
            try:
                self.logger.debug(
                    f"{operation_name} 実行試行 {attempt + 1}/{max_retries + 1}")
                return operation_func(**kwargs)

            except Exception as e:
                last_exception = e

                if is_retryable_error(e) and attempt < max_retries:
                    delay = get_retry_delay(attempt)
                    self.logger.warning(
                        f"{operation_name}でリトライ可能なエラー: {e}. {delay}秒後にリトライ...")
                    time.sleep(delay)
                    continue
                else:
                    self.logger.error(f"{operation_name}でエラー: {e}")
                    raise

        # ここには到達しないはずだが、安全のため
        if last_exception:
            raise last_exception


# ファクトリ関数
def create_jvlink_adapter(jvlink_path: Optional[str] = None) -> JVLinkAdapter:
    """
    JV-Linkアダプターを作成

    Args:
        jvlink_path: JV-Link実行ファイルパス

    Returns:
        JVLinkAdapterインスタンス
    """
    return JVLinkAdapter(jvlink_path)
