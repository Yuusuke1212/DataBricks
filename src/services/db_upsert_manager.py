"""
データベースUPSERT操作専用マネージャー
Clean Architecture原則に従ったアトミックUPSERT実装

dataclassを受け取り、データベース種別に応じた最適なUPSERT操作を提供
"""

import logging
from typing import List, Dict, Any
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from ..exceptions import DatabaseError, DatabaseIntegrityError
from ..services.db_manager import DatabaseManager


logger = logging.getLogger(__name__)


class UpsertManager:
    """
    アトミックUPSERT操作専用マネージャー

    MySQL、PostgreSQL、SQLite対応の効率的なUPSERT操作を提供
    """

    def __init__(self, db_manager: DatabaseManager):
        """
        UpsertManagerを初期化

        Args:
            engine: SQLAlchemyエンジン
            db_type: データベース種別 ('mysql', 'postgresql', 'sqlite')
        """
        self.db_manager = db_manager

    def _get_connection(self):
        return self.db_manager.get_connection()

    def upsert_records(self, table_name: str, records: List[Any],
                       primary_keys: List[str] = None) -> Dict[str, int]:
        """
        アトミックなUPSERT操作でレコードを挿入/更新

        Args:
            table_name: テーブル名
            records: dataclassインスタンスまたは辞書のリスト
            primary_keys: 主キーとなるカラム名のリスト

        Returns:
            処理結果の統計情報 {'processed': 0, 'errors': 0}
        """
        if not records:
            self.logger.warning("挿入するレコードがありません")
            return {'processed': 0, 'errors': 0}

        if not self._get_connection():
            raise DatabaseError("データベース接続が確立されていません", operation="upsert")

        # dataclassを辞書に変換
        record_dicts = self._convert_to_dicts(records)

        if not record_dicts:
            return {'processed': 0, 'errors': 0}

        # データベース種別に応じたUPSERT実行
        try:
            if self.db_manager.db_type == 'mysql':
                return self._mysql_upsert(table_name, record_dicts, primary_keys)
            elif self.db_manager.db_type == 'postgresql':
                return self._postgresql_upsert(table_name, record_dicts, primary_keys)
            elif self.db_manager.db_type == 'sqlite':
                return self._sqlite_upsert(table_name, record_dicts, primary_keys)
            else:
                raise DatabaseError(f"サポートされていないデータベース種別: {self.db_manager.db_type}")

        except Exception as e:
            self.logger.error(f"UPSERT操作中にエラーが発生: {e}")
            raise DatabaseError(f"UPSERT操作に失敗しました: {e}", operation="upsert")

    def _convert_to_dicts(self, records: List[Any]) -> List[Dict[str, Any]]:
        """レコードを辞書形式に変換"""
        record_dicts = []

        for record in records:
            if hasattr(record, '__dataclass_fields__'):
                # dataclassの場合
                record_dict = {
                    field.name: getattr(record, field.name)
                    for field in record.__dataclass_fields__.values()
                }
                record_dicts.append(record_dict)
            elif isinstance(record, dict):
                # 既に辞書の場合
                record_dicts.append(record)
            else:
                self.logger.warning(f"サポートされていないレコード型をスキップ: {type(record)}")
                continue

        return record_dicts

    def _mysql_upsert(self, table_name: str, records: List[Dict[str, Any]],
                      primary_keys: List[str] = None) -> Dict[str, int]:
        """MySQL用のUPSERT操作 (INSERT ... ON DUPLICATE KEY UPDATE)"""
        if not records:
            return {'processed': 0, 'errors': 0}

        columns = list(records[0].keys())
        update_columns = [
            col for col in columns if col not in (primary_keys or [])]

        # SQL構築
        placeholders = ', '.join(['%s'] * len(columns))
        column_list = ', '.join([f"`{col}`" for col in columns])

        if update_columns:
            update_clause = ', '.join(
                [f"`{col}` = VALUES(`{col}`)" for col in update_columns])
            sql = f"""
                INSERT INTO `{table_name}` ({column_list})
                VALUES ({placeholders})
                ON DUPLICATE KEY UPDATE {update_clause}
            """
        else:
            sql = f"""
                INSERT IGNORE INTO `{table_name}` ({column_list})
                VALUES ({placeholders})
            """

        return self._execute_batch_upsert(sql, records, columns, "MySQL")

    def _postgresql_upsert(self, table_name: str, records: List[Dict[str, Any]],
                           primary_keys: List[str] = None) -> Dict[str, int]:
        """PostgreSQL用のUPSERT操作 (INSERT ... ON CONFLICT DO UPDATE)"""
        if not records:
            return {'processed': 0, 'errors': 0}

        columns = list(records[0].keys())

        if not primary_keys:
            primary_keys = ['id']

        update_columns = [col for col in columns if col not in primary_keys]

        # SQL構築
        placeholders = ', '.join(['%s'] * len(columns))
        column_list = ', '.join([f'"{col}"' for col in columns])
        conflict_target = ', '.join([f'"{pk}"' for pk in primary_keys])

        if update_columns:
            update_clause = ', '.join(
                [f'"{col}" = EXCLUDED."{col}"' for col in update_columns])
            sql = f"""
                INSERT INTO "{table_name}" ({column_list})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_target}) DO UPDATE SET {update_clause}
            """
        else:
            sql = f"""
                INSERT INTO "{table_name}" ({column_list})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_target}) DO NOTHING
            """

        return self._execute_batch_upsert(sql, records, columns, "PostgreSQL")

    def _sqlite_upsert(self, table_name: str, records: List[Dict[str, Any]],
                       primary_keys: List[str] = None) -> Dict[str, int]:
        """SQLite用のUPSERT操作 (INSERT ... ON CONFLICT DO UPDATE)"""
        if not records:
            return {'processed': 0, 'errors': 0}

        columns = list(records[0].keys())

        if not primary_keys:
            primary_keys = self._get_sqlite_primary_keys(table_name)

        update_columns = [col for col in columns if col not in primary_keys]

        # SQL構築
        placeholders = ', '.join(['?'] * len(columns))
        column_list = ', '.join([f'"{col}"' for col in columns])

        if update_columns and primary_keys:
            conflict_target = ', '.join([f'"{pk}"' for pk in primary_keys])
            update_clause = ', '.join(
                [f'"{col}" = excluded."{col}"' for col in update_columns])
            sql = f"""
                INSERT INTO "{table_name}" ({column_list})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_target}) DO UPDATE SET {update_clause}
            """
        else:
            sql = f"""
                INSERT OR IGNORE INTO "{table_name}" ({column_list})
                VALUES ({placeholders})
            """

        return self._execute_batch_upsert(sql, records, columns, "SQLite")

    def _execute_batch_upsert(self, sql: str, records: List[Dict[str, Any]],
                              columns: List[str], db_type: str) -> Dict[str, int]:
        """バッチUPSERT操作を実行"""
        batch_data = []
        for record in records:
            row_data = [record.get(col) for col in columns]
            batch_data.append(row_data)

        try:
            with self._get_connection().begin() as conn:
                result = conn.execute(text(sql), batch_data)
                affected_rows = result.rowcount if hasattr(
                    result, 'rowcount') else len(batch_data)

                self.logger.info(f"{db_type} UPSERT操作完了: {affected_rows}行処理")

                return {
                    'processed': affected_rows,
                    'errors': max(0, len(batch_data) - affected_rows)
                }

        except IntegrityError as e:
            self.logger.error(f"データ整合性エラー: {e}")
            raise DatabaseIntegrityError(f"データ整合性エラー: {e}", operation="upsert")
        except Exception as e:
            self.logger.error(f"UPSERT実行エラー: {e}")
            raise DatabaseError(f"UPSERT実行に失敗しました: {e}", operation="upsert")

    def _get_sqlite_primary_keys(self, table_name: str) -> List[str]:
        """SQLiteテーブルの主キーカラムを取得"""
        try:
            with self._get_connection().connect() as conn:
                result = conn.execute(
                    text(f"PRAGMA table_info('{table_name}')"))
                primary_keys = []
                for row in result:
                    if row[5]:  # pk フィールドが1の場合
                        primary_keys.append(row[1])  # column name
                return primary_keys or ['rowid']
        except Exception as e:
            self.logger.warning(f"主キー情報の取得に失敗: {e}")
            return ['rowid']

    # 特定のテーブル用の便利メソッド
    def upsert_race_details(self, race_details: List[Any]) -> Dict[str, int]:
        """レース詳細情報のUPSERT操作"""
        primary_keys = ['kaisai_year', 'keibajo_code',
                        'kaisai_kaiji', 'kaisai_nichiji', 'race_number']
        return self.upsert_records('races', race_details, primary_keys)

    def upsert_horse_race_info(self, horse_race_infos: List[Any]) -> Dict[str, int]:
        """馬毎レース情報のUPSERT操作"""
        primary_keys = ['kaisai_year', 'keibajo_code', 'kaisai_kaiji', 'kaisai_nichiji',
                        'race_number', 'umaban']
        return self.upsert_records('race_entries', horse_race_infos, primary_keys)


# ファクトリ関数
def create_upsert_manager(db_manager: DatabaseManager) -> UpsertManager:
    """
    UpsertManagerインスタンスを作成

    Args:
        engine: SQLAlchemyエンジン
        db_type: データベース種別

    Returns:
        UpsertManagerインスタンス
    """
    return UpsertManager(db_manager)
