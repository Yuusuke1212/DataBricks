"""
Error State Management for JRA-Data Collector

報告書修正点2: エラーダイアログの重複表示修正
責務分離によるクリーンなエラーハンドリングアーキテクチャ
"""

from datetime import datetime
from typing import Optional, Dict, Any
from PyQt5.QtCore import QObject, pyqtSignal as Signal

from .base import AppState
from ..workers.signals import LoggerMixin, LogRecord


class ErrorState(AppState, LoggerMixin):
    """
    アプリケーションのエラー状態を管理し、通知するクラス

    報告書修正点2: エラー発生時にログを記録し、error_occurred シグナルを発行
    UIダイアログ表示の責務は持たない（AppControllerが担当）
    """

    # シグナル定義
    error_occurred = Signal(str, str)  # title, message
    error_recovered = Signal()
    error_escalated = Signal(str, str, object)  # title, message, exception

    def __init__(self, error_title: str = "エラー", error_message: str = "不明なエラーが発生しました",
                 exception: Optional[Exception] = None, error_context: Optional[Dict[str, Any]] = None):
        AppState.__init__(self, "Error")
        LoggerMixin.__init__(self, "システムエラー", "ErrorState")

        self.error_title = error_title
        self.error_message = error_message
        self.exception = exception
        self.error_context = error_context or {}
        self.error_timestamp = datetime.now()
        self.error_id = self._generate_error_id()

        # エラー詳細ログの記録
        self._log_error_details()

        # エラー発生シグナルを発行（AppControllerがキャッチしてダイアログ表示）
        self.error_occurred.emit(self.error_title, self.error_message)

    def _generate_error_id(self) -> str:
        """一意のエラーIDを生成"""
        return f"ERR_{self.error_timestamp.strftime('%Y%m%d_%H%M%S_%f')}"

    def _log_error_details(self):
        """エラーの詳細をログに記録"""
        # 基本的なエラー情報
        self.emit_log(
            "ERROR", f"[{self.error_id}] {self.error_title}: {self.error_message}")

        # 例外情報がある場合
        if self.exception:
            self.emit_log(
                "ERROR", f"[{self.error_id}] 例外タイプ: {type(self.exception).__name__}")
            self.emit_log(
                "ERROR", f"[{self.error_id}] 例外詳細: {str(self.exception)}")

            # スタックトレース
            import traceback
            stack_trace = traceback.format_exception(
                type(self.exception), self.exception, self.exception.__traceback__)
            for line in stack_trace:
                self.emit_log("ERROR", f"[{self.error_id}] {line.strip()}")

        # コンテキスト情報がある場合
        if self.error_context:
            self.emit_log(
                "ERROR", f"[{self.error_id}] エラーコンテキスト: {self.error_context}")

    def enter(self, context):
        """エラー状態への遷移時の処理"""
        self.emit_log("INFO", f"エラー状態に遷移しました: {self.error_title}")

        # 進行中のタスクを安全に停止
        if hasattr(context, 'active_tasks'):
            for task_name in list(context.active_tasks.keys()):
                self.emit_log(
                    "WARNING", f"[{self.error_id}] タスク '{task_name}' を中断しています...")
                context.active_tasks[task_name]['status'] = 'error'

        # エラー統計を更新
        if hasattr(context, 'error_stats'):
            context.error_stats['total_errors'] = context.error_stats.get(
                'total_errors', 0) + 1
            context.error_stats['last_error_time'] = self.error_timestamp
            context.error_stats['last_error_id'] = self.error_id

    def exit(self, context):
        """エラー状態からの退出時の処理"""
        self.emit_log("INFO", f"エラー状態から退出します: {self.error_id}")

        # 回復可能なエラーの場合は回復シグナルを発行
        if self._is_recoverable_error():
            self.error_recovered.emit()

    def handle_user_input(self, action: str, context) -> 'AppState':
        """
        ユーザーからの入力に対する応答

        Args:
            action: 'retry', 'ignore', 'restart', 'quit'
            context: アプリケーションコンテキスト
        """
        self.emit_log("INFO", f"[{self.error_id}] ユーザーアクション: {action}")

        if action == 'retry':
            return self._handle_retry(context)
        elif action == 'ignore':
            return self._handle_ignore(context)
        elif action == 'restart':
            return self._handle_restart(context)
        elif action == 'quit':
            return self._handle_quit(context)
        else:
            self.emit_log("WARNING", f"[{self.error_id}] 不明なアクション: {action}")
            return self

    def _handle_retry(self, context) -> 'AppState':
        """再試行処理"""
        if self._is_retryable_error():
            self.emit_log("INFO", f"[{self.error_id}] エラーから再試行を実行")
            # 前の状態に戻る
            from .states import IdleState
            return IdleState()
        else:
            self.emit_log("WARNING", f"[{self.error_id}] このエラーは再試行できません")
            return self

    def _handle_ignore(self, context) -> 'AppState':
        """エラーを無視して継続"""
        self.emit_log("WARNING", f"[{self.error_id}] エラーを無視して継続")
        from .states import IdleState
        return IdleState()

    def _handle_restart(self, context) -> 'AppState':
        """アプリケーションを再起動状態にリセット"""
        self.emit_log("INFO", f"[{self.error_id}] アプリケーションを再起動")

        # すべてのタスクをクリア
        if hasattr(context, 'clear_all_tasks'):
            context.clear_all_tasks()

        from .states import IdleState
        return IdleState()

    def _handle_quit(self, context) -> 'AppState':
        """アプリケーション終了"""
        self.emit_log("INFO", f"[{self.error_id}] アプリケーション終了要求")

        # クリティカルエラーとしてエスカレーション
        self.error_escalated.emit(
            "アプリケーション終了",
            f"ユーザーがエラー [{self.error_id}] により終了を選択しました",
            self.exception
        )

        return self  # 終了処理は外部で実行

    def _is_recoverable_error(self) -> bool:
        """エラーが回復可能かどうかを判定"""
        if self.exception is None:
            return True

        # 特定の例外タイプは回復不可能
        unrecoverable_types = [
            'SystemExit',
            'KeyboardInterrupt',
            'MemoryError',
            'OSError'
        ]

        return type(self.exception).__name__ not in unrecoverable_types

    def _is_retryable_error(self) -> bool:
        """エラーが再試行可能かどうかを判定"""
        if not self._is_recoverable_error():
            return False

        # 一時的なエラーは再試行可能
        retryable_patterns = [
            'timeout',
            'connection',
            'network',
            'temporary',
            'deadlock'
        ]

        error_text = f"{self.error_title} {self.error_message}".lower()
        return any(pattern in error_text for pattern in retryable_patterns)

    def get_error_summary(self) -> Dict[str, Any]:
        """エラーサマリーを取得"""
        return {
            'error_id': self.error_id,
            'title': self.error_title,
            'message': self.error_message,
            'timestamp': self.error_timestamp.isoformat(),
            'exception_type': type(self.exception).__name__ if self.exception else None,
            'recoverable': self._is_recoverable_error(),
            'retryable': self._is_retryable_error(),
            'context': self.error_context
        }

    def to_log_record(self) -> LogRecord:
        """エラー情報をLogRecordとして出力"""
        return LogRecord(
            timestamp=self.error_timestamp,
            level="ERROR",
            task_name="システムエラー",
            worker_name="ErrorState",
            message=f"[{self.error_id}] {self.error_title}: {self.error_message}",
            context=self.get_error_summary()
        )
