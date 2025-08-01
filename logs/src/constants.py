"""
アプリケーション定数定義モジュール
Clean Architecture原則に従った型安全な定数管理
"""

from enum import Enum
from typing import Dict, Any


class DatabaseType(Enum):
    """
    サポートされるデータベース種別の列挙型
    設定ファイルの文字列値と型安全な値の橋渡しを担う
    """
    SQLITE = "SQLite"
    MYSQL = "MySQL"
    POSTGRESQL = "PostgreSQL"
    
    @classmethod
    def from_string(cls, value: str) -> 'DatabaseType':
        """
        文字列からDatabaseType Enumメンバーに変換
        
        Args:
            value: データベース種別文字列（大文字小文字を区別しない）
            
        Returns:
            対応するDatabaseType Enumメンバー
            
        Raises:
            ValueError: 未サポートのデータベース種別の場合
        """
        # ★修正★: 入力値の型安全性チェックを追加
        if not isinstance(value, str):
            raise ValueError(f"文字列が必要ですが、{type(value)}型が渡されました: {value}")
        
        normalized_value = value.strip()
        
        # 大文字小文字を区別しない比較 - ★修正★: 型安全な.valueアクセス
        for db_type in cls:
            if hasattr(db_type, 'value') and db_type.value.lower() == normalized_value.lower():
                return db_type
                
        # フォールバック値の候補
        fallback_mapping = {
            'sqlite3': cls.SQLITE,
            'postgres': cls.POSTGRESQL,
            'postgresql': cls.POSTGRESQL,
            'mysql': cls.MYSQL,
            'mariadb': cls.MYSQL,
        }
        
        normalized_lower = normalized_value.lower()
        if normalized_lower in fallback_mapping:
            return fallback_mapping[normalized_lower]
            
        raise ValueError(f"未サポートのデータベース種別: {value}")
    
    def get_default_port(self) -> int:
        """各データベース種別のデフォルトポート番号を取得"""
        port_mapping = {
            self.SQLITE: 0,  # SQLiteはポートを使用しない
            self.MYSQL: 3306,
            self.POSTGRESQL: 5432,
        }
        return port_mapping[self]


class JVLinkDataSpec(Enum):
    """
    JV-Link データ仕様書に基づくデータ種別定義
    UIでの表示名とJV-Link API仕様の DataSpec ID をマッピング
    """
    RACE_DETAIL = ("RACE", "レース詳細")
    HORSE_MASTER = ("UM", "競走馬マスタ")
    JOCKEY_MASTER = ("KS", "騎手マスタ")
    TRAINER_MASTER = ("CH", "調教師マスタ")
    BREEDER_MASTER = ("BR", "生産者マスタ")
    OWNER_MASTER = ("BN", "馬主マスタ")
    RACE_RESULT = ("SE", "レース結果")
    PAYOUT = ("HR", "払戻")
    ODDS_WIN_PLACE = ("O1", "単勝・複勝オッズ")
    ODDS_EXACT = ("O2", "馬連オッズ")
    ODDS_TRIFECTA = ("O3", "3連単オッズ")
    ODDS_TRIO = ("O4", "3連複オッズ")
    ODDS_WIDE = ("O5", "ワイドオッズ")
    ODDS_QUINELLA_PLACE = ("O6", "馬単オッズ")
    
    def __init__(self, dataspec_id: str, display_name: str):
        self.dataspec_id = dataspec_id
        self.display_name = display_name
    
    @classmethod
    def get_display_names(cls) -> Dict[str, str]:
        """表示名とDataSpec IDのマッピング辞書を取得"""
        return {spec.display_name: spec.dataspec_id for spec in cls}
    
    @classmethod
    def from_display_name(cls, display_name: str) -> 'JVLinkDataSpec':
        """表示名からJVLinkDataSpecを取得"""
        for spec in cls:
            if spec.display_name == display_name:
                return spec
        raise ValueError(f"未知の表示名: {display_name}")


class ApplicationConstants:
    """
    アプリケーション全体で使用される定数値
    """
    # アプリケーション情報
    APP_NAME = "JRA-Data Collector"
    APP_VERSION = "1.0.0"
    
    # JV-Link関連
    JVLINK_SOFTWARE_ID = "DataBricks/1.0.0"
    JVLINK_DEFAULT_TIMEOUT = 30  # 秒
    JVLINK_PROCESS_CHECK_INTERVAL = 0.2  # 秒
    JVLINK_MAX_WAIT_TIME = 5  # 秒
    
    # データベース関連
    DB_CONNECTION_TIMEOUT = 10  # 秒
    DB_BATCH_SIZE = 1000
    DB_COMMIT_INTERVAL = 5000
    
    # UI関連
    UI_ANIMATION_DURATION = 300  # ミリ秒
    UI_NOTIFICATION_DEFAULT_DURATION = 3000  # ミリ秒
    UI_NOTIFICATION_ERROR_DURATION = 5000  # ミリ秒
    
    # ログ関連
    LOG_MAX_FILES = 10
    LOG_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    
    # ネットワーク関連
    NETWORK_RETRY_COUNT = 3
    NETWORK_RETRY_DELAY = 1  # 秒 