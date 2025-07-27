"""
Unified Worker Signals for JRA-Data Collector

プロジェクト全体で使用する統一されたワーカーシグナル定義と
構造化ログのためのデータクラスを提供します。
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional
from PySide6.QtCore import QObject, Signal


@dataclass
class LogRecord:
    """
    構造化ログレコード

    マルチスレッド環境での詳細なログ管理とフィルタリングを可能にします。
    """
    timestamp: datetime
    level: str  # 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
    task_name: str  # 例: 'レース詳細', '騎手マスタ', 'データベース書き込み'
    worker_name: str  # 例: 'JvLinkReader', 'EtlProcessor', 'DatabaseWriter'
    message: str
    context: Optional[Dict[str, Any]] = None  # 追加のコンテキスト情報


@dataclass
class ProgressInfo:
    """
    進捗情報構造体

    ワーカーの進捗状況を詳細に追跡するための情報を格納します。
    """
    task_name: str
    worker_name: str
    percentage: int  # 0-100
    current_items: int
    total_items: int
    status_message: str
    elapsed_time: float
    estimated_remaining: Optional[float] = None


@dataclass
class TaskResult:
    """
    タスク完了結果

    ワーカーの処理完了時の詳細な結果情報を格納します。
    """
    task_name: str
    worker_name: str
    success: bool
    items_processed: int
    records_written: int
    processing_time: float
    error_message: Optional[str] = None
    summary: Optional[Dict[str, Any]] = None


class WorkerSignals(QObject):
    """
    統一されたワーカーシグナル定義

    すべてのワーカークラスで使用する標準化されたシグナルセット。
    構造化されたデータを通じて型安全な通信を実現します。
    """

    # 進捗報告 - ProgressInfo構造体を使用
    progress = Signal(object)  # ProgressInfo

    # ステータス更新 - タスクとワーカーの状態変更
    status = Signal(str, str, str)  # task_name, worker_name, status_message

    # タスク完了 - TaskResult構造体を使用
    finished = Signal(object)  # TaskResult

    # エラー発生 - 詳細なエラー情報
    error = Signal(str, str, str)  # task_name, worker_name, error_message

    # 構造化ログ - LogRecord構造体を使用
    log = Signal(object)  # LogRecord

    # データ受信 - レガシー互換性のため維持
    data_received = Signal(list)

    # 操作完了 - レガシー互換性のため維持
    operation_finished = Signal(str)


class LoggerMixin:
    """
    構造化ログを発行するためのミックスイン

    ワーカークラスに追加することで、統一されたログ機能を提供します。
    """

    def __init__(self, task_name: str, worker_name: str):
        self.task_name = task_name
        self.worker_name = worker_name
        self.signals = WorkerSignals()

    def emit_log(self, level: str, message: str, context: Optional[Dict[str, Any]] = None):
        """構造化ログを発行"""
        log_record = LogRecord(
            timestamp=datetime.now(),
            level=level,
            task_name=self.task_name,
            worker_name=self.worker_name,
            message=message,
            context=context
        )
        self.signals.log.emit(log_record)

    def emit_progress(self, percentage: int, current_items: int, total_items: int,
                      status_message: str, elapsed_time: float,
                      estimated_remaining: Optional[float] = None):
        """進捗情報を発行"""
        progress_info = ProgressInfo(
            task_name=self.task_name,
            worker_name=self.worker_name,
            percentage=percentage,
            current_items=current_items,
            total_items=total_items,
            status_message=status_message,
            elapsed_time=elapsed_time,
            estimated_remaining=estimated_remaining
        )
        self.signals.progress.emit(progress_info)

    def emit_status(self, status_message: str):
        """ステータス更新を発行"""
        self.signals.status.emit(
            self.task_name, self.worker_name, status_message)

    def emit_error(self, error_message: str):
        """エラーを発行"""
        self.signals.error.emit(
            self.task_name, self.worker_name, error_message)
        self.emit_log("ERROR", error_message)

    def emit_finished(self, success: bool, items_processed: int, records_written: int,
                      processing_time: float, error_message: Optional[str] = None,
                      summary: Optional[Dict[str, Any]] = None):
        """完了結果を発行"""
        result = TaskResult(
            task_name=self.task_name,
            worker_name=self.worker_name,
            success=success,
            items_processed=items_processed,
            records_written=records_written,
            processing_time=processing_time,
            error_message=error_message,
            summary=summary
        )
        self.signals.finished.emit(result)
