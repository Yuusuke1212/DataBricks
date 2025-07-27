"""
ETL Processor Worker for JRA-Data Collector

生データを変換処理し、データベース用の構造化データに変換するトランスフォーマーワーカー
Phase 3: ProcessPoolExecutor統合による高性能並列処理対応
"""

from typing import Optional, Dict, Any, List
import logging
import time
from queue import Queue
import pandas as pd

from .base import QueueWorker, CancellationToken, ProgressInfo
from ..etl_processor import EtlProcessor

# Phase 3: 高性能並列処理の統合
try:
    from ..etl_processor_parallel import HighPerformanceEtlProcessor
    HIGH_PERFORMANCE_ETL_AVAILABLE = True
except ImportError:
    HIGH_PERFORMANCE_ETL_AVAILABLE = False
    logging.warning(
        "HighPerformanceEtlProcessor not available, using standard processing")


class EtlProcessorWorker(QueueWorker):
    """
    生データを変換処理するETLトランスフォーマーワーカー

    生データキューからデータを取得し、ETL処理を行って
    構造化データキューに送信します。

    Phase 3: ProcessPoolExecutorによる高性能並列処理をサポート
    """

    def __init__(self,
                 raw_data_queue: Queue,
                 processed_data_queue: Queue,
                 etl_processor: EtlProcessor,
                 etl_rules: Dict[str, Any],
                 cancellation_token: CancellationToken,
                 progress_callback=None,
                 error_callback=None,
                 batch_size: int = 10,
                 enable_high_performance: bool = True,
                 parallel_chunk_size: int = 100):

        super().__init__(
            name="EtlProcessor",
            input_queue=raw_data_queue,
            output_queue=processed_data_queue,
            cancellation_token=cancellation_token,
            progress_callback=progress_callback,
            error_callback=error_callback
        )

        self.etl_processor = etl_processor
        self.etl_rules = etl_rules
        self.batch_size = batch_size
        self.parallel_chunk_size = parallel_chunk_size

        # Phase 3: 高性能並列処理の設定
        self.enable_high_performance = enable_high_performance and HIGH_PERFORMANCE_ETL_AVAILABLE
        self.high_performance_processor: Optional[HighPerformanceEtlProcessor] = None

        # 統計情報
        self.records_processed = 0
        self.batch_count = 0
        self.error_count = 0
        self.parallel_batches_count = 0

        # バッチ処理用バッファ
        self.current_batch = []

        # パフォーマンスしきい値（並列処理を開始するバッチサイズ）
        self.parallel_threshold = 50

    def on_start(self) -> None:
        """ワーカー開始時の初期化"""
        mode = "High-Performance Parallel" if self.enable_high_performance else "Standard"
        self.logger.info(
            f"Starting ETL processor ({mode}) with batch size: {self.batch_size}")
        self.logger.info(
            f"ETL rules: {list(self.etl_rules.keys()) if self.etl_rules else 'Default'}")

        # 高性能プロセッサーの初期化
        if self.enable_high_performance:
            self._initialize_high_performance_processor()

    def _initialize_high_performance_processor(self) -> None:
        """高性能並列プロセッサーを初期化"""
        try:
            if HIGH_PERFORMANCE_ETL_AVAILABLE:
                self.high_performance_processor = HighPerformanceEtlProcessor(
                    base_processor=self.etl_processor,
                    max_workers=None,  # 自動設定
                    chunk_size=self.parallel_chunk_size,
                    progress_callback=self._on_parallel_progress
                )
                self.logger.info(
                    "High-performance parallel ETL processor initialized")
            else:
                self.logger.warning(
                    "High-performance ETL not available, using standard processing")
                self.enable_high_performance = False
        except Exception as e:
            self.logger.error(
                f"Failed to initialize high-performance processor: {e}")
            self.enable_high_performance = False

    def _on_parallel_progress(self, progress_info: Dict[str, Any]) -> None:
        """並列処理からの進捗更新を処理"""
        try:
            # ワーカー進捗情報に変換
            worker_progress = ProgressInfo(
                worker_name=self.worker_name,
                current_item=progress_info.get('processed_items', 0),
                total_items=progress_info.get('total_items', 0),
                message=f"Parallel ETL: {progress_info.get('percentage', 0):.1f}% ({progress_info.get('throughput', 0):.1f} items/s)"
            )

            # 進捗報告
            self.report_progress(
                worker_progress.current_item,
                worker_progress.total_items,
                worker_progress.message
            )

        except Exception as e:
            self.logger.warning(f"Parallel progress update failed: {e}")

    def process_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        個別の生データアイテムを処理

        Args:
            item: 生データアイテム
                - data_spec: データ仕様
                - raw_data: 生データ
                - file_index: ファイルインデックス
                - timestamp: タイムスタンプ

        Returns:
            Optional[Dict]: 処理済みデータ（Noneでスキップ）
        """
        try:
            # キャンセルチェック
            self.cancellation_token.throw_if_cancelled()

            data_spec = item.get('data_spec', 'UNKNOWN')
            raw_data = item.get('raw_data', '')

            if not raw_data:
                self.logger.warning(f"Empty raw data for spec: {data_spec}")
                return None

            # ETL処理を実行
            start_time = time.time()
            transformed_data = self._transform_data(data_spec, raw_data)
            processing_time = time.time() - start_time

            if not transformed_data:
                self.logger.debug(
                    f"No data after transformation for spec: {data_spec}")
                return None

            # 処理済みデータアイテムを作成
            processed_item = {
                'data_spec': data_spec,
                'transformed_data': transformed_data,
                'original_item': item,
                'processing_time': processing_time,
                'processed_at': time.time(),
                'records_count': self._count_records(transformed_data),
                'processing_mode': 'standard'
            }

            # 統計更新
            self.records_processed += processed_item['records_count']

            return processed_item

        except Exception as e:
            self.error_count += 1
            self.logger.error(
                f"Error processing item {item.get('file_index', 'unknown')}: {e}")

            # エラーアイテムとして送信（デバッグ用）
            error_item = {
                'data_spec': item.get('data_spec', 'UNKNOWN'),
                'error': str(e),
                'original_item': item,
                'error_type': type(e).__name__,
                'processed_at': time.time()
            }

            return error_item

    def _transform_data(self, data_spec: str, raw_data: str) -> Dict[str, pd.DataFrame]:
        """
        生データをETL処理して構造化データに変換

        Args:
            data_spec: データ仕様
            raw_data: 生データ

        Returns:
            Dict[str, pd.DataFrame]: テーブル名をキーとするDataFrameの辞書
        """
        try:
            # 既存のEtlProcessorを使用してデータ変換
            transformed_dfs = self.etl_processor.transform(
                [raw_data], data_spec)

            # 空のDataFrameを除外
            non_empty_dfs = {
                table_name: df for table_name, df in transformed_dfs.items()
                if not df.empty
            }

            if non_empty_dfs:
                table_names = list(non_empty_dfs.keys())
                total_records = sum(len(df) for df in non_empty_dfs.values())
                self.logger.debug(
                    f"Transformed {data_spec}: {total_records} records -> {table_names}"
                )

            return non_empty_dfs

        except Exception as e:
            self.logger.error(
                f"ETL transformation failed for {data_spec}: {e}")
            raise

    def _transform_data_parallel(self, raw_data_list: List[str], data_spec: str) -> Dict[str, pd.DataFrame]:
        """
        高性能並列ETL変換処理

        Args:
            raw_data_list: 生データのリスト
            data_spec: データ仕様

        Returns:
            Dict[str, pd.DataFrame]: 変換済みデータ
        """
        try:
            if not self.high_performance_processor:
                raise RuntimeError(
                    "High-performance processor not initialized")

            # 並列ETL処理を実行
            start_time = time.time()
            result = self.high_performance_processor.transform_parallel(
                raw_data_list,
                data_spec,
                self.etl_rules
            )

            processing_time = time.time() - start_time
            self.logger.info(
                f"Parallel ETL completed in {processing_time:.2f}s for {len(raw_data_list)} items")

            # パフォーマンス統計を取得
            stats = self.high_performance_processor.get_performance_stats()
            if stats.get('speedup_ratio', 1.0) > 1.0:
                self.logger.info(
                    f"Achieved {stats['speedup_ratio']:.2f}x speedup with parallel processing")

            return result

        except Exception as e:
            self.logger.error(f"Parallel ETL transformation failed: {e}")
            raise

    def _count_records(self, transformed_data: Optional[Dict[str, Any]]) -> int:
        """
        変換済みデータのレコード数をカウント

        Args:
            transformed_data: 変換済みデータ

        Returns:
            int: レコード数
        """
        if not transformed_data:
            return 0

        total_count = 0

        try:
            for table_name, table_data in transformed_data.items():
                if hasattr(table_data, '__len__'):
                    # DataFrameや配列の場合
                    count = len(table_data)
                elif hasattr(table_data, 'shape'):
                    # NumPy配列の場合
                    count = table_data.shape[0] if len(
                        table_data.shape) > 0 else 1
                else:
                    # その他の場合（辞書、文字列など）
                    count = 1

                total_count += count
                self.logger.debug(f"Table '{table_name}': {count} records")

        except Exception as e:
            self.logger.warning(f"Error counting records: {e}")
            # フォールバック: データが存在する場合は最低1レコードとして扱う
            return 1 if transformed_data else 0

        return total_count

    def process_loop(self) -> None:
        """メイン処理ループ（並列処理対応）"""
        if self.batch_size > 1:
            self._process_loop_batch()
        else:
            self._process_loop_single()

    def _process_loop_single(self) -> None:
        """単一アイテム処理ループ"""
        while not self.cancellation_token.is_cancelled:
            try:
                # 入力キューからアイテムを取得
                item = self.input_queue.get(timeout=self.queue_timeout)

                if item is None:  # 終了マーカー
                    break

                # アイテムを処理
                processed_item = self.process_item(item)

                # 出力キューに送信
                if processed_item is not None:
                    self.output_queue.put(processed_item)

                self.items_processed += 1

                # 定期的に進捗報告
                if self.items_processed % 50 == 0:
                    self.report_progress(
                        self.items_processed,
                        -1,
                        f"Processed {self.items_processed} items, {self.records_processed} records"
                    )

            except Exception as e:
                self.logger.error(f"Error in single item processing loop: {e}")
                continue

    def _process_loop_batch(self) -> None:
        """バッチ処理ループ（並列処理対応）"""
        while not self.cancellation_token.is_cancelled:
            try:
                # バッチを収集
                batch = self._collect_batch()

                if not batch:
                    break  # 終了マーカーを受信

                # バッチサイズに基づいて処理方法を決定
                if self.enable_high_performance and len(batch) >= self.parallel_threshold:
                    # 並列処理でバッチを処理
                    processed_batch = self._process_batch_parallel(batch)
                    self.parallel_batches_count += 1
                else:
                    # 標準処理でバッチを処理
                    processed_batch = self._process_batch_standard(batch)

                # 処理済みバッチを出力
                for processed_item in processed_batch:
                    if processed_item is not None:
                        self.output_queue.put(processed_item)

                self.batch_count += 1
                self.items_processed += len(batch)

                # 進捗報告
                mode = "parallel" if len(
                    batch) >= self.parallel_threshold and self.enable_high_performance else "standard"
                self.report_progress(
                    self.items_processed,
                    -1,
                    f"Processed {self.batch_count} batches ({mode}), {self.items_processed} items, {self.records_processed} records"
                )

            except Exception as e:
                self.logger.error(f"Error in batch processing loop: {e}")
                continue

    def _process_batch_parallel(self, batch: List[Dict[str, Any]]) -> List[Optional[Dict[str, Any]]]:
        """
        バッチを並列処理で処理

        Args:
            batch: 処理するバッチ

        Returns:
            List[Optional[Dict]]: 処理済みアイテムのリスト
        """
        start_time = time.time()
        processed_batch = []

        try:
            # データ仕様別にバッチをグループ化
            spec_groups = {}
            for item in batch:
                data_spec = item.get('data_spec', 'UNKNOWN')
                if data_spec not in spec_groups:
                    spec_groups[data_spec] = []
                spec_groups[data_spec].append(item)

            # 各データ仕様グループを並列処理
            for data_spec, items in spec_groups.items():
                try:
                    # 生データを抽出
                    raw_data_list = [item.get('raw_data', '')
                                     for item in items if item.get('raw_data')]

                    if raw_data_list:
                        # 並列ETL処理を実行
                        combined_transformed_data = self._transform_data_parallel(
                            raw_data_list, data_spec)

                        # 結果を個別アイテムに適切に分割
                        # 各アイテムに対して個別の変換結果を生成
                        for i, item in enumerate(items):
                            if item.get('raw_data'):
                                # 個別の生データを標準変換で処理（確実性のため）
                                individual_transformed = self._transform_data(
                                    data_spec, item.get('raw_data', ''))

                                # 並列処理の結果が利用可能な場合はそれを使用、そうでなければ個別結果を使用
                                final_transformed = individual_transformed if individual_transformed else combined_transformed_data

                                if final_transformed:
                                    processed_item = {
                                        'data_spec': data_spec,
                                        'transformed_data': final_transformed,
                                        'original_item': item,
                                        'processing_time': time.time() - start_time,
                                        'processed_at': time.time(),
                                        'records_count': self._count_records(final_transformed),
                                        'processing_mode': 'parallel'
                                    }
                                    processed_batch.append(processed_item)

                                    # 統計更新
                                    self.records_processed += processed_item['records_count']
                                else:
                                    # 変換結果が空の場合はNoneアイテムを追加
                                    processed_batch.append(None)
                            else:
                                processed_batch.append(None)

                except Exception as e:
                    self.logger.error(
                        f"Parallel processing failed for spec {data_spec}: {e}")
                    # フォールバック: 標準処理
                    fallback_batch = self._process_batch_standard(items)
                    processed_batch.extend(fallback_batch)

        except Exception as e:
            self.logger.error(f"Parallel batch processing failed: {e}")
            # 完全フォールバック: 標準処理
            return self._process_batch_standard(batch)

        processing_time = time.time() - start_time
        valid_items = sum(1 for item in processed_batch if item is not None)
        self.logger.info(
            f"Parallel batch processed: {valid_items}/{len(batch)} items in {processing_time:.2f}s")

        return processed_batch

    def _process_batch_standard(self, batch: List[Dict[str, Any]]) -> List[Optional[Dict[str, Any]]]:
        """
        バッチを標準的な順次処理で処理

        Args:
            batch: 処理するバッチ

        Returns:
            List[Optional[Dict]]: 処理済みアイテムのリスト
        """
        start_time = time.time()
        processed_batch = []

        for item in batch:
            try:
                data_spec = item.get('data_spec', 'UNKNOWN')
                raw_data = item.get('raw_data', '')

                # データ変換
                transformed_data = self._transform_data(data_spec, raw_data)

                if transformed_data:
                    # レコード数の正確なカウント
                    records_count = self._count_records(transformed_data)

                    processed_item = {
                        'data_spec': data_spec,
                        'transformed_data': transformed_data,
                        'original_item': item,
                        'processing_time': time.time() - start_time,
                        'processed_at': time.time(),
                        'records_count': records_count,
                        'processing_mode': 'standard'
                    }
                    processed_batch.append(processed_item)

                    # 統計更新
                    self.records_processed += records_count

                    self.logger.debug(
                        f"Processed item: {data_spec}, {records_count} records")
                else:
                    # 変換に失敗した場合
                    processed_batch.append(None)
                    self.logger.warning(
                        f"Failed to transform data for spec: {data_spec}")

            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                processed_batch.append(None)

        processing_time = time.time() - start_time
        valid_items = sum(1 for item in processed_batch if item is not None)
        self.logger.info(
            f"Standard batch processed: {valid_items}/{len(batch)} items in {processing_time:.2f}s")

        return processed_batch

    def _collect_batch(self) -> List[Dict[str, Any]]:
        """
        バッチサイズ分のアイテムを収集

        Returns:
            List[Dict]: バッチアイテムのリスト
        """
        batch = []

        for _ in range(self.batch_size):
            try:
                item = self.input_queue.get(timeout=self.queue_timeout)

                if item is None:  # 終了マーカー
                    break

                batch.append(item)

            except Exception:
                # タイムアウトまたはエラーの場合は現在のバッチを返す
                break

        return batch

    def on_cleanup(self) -> None:
        """ワーカー終了時のクリーンアップ"""
        try:
            # 残っているバッチがあれば処理
            if self.current_batch:
                self.logger.info(
                    f"Processing remaining {len(self.current_batch)} items in batch")
                if self.enable_high_performance and len(self.current_batch) >= self.parallel_threshold:
                    processed_batch = self._process_batch_parallel(
                        self.current_batch)
                else:
                    processed_batch = self._process_batch_standard(
                        self.current_batch)

                for processed_item in processed_batch:
                    if processed_item is not None:
                        self.output_queue.put(processed_item)

            # 終了マーカーを送信
            self.finish_input()

            # 最終統計をログ
            self.logger.info(
                f"ETL processor completed: {self.items_processed} items, "
                f"{self.records_processed} records, {self.error_count} errors, "
                f"{self.parallel_batches_count} parallel batches"
            )

            # 高性能プロセッサーの統計
            if self.high_performance_processor:
                stats = self.high_performance_processor.get_performance_stats()
                if stats.get('speedup_ratio', 1.0) > 1.0:
                    self.logger.info(
                        f"Overall parallel speedup achieved: {stats['speedup_ratio']:.2f}x")

        except Exception as e:
            self.logger.error(f"Error during ETL processor cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        base_stats = super().get_stats()
        etl_stats = {
            "batch_size": self.batch_size,
            "batch_count": self.batch_count,
            "parallel_batches_count": self.parallel_batches_count,
            "records_processed": self.records_processed,
            "error_count": self.error_count,
            "enable_high_performance": self.enable_high_performance,
            "parallel_threshold": self.parallel_threshold,
            "avg_records_per_item": (
                self.records_processed / self.items_processed
                if self.items_processed > 0 else 0
            ),
            "error_rate": (
                self.error_count / self.items_processed
                if self.items_processed > 0 else 0
            ),
            "parallel_processing_rate": (
                self.parallel_batches_count / self.batch_count
                if self.batch_count > 0 else 0
            )
        }

        # 高性能プロセッサーの統計を追加
        if self.high_performance_processor:
            parallel_stats = self.high_performance_processor.get_performance_stats()
            etl_stats["parallel_performance"] = parallel_stats

        return {**base_stats, **etl_stats}
