"""
Pipeline Coordinator for JRA-Data Collector

Producer-Consumer パイプライン全体を統合管理し、
State Machine との連携を担うコーディネーター
"""

from typing import Dict, List, Any, Optional, Callable
import logging
import time
import queue
from queue import Queue
from threading import Event

from .base import BaseWorker, CancellationToken, ProgressInfo, WorkerState
from .jvlink_reader import JvLinkReaderWorker
from .etl_processor_worker import EtlProcessorWorker
from .database_writer import DatabaseWriterWorker


class PipelineCoordinator:
    """
    データ処理パイプライン全体を統合管理するコーディネーター

    JvLinkReader → EtlProcessor → DatabaseWriter のフローを制御し、
    State Machine との連携、エラーハンドリング、進捗管理を行います。
    """

    def __init__(self,
                 jvlink_manager,
                 etl_processor,
                 db_manager,
                 settings_manager,
                 progress_callback: Optional[Callable[[
                     ProgressInfo], None]] = None,
                 error_callback: Optional[Callable[[
                     str, Exception], None]] = None,
                 pipeline_config: Optional[Dict[str, Any]] = None):

        self.jvlink_manager = jvlink_manager
        self.etl_processor = etl_processor
        self.db_manager = db_manager
        self.settings_manager = settings_manager

        # コールバック
        self.progress_callback = progress_callback
        self.error_callback = error_callback

        # パイプライン設定
        config = pipeline_config or {}
        self.raw_queue_size = config.get('raw_queue_size', 1000)
        self.processed_queue_size = config.get('processed_queue_size', 500)
        self.etl_batch_size = config.get('etl_batch_size', 10)
        self.db_batch_size = config.get('db_batch_size', 100)
        self.db_commit_interval = config.get('db_commit_interval', 1000)

        # キューと同期オブジェクト
        self.raw_data_queue: Queue = Queue(maxsize=self.raw_queue_size)
        self.processed_data_queue: Queue = Queue(
            maxsize=self.processed_queue_size)
        self.cancellation_token = CancellationToken()
        self.pipeline_finished = Event()

        # ワーカーインスタンス
        self.workers: List[BaseWorker] = []
        self.jvlink_reader: Optional[JvLinkReaderWorker] = None
        self.etl_processor_worker: Optional[EtlProcessorWorker] = None
        self.db_writer: Optional[DatabaseWriterWorker] = None

        # 統計情報
        self.pipeline_start_time: Optional[float] = None
        self.pipeline_end_time: Optional[float] = None
        self.total_processing_time: Optional[float] = None

        # ログ
        self.logger = logging.getLogger("PipelineCoordinator")

    def start_pipeline(self, data_params: Dict[str, Any], etl_rules: Dict[str, Any]) -> bool:
        """
        パイプラインを開始

        Args:
            data_params: データ取得パラメータ
            etl_rules: ETL処理ルール

        Returns:
            bool: 開始に成功した場合True
        """
        try:
            self.logger.info("Starting data processing pipeline...")
            self.pipeline_start_time = time.time()

            # キャンセレーショントークンをリセット
            self.cancellation_token = CancellationToken()
            self.pipeline_finished.clear()

            # ワーカーを作成
            self._create_workers(data_params, etl_rules)

            # ワーカーを開始
            self._start_workers()

            self.logger.info("Pipeline started successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start pipeline: {e}")
            self._handle_pipeline_error("Pipeline startup", e)
            return False

    def _create_workers(self, data_params: Dict[str, Any], etl_rules: Dict[str, Any]) -> None:
        """ワーカーインスタンスを作成"""

        # 1. JvLink Reader (Producer)
        self.jvlink_reader = JvLinkReaderWorker(
            raw_data_queue=self.raw_data_queue,
            jvlink_manager=self.jvlink_manager,
            data_params=data_params,
            cancellation_token=self.cancellation_token,
            progress_callback=self._on_worker_progress,
            error_callback=self._on_worker_error
        )

        # 2. ETL Processor (Transformer)
        self.etl_processor_worker = EtlProcessorWorker(
            raw_data_queue=self.raw_data_queue,
            processed_data_queue=self.processed_data_queue,
            etl_processor=self.etl_processor,
            etl_rules=etl_rules,
            cancellation_token=self.cancellation_token,
            progress_callback=self._on_worker_progress,
            error_callback=self._on_worker_error,
            batch_size=self.etl_batch_size
        )

        # 3. Database Writer (Loader)
        self.db_writer = DatabaseWriterWorker(
            processed_data_queue=self.processed_data_queue,
            db_manager=self.db_manager,
            cancellation_token=self.cancellation_token,
            progress_callback=self._on_worker_progress,
            error_callback=self._on_worker_error,
            batch_size=self.db_batch_size,
            commit_interval=self.db_commit_interval
        )

        # ワーカーリストに追加
        self.workers = [self.jvlink_reader,
                        self.etl_processor_worker, self.db_writer]

    def _start_workers(self) -> None:
        """すべてのワーカーを開始"""
        for worker in self.workers:
            if worker:
                worker.start()
                self.logger.info(f"Started worker: {worker.worker_name}")

    def stop_pipeline(self, timeout: float = 30.0) -> bool:
        """
        パイプラインを停止

        Args:
            timeout: 停止待機時間（秒）

        Returns:
            bool: 正常に停止した場合True
        """
        try:
            self.logger.info("Stopping data processing pipeline...")

            # キャンセル要求
            self.cancellation_token.cancel("Pipeline stop requested")

            # ワーカーの停止を待機
            all_stopped = True
            for worker in self.workers:
                if worker and worker.is_alive():
                    if not worker.stop(timeout / len(self.workers)):
                        all_stopped = False
                        self.logger.warning(
                            f"Worker {worker.worker_name} did not stop gracefully")

            # パイプライン終了時刻を記録
            self.pipeline_end_time = time.time()
            if self.pipeline_start_time:
                self.total_processing_time = self.pipeline_end_time - self.pipeline_start_time

            # 最終統計をログ
            self._log_final_statistics()

            # 完了シグナル
            self.pipeline_finished.set()

            self.logger.info(
                f"Pipeline stopped {'successfully' if all_stopped else 'with warnings'}")
            return all_stopped

        except Exception as e:
            self.logger.error(f"Error stopping pipeline: {e}")
            return False

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        パイプライン完了を待機

        Args:
            timeout: 待機時間（秒、Noneで無制限）

        Returns:
            bool: 完了した場合True、タイムアウトの場合False
        """
        try:
            # すべてのワーカーが完了するまで待機
            for worker in self.workers:
                if worker and worker.is_alive():
                    worker.join(timeout)

                    if worker.is_alive():
                        self.logger.warning(
                            f"Worker {worker.worker_name} did not complete within timeout")
                        return False

            # パイプライン完了
            self.pipeline_end_time = time.time()
            if self.pipeline_start_time:
                self.total_processing_time = self.pipeline_end_time - self.pipeline_start_time

            self._log_final_statistics()
            self.pipeline_finished.set()

            self.logger.info("Pipeline completed successfully")
            return True

        except Exception as e:
            self.logger.error(f"Error waiting for pipeline completion: {e}")
            return False

    def _on_worker_progress(self, progress: ProgressInfo) -> None:
        """ワーカーからの進捗更新を処理"""
        try:
            # 統合進捗情報を作成
            integrated_progress = self._calculate_integrated_progress(progress)

            # State Machine または UI にコールバック
            if self.progress_callback:
                self.progress_callback(integrated_progress)

            # 定期的にログ出力
            if progress.current_item % 500 == 0:
                self.logger.info(
                    f"Progress: {progress.worker_name} - {progress.percentage:.1f}% "
                    f"({progress.current_item}/{progress.total_items}) - {progress.message}"
                )

        except Exception as e:
            self.logger.error(f"Error handling worker progress: {e}")

    def _calculate_integrated_progress(self, worker_progress: ProgressInfo) -> ProgressInfo:
        """
        複数ワーカーの進捗を統合した全体進捗を計算

        Args:
            worker_progress: 個別ワーカーの進捗

        Returns:
            ProgressInfo: 統合進捗情報
        """
        # 各ワーカーの統計を取得
        reader_stats = self.jvlink_reader.get_stats() if self.jvlink_reader else {}
        etl_stats = self.etl_processor_worker.get_stats() if self.etl_processor_worker else {}
        db_stats = self.db_writer.get_stats() if self.db_writer else {}

        # 統合メッセージを作成
        reader_items = reader_stats.get('items_processed', 0)
        etl_items = etl_stats.get('items_processed', 0)
        db_items = db_stats.get('items_processed', 0)
        db_records = db_stats.get('records_written', 0)

        integrated_message = (
            f"Read: {reader_items}, ETL: {etl_items}, DB: {db_items} items, "
            f"{db_records} records written"
        )

        # 統合進捗率を計算（最も遅いワーカーの進捗を基準）
        min_items = min(reader_items, etl_items,
                        db_items) if reader_items > 0 else 0
        total_expected = reader_stats.get('total_specs', 1)

        integrated_percentage = (
            min_items / total_expected * 100) if total_expected > 0 else 0

        return ProgressInfo(
            worker_name="Pipeline",
            current_item=min_items,
            total_items=total_expected,
            message=integrated_message,
            percentage=integrated_percentage
        )

    def _on_worker_error(self, worker_name: str, error: Exception) -> None:
        """ワーカーエラーを処理"""
        self.logger.error(f"Worker {worker_name} error: {error}")

        # エラーコールバック
        if self.error_callback:
            try:
                self.error_callback(worker_name, error)
            except Exception as callback_error:
                self.logger.error(f"Error callback failed: {callback_error}")

        # 重大なエラーの場合はパイプライン全体を停止
        if self._is_critical_error(error):
            self.logger.error("Critical error detected, stopping pipeline")
            self.stop_pipeline()

    def _is_critical_error(self, error: Exception) -> bool:
        """
        重大なエラーかどうかを判定

        Args:
            error: 発生したエラー

        Returns:
            bool: 重大なエラーの場合True
        """
        # データベース接続エラー、JV-Link認証エラーなどは重大
        critical_error_types = [
            "ConnectionError",
            "AuthenticationError",
            "DatabaseError",
            "PermissionError"
        ]

        error_type = type(error).__name__
        return error_type in critical_error_types

    def _handle_pipeline_error(self, context: str, error: Exception) -> None:
        """パイプライン全体のエラーハンドリング"""
        self.logger.error(f"Pipeline error in {context}: {error}")

        try:
            # パイプラインを停止
            self.stop_pipeline()

            # エラー情報をState Machineに通知
            if self.error_callback:
                self.error_callback("Pipeline", error)

        except Exception as handle_error:
            self.logger.critical(
                f"Failed to handle pipeline error: {handle_error}")

    def _log_final_statistics(self) -> None:
        """最終統計をログ出力"""
        try:
            # 各ワーカーの統計を収集
            stats = self.get_pipeline_stats()

            self.logger.info("=" * 60)
            self.logger.info("PIPELINE COMPLETION STATISTICS")
            self.logger.info("=" * 60)

            if self.total_processing_time:
                self.logger.info(
                    f"Total processing time: {self.total_processing_time:.2f} seconds")

            # Reader統計
            reader_stats = stats.get('jvlink_reader', {})
            self.logger.info(
                f"JvLink Reader: {reader_stats.get('items_processed', 0)} items read")

            # ETL統計
            etl_stats = stats.get('etl_processor', {})
            self.logger.info(
                f"ETL Processor: {etl_stats.get('items_processed', 0)} items, "
                f"{etl_stats.get('records_processed', 0)} records processed"
            )

            # DB Writer統計
            db_stats = stats.get('database_writer', {})
            self.logger.info(
                f"Database Writer: {db_stats.get('items_processed', 0)} items, "
                f"{db_stats.get('records_written', 0)} records written"
            )

            # テーブル別統計
            table_stats = db_stats.get('table_stats', {})
            if table_stats:
                self.logger.info("Table breakdown:")
                for table, count in sorted(table_stats.items()):
                    self.logger.info(f"  {table}: {count} records")

            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"Error logging final statistics: {e}")

    def get_pipeline_stats(self) -> Dict[str, Any]:
        """パイプライン全体の統計情報を取得"""
        stats = {
            'pipeline_start_time': self.pipeline_start_time,
            'pipeline_end_time': self.pipeline_end_time,
            'total_processing_time': self.total_processing_time,
            'is_running': not self.cancellation_token.is_cancelled,
            'pipeline_config': {
                'raw_queue_size': self.raw_queue_size,
                'processed_queue_size': self.processed_queue_size,
                'etl_batch_size': self.etl_batch_size,
                'db_batch_size': self.db_batch_size,
                'db_commit_interval': self.db_commit_interval
            }
        }

        # 各ワーカーの統計を追加
        if self.jvlink_reader:
            stats['jvlink_reader'] = self.jvlink_reader.get_stats()
        if self.etl_processor_worker:
            stats['etl_processor'] = self.etl_processor_worker.get_stats()
        if self.db_writer:
            stats['database_writer'] = self.db_writer.get_stats()

        # キューの状況
        stats['queue_status'] = {
            'raw_data_queue_size': self.raw_data_queue.qsize(),
            'processed_data_queue_size': self.processed_data_queue.qsize()
        }

        return stats

    @property
    def is_running(self) -> bool:
        """パイプラインが実行中かどうかを判定"""
        return not self.cancellation_token.is_cancelled and any(
            worker.is_running for worker in self.workers if worker
        )

    @property
    def is_completed(self) -> bool:
        """パイプラインが完了したかどうかを判定"""
        return self.pipeline_finished.is_set()
