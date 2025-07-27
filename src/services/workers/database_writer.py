"""
Database Writer Worker for JRA-Data Collector

構造化データをデータベースに効率的に書き込むローダーワーカー
"""

from typing import Optional, Dict, Any, List
import logging
import time
from queue import Queue
import pandas as pd
from collections import defaultdict

from .base import QueueWorker, CancellationToken, ProgressInfo
# 循環インポートを避けるため、DatabaseManagerは遅延インポートまたは依存性注入を使用


class DatabaseWriterWorker(QueueWorker):
    """
    構造化データをデータベースに書き込むローダーワーカー

    Phase 3 Update: 循環インポート解決済み、依存性注入パターン使用
    """

    def __init__(self, db_manager=None, table_name="default_table", batch_size=1000):
        """
        Args:
            db_manager: DatabaseManagerインスタンス（依存性注入）
            table_name: 書き込み先テーブル名
            batch_size: バッチ書き込みサイズ
        """
        super().__init__()
        self.db_manager = db_manager
        self.table_name = table_name
        self.batch_size = batch_size
        self.pending_data = []
        self.write_stats = defaultdict(int)

        if self.db_manager is None:
            # 遅延インポート（最後の手段）
            self._lazy_init_db_manager()

    def _lazy_init_db_manager(self):
        """遅延インポートでDatabaseManagerを初期化"""
        try:
            from ..db_manager import DatabaseManager
            # 注意: この場合はsettings_managerが必要
            # 通常は外部から注入されることが望ましい
            self.db_manager = None  # 適切な初期化が必要
            self.emit_log(
                "WARNING", "DatabaseManagerが注入されていません。適切な依存性注入を使用してください。")
        except ImportError as e:
            self.emit_log("ERROR", f"DatabaseManagerの遅延インポートに失敗: {e}")
            self.db_manager = None

    def on_start(self) -> None:
        """ワーカー開始時の初期化"""
        self.logger.info(
            f"Starting database writer with batch size: {self.batch_size}")
        self.logger.info(f"Commit interval: {self.commit_interval} records")

        # データベース接続確認
        try:
            if not self.db_manager.is_connected():
                self.db_manager.connect()
            self.logger.info("Database connection confirmed")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise

    def process_item(self, item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        個別の処理済みデータアイテムを処理

        Args:
            item: 処理済みデータアイテム
                - data_spec: データ仕様
                - transformed_data: 変換済みデータ（Dict[table_name, DataFrame]）
                - records_count: レコード数

        Returns:
            Optional[Dict]: 処理結果（統計用）
        """
        try:
            # キャンセルチェック
            self.cancellation_token.throw_if_cancelled()

            # エラーアイテムの場合はスキップ
            if 'error' in item:
                self.logger.warning(
                    f"Skipping error item: {item.get('error', 'Unknown error')}")
                self.error_count += 1
                return None

            transformed_data = item.get('transformed_data', {})
            data_spec = item.get('data_spec', 'UNKNOWN')

            if not transformed_data:
                self.logger.debug(f"No transformed data for spec: {data_spec}")
                return None

            # テーブル別にデータをバッファに追加
            records_added = 0
            for table_name, df in transformed_data.items():
                if not df.empty:
                    self.table_buffers[table_name].append(df)
                    records_added += len(df)
                    self.table_stats[table_name] += len(df)

            self.records_written += records_added
            self.records_since_commit += records_added

            # バッチサイズに達したらデータベースに書き込み
            if self._should_flush_batch():
                self._flush_buffers()

            # コミット間隔に達したらコミット
            if self.records_since_commit >= self.commit_interval:
                self._commit_transaction()

            # 処理結果を返す
            return {
                'data_spec': data_spec,
                'records_written': records_added,
                'tables_affected': list(transformed_data.keys()),
                'written_at': time.time()
            }

        except Exception as e:
            self.error_count += 1
            self.logger.error(f"Error writing item to database: {e}")

            # エラー時はバッファをクリアして継続
            self._clear_buffers()

            return {
                'error': str(e),
                'error_type': type(e).__name__,
                'data_spec': item.get('data_spec', 'UNKNOWN'),
                'written_at': time.time()
            }

    def _should_flush_batch(self) -> bool:
        """
        バッファをフラッシュすべきかどうかを判定

        Returns:
            bool: フラッシュすべき場合True
        """
        # いずれかのテーブルがバッチサイズに達している場合
        for table_name, buffer in self.table_buffers.items():
            total_records = sum(len(df) for df in buffer)
            if total_records >= self.batch_size:
                return True
        return False

    def _flush_buffers(self) -> None:
        """テーブルバッファをデータベースに書き込み"""
        if not self.table_buffers:
            return

        start_time = time.time()

        for table_name, buffer in self.table_buffers.items():
            if not buffer:
                continue

            try:
                # バッファ内のDataFrameを結合
                combined_df = pd.concat(buffer, ignore_index=True)

                if combined_df.empty:
                    continue

                # データベースに書き込み
                self._write_dataframe_to_table(table_name, combined_df)

                self.logger.debug(
                    f"Flushed {len(combined_df)} records to table '{table_name}'"
                )

            except Exception as e:
                self.logger.error(
                    f"Error flushing buffer for table '{table_name}': {e}")
                self.error_count += 1

        # バッファをクリア
        self._clear_buffers()

        processing_time = time.time() - start_time
        self.batch_count += 1

        self.logger.info(
            f"Batch {self.batch_count}: Flushed buffers in {processing_time:.2f}s"
        )

    def _write_dataframe_to_table(self, table_name: str, df: pd.DataFrame) -> None:
        """
        DataFrameをテーブルに書き込み

        Args:
            table_name: テーブル名
            df: 書き込むDataFrame
        """
        try:
            # 既存のDatabaseManagerのバルク挿入機能を使用
            self.db_manager.bulk_insert(table_name, df)

        except Exception as e:
            self.logger.error(f"Failed to write to table '{table_name}': {e}")
            raise

    def _clear_buffers(self) -> None:
        """すべてのテーブルバッファをクリア"""
        self.table_buffers.clear()

    def _commit_transaction(self) -> None:
        """データベーストランザクションをコミット"""
        try:
            # データベースマネージャーのコミット機能を使用
            if hasattr(self.db_manager, 'commit'):
                self.db_manager.commit()

            self.commit_count += 1
            self.records_since_commit = 0

            self.logger.info(
                f"Committed transaction {self.commit_count}: "
                f"{self.records_written} total records written"
            )

        except Exception as e:
            self.logger.error(f"Failed to commit transaction: {e}")
            # コミット失敗時はロールバックを試行
            try:
                if hasattr(self.db_manager, 'rollback'):
                    self.db_manager.rollback()
                self.logger.info("Transaction rolled back")
            except Exception as rollback_error:
                self.logger.error(f"Rollback also failed: {rollback_error}")
            raise

    def process_loop(self) -> None:
        """メイン処理ループ"""
        while not self.cancellation_token.is_cancelled:
            try:
                # 入力キューからアイテムを取得
                item = self.input_queue.get(timeout=self.queue_timeout)

                if item is None:  # 終了マーカー
                    break

                # アイテムを処理
                result = self.process_item(item)

                self.items_processed += 1

                # 定期的に進捗報告
                if self.items_processed % 100 == 0:
                    table_summary = ", ".join([
                        f"{table}: {count}" for table, count in self.table_stats.items()
                    ])

                    self.report_progress(
                        self.items_processed,
                        -1,
                        f"Written {self.records_written} records to DB ({table_summary})"
                    )

            except Exception as e:
                self.logger.error(f"Error in database writer loop: {e}")
                continue

    def on_cleanup(self) -> None:
        """ワーカー終了時のクリーンアップ"""
        try:
            # 残っているバッファをフラッシュ
            if any(self.table_buffers.values()):
                self.logger.info("Flushing remaining buffers before shutdown")
                self._flush_buffers()

            # 最終コミット
            if self.records_since_commit > 0:
                self.logger.info("Final commit before shutdown")
                self._commit_transaction()

            # 最終統計をログ
            table_summary = "\n".join([
                f"  {table}: {count} records"
                for table, count in sorted(self.table_stats.items())
            ])

            self.logger.info(
                f"Database writer completed:\n"
                f"  Total items processed: {self.items_processed}\n"
                f"  Total records written: {self.records_written}\n"
                f"  Batches processed: {self.batch_count}\n"
                f"  Commits performed: {self.commit_count}\n"
                f"  Errors encountered: {self.error_count}\n"
                f"Table breakdown:\n{table_summary}"
            )

        except Exception as e:
            self.logger.error(f"Error during database writer cleanup: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """統計情報を取得"""
        base_stats = super().get_stats()
        db_stats = {
            "batch_size": self.batch_size,
            "commit_interval": self.commit_interval,
            "records_written": self.records_written,
            "batch_count": self.batch_count,
            "commit_count": self.commit_count,
            "error_count": self.error_count,
            "records_since_commit": self.records_since_commit,
            "table_stats": dict(self.table_stats),
            "avg_records_per_item": (
                self.records_written / self.items_processed
                if self.items_processed > 0 else 0
            ),
            "write_rate": (
                self.records_written / self.processing_time
                if self.processing_time and self.processing_time > 0 else 0
            )
        }

        return {**base_stats, **db_stats}
