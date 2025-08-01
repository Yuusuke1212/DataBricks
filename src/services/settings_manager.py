"""
設定管理モジュール - configparserベースの実装
Clean Architecture原則に従った近代的な設定管理を提供
"""

import configparser
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# カスタム定数とEnumのインポート
from ..constants import DatabaseType

# PyQtシグナル機構のサポート
try:
    from PyQt5.QtCore import QObject, pyqtSignal as Signal
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False
    QObject = object
    Signal = lambda *args: None


class ConfigManager(QObject):
    """
    アプリケーション設定を管理するクラス

    - configparserを使用したINI形式での設定管理
    - シングルトンパターンでアプリケーション全体で一意のインスタンスを保証
    - PyQtシグナルによる設定変更の通知機能
    """

    # シグナル定義
    database_config_updated = Signal(dict)
    settings_saved = Signal()

    def __init__(self, config_filename: str = "settings.ini", parent=None):
        """
        ConfigManagerを初期化

        Args:
            config_filename: 設定ファイル名（デフォルト: settings.ini）
            parent: 親QObject（オプション）
        """
        if QT_AVAILABLE:
            super().__init__(parent)

        self.logger = logging.getLogger(__name__)

        # パス解決の堅牢化
        try:
            current_dir = Path(__file__).parent
            project_root = current_dir.parent.parent
            self.config_path = project_root / config_filename
            self.config_path = self.config_path.resolve()

            self.logger.info(f"設定ファイルパス: {self.config_path}")

        except Exception as e:
            self.logger.error(f"パス解決エラー: {e}")
            # フォールバック
            self.config_path = Path(config_filename).resolve()

        self.config = configparser.ConfigParser(interpolation=None)
        self._load_config()

    def _load_config(self) -> None:
        """設定ファイルを読み込み、存在しない場合はデフォルト設定で初期化"""
        try:
            if self.config_path.exists():
                self.config.read(self.config_path, encoding='utf-8')
                self.logger.info(
                    f"設定ファイル読み込み成功: {len(self.config.sections())} セクション")
            else:
                self.logger.warning("設定ファイルが見つかりません。デフォルト設定で初期化します。")
                self._create_default_config()
                self.save()

        except Exception as e:
            self.logger.error(f"設定ファイル読み込みエラー: {e}")
            self._create_default_config()
            self.save()

    def _create_default_config(self) -> None:
        """デフォルト設定を作成"""
        # Database section
        self.config.add_section('Database')
        self.config.set('Database', 'type', 'SQLite')
        self.config.set('Database', 'host', 'localhost')
        self.config.set('Database', 'port', '5432')
        self.config.set('Database', 'username', 'postgres')
        self.config.set('Database', 'password', '')
        self.config.set('Database', 'db_name', 'jra_data.db')

        # DataSync section - アプリケーション管理の設定（保持）
        self.config.add_section('DataSync')
        self.config.set('DataSync', 'last_file_timestamp', '')
        self.config.set('DataSync', 'auto_sync_enabled', 'true')
        self.config.set('DataSync', 'sync_interval_minutes', '5')

        # Paths section
        self.config.add_section('Paths')
        self.config.set('Paths', 'jvlink_exe_path', 'JV-Link/JV-Link.exe')
        self.config.set('Paths', 'data_export_path', 'exports/')
        self.config.set('Paths', 'log_file_path',
                        'logs/jra_data_collector.log')

        # Processing section
        self.config.add_section('Processing')
        self.config.set('Processing', 'max_concurrent_workers', '4')
        self.config.set('Processing', 'batch_size', '1000')
        self.config.set('Processing', 'enable_compression', 'false')

    def save(self) -> None:
        """設定をファイルに保存し、保存完了をシグナルで通知"""
        try:
            # ディレクトリが存在しない場合は作成
            self.config_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_path, 'w', encoding='utf-8') as f:
                self.config.write(f)

            self.logger.info(f"設定ファイル保存成功: {self.config_path}")

            # 設定保存完了をシグナルで通知
            if QT_AVAILABLE:
                self.settings_saved.emit()

        except Exception as e:
            self.logger.error(f"設定ファイル保存エラー: {e}")
            raise

    # Database Configuration
    def get_db_config(self) -> Dict[str, Any]:
        """データベース設定を取得（型安全な DatabaseType Enum を使用）"""
        try:
            # 文字列としてDBタイプを読み込み
            db_type_str = self.config.get('Database', 'type', fallback='SQLite')

            # ★重要★: 型安全な文字列からEnumへの変換処理
            try:
                # 値が確実に文字列であることを保証
                if not isinstance(db_type_str, str):
                    self.logger.warning(f"データベース種別が文字列ではありません: {type(db_type_str)} = {db_type_str}. 'SQLite'を使用します。")
                    db_type_str = 'SQLite'

                db_type = DatabaseType.from_string(db_type_str)
                self.logger.debug(f"データベース種別変換成功: '{db_type_str}' → {db_type}")
            except (ValueError, AttributeError, TypeError) as e:
                self.logger.warning(f"設定ファイルに不正なDBタイプ '{db_type_str}' が指定されています。SQLiteにフォールバックします。エラー: {e}")
                db_type = DatabaseType.SQLITE
            except Exception as e:
                self.logger.error(f"予期しないエラーが発生しました: {e}. SQLiteにフォールバックします。")
                db_type = DatabaseType.SQLITE

            return {
                'type': db_type,  # DatabaseType Enumとして返す
                'host': self.config.get('Database', 'host', fallback='localhost'),
                'port': self.config.getint('Database', 'port', fallback=5432),
                'username': self.config.get('Database', 'username', fallback='postgres'),
                'password': self.config.get('Database', 'password', fallback=''),
                'db_name': self.config.get('Database', 'db_name', fallback='jra_data.db'),
            }
        except Exception as e:
            self.logger.error(f"データベース設定取得エラー: {e}")
            # フォールバック時もDatabaseType Enumを使用
            return {'type': DatabaseType.SQLITE, 'db_name': 'jra_data.db'}

    def update_db_config(self, **kwargs) -> None:
        """データベース設定を更新し、変更をシグナルで通知"""
        if not self.config.has_section('Database'):
            self.config.add_section('Database')

        for key, value in kwargs.items():
            self.config.set('Database', key, str(value))

        self.save()
        self.logger.info("データベース設定を更新しました")

        # 更新された設定をシグナルで通知
        if QT_AVAILABLE:
            updated_config = self.get_db_config()
            self.database_config_updated.emit(updated_config)

    # LastFileTimestamp Management
    def get_last_file_timestamp(self) -> Optional[str]:
        """最終ファイルタイムスタンプを取得"""
        try:
            timestamp = self.config.get(
                'DataSync', 'last_file_timestamp', fallback='')
            return timestamp if timestamp else None
        except Exception as e:
            self.logger.error(f"最終タイムスタンプ取得エラー: {e}")
            return None

    def update_last_file_timestamp(self, timestamp: str) -> None:
        """
        最終ファイルタイムスタンプを更新・保存
        データ取得処理が正常完了した際に呼び出される
        """
        try:
            if not self.config.has_section('DataSync'):
                self.config.add_section('DataSync')

            self.config.set('DataSync', 'last_file_timestamp', timestamp)
            self.save()

            self.logger.info(f"最終ファイルタイムスタンプを更新: {timestamp}")

        except Exception as e:
            self.logger.error(f"最終タイムスタンプ更新エラー: {e}")
            raise

    # Processing Configuration
    def get_processing_config(self) -> Dict[str, Any]:
        """処理設定を取得"""
        try:
            return {
                'max_concurrent_workers': self.config.getint('Processing', 'max_concurrent_workers', fallback=4),
                'batch_size': self.config.getint('Processing', 'batch_size', fallback=1000),
                'enable_compression': self.config.getboolean('Processing', 'enable_compression', fallback=False),
            }
        except Exception as e:
            self.logger.error(f"処理設定取得エラー: {e}")
            return {'max_concurrent_workers': 4, 'batch_size': 1000, 'enable_compression': False}

    # Path Configuration
    def get_jvlink_exe_path(self) -> str:
        """JV-Link実行ファイルパスを取得"""
        try:
            relative_path = self.config.get(
                'Paths', 'jvlink_exe_path', fallback='JV-Link/JV-Link.exe')
            # プロジェクトルートからの相対パスを絶対パスに変換
            project_root = self.config_path.parent
            return str((project_root / relative_path).resolve())
        except Exception as e:
            self.logger.error(f"JV-Linkパス取得エラー: {e}")
            return str(Path('JV-Link/JV-Link.exe').resolve())

    # Legacy Compatibility Methods (既存コードとの互換性のため)
    def get_all(self) -> Dict[str, Any]:
        """
        すべての設定を辞書形式で取得（既存コードとの互換性のため）
        """
        return {
            'database': self.get_db_config(),
            'processing': self.get_processing_config(),
        }

    def get_all_settings(self) -> Dict[str, Any]:
        """get_allのエイリアス"""
        return self.get_all()

    # 新しい API も提供
    def get_section(self, section_name: str) -> Dict[str, str]:
        """指定されたセクションのすべての設定を取得"""
        try:
            if self.config.has_section(section_name):
                return dict(self.config.items(section_name))
            else:
                self.logger.warning(f"セクション '{section_name}' が存在しません")
                return {}
        except Exception as e:
            self.logger.error(f"セクション取得エラー: {e}")
            return {}

    def set_value(self, section: str, key: str, value: str) -> None:
        """設定値を設定"""
        try:
            if not self.config.has_section(section):
                self.config.add_section(section)

            self.config.set(section, key, value)
            self.save()

        except Exception as e:
            self.logger.error(f"設定値設定エラー: {e}")
            raise

    # ETLルール管理機能（旧SettingsManagerとの互換性のため）
    def load_etl_rules(self) -> Dict[str, Any]:
        """
        保存されているすべてのETLルールを読み込む

        Returns:
            ETLルールの辞書
        """
        try:
            if self.config.has_section('ETLRules'):
                rules = {}
                for key, value in self.config.items('ETLRules'):
                    try:
                        # JSON形式で保存されたルールをデコード
                        import json
                        rules[key] = json.loads(value)
                    except json.JSONDecodeError as e:
                        self.logger.warning(f"ETLルール '{key}' のデコードに失敗: {e}")
                        continue

                return rules
            else:
                return {}
        except Exception as e:
            self.logger.error(f"ETLルール読み込みエラー: {e}")
            return {}

    def save_etl_rule(self, rule_name: str, rule_data: Dict[str, Any]) -> None:
        """
        指定された名前でETLルールを保存または更新する

        Args:
            rule_name: ルール名
            rule_data: ルールデータの辞書
        """
        try:
            if not self.config.has_section('ETLRules'):
                self.config.add_section('ETLRules')

            # ルールデータをJSON形式で保存
            import json
            rule_json = json.dumps(rule_data, ensure_ascii=False)
            self.config.set('ETLRules', rule_name, rule_json)

            self.save()
            self.logger.info(f"ETLルール '{rule_name}' を保存しました")

        except Exception as e:
            self.logger.error(f"ETLルール保存エラー: {e}")
            raise

    def delete_etl_rule(self, rule_name: str) -> None:
        """
        指定された名前のETLルールを削除する

        Args:
            rule_name: 削除するルール名
        """
        try:
            if self.config.has_section('ETLRules') and self.config.has_option('ETLRules', rule_name):
                self.config.remove_option('ETLRules', rule_name)
                self.save()
                self.logger.info(f"ETLルール '{rule_name}' を削除しました")
            else:
                self.logger.warning(f"ETLルール '{rule_name}' が見つかりません")

        except Exception as e:
            self.logger.error(f"ETLルール削除エラー: {e}")
            raise

# === Database Profile Management (複数DB設定サポート) ===

    def get_database_profiles(self) -> Dict[str, Dict[str, Any]]:
        """
        保存されているすべてのデータベースプロファイルを取得
        
        Returns:
            プロファイル名をキーとするデータベース設定の辞書
        """
        try:
            profiles = {}

            # メインのDatabase設定も含める
            if self.config.has_section('Database'):
                profiles['default'] = self.get_db_config()

            # 追加プロファイルを検索
            for section_name in self.config.sections():
                if section_name.startswith('Database_'):
                    profile_name = section_name[9:]  # "Database_"を除去
                    profiles[profile_name] = self._get_profile_config(section_name)

            self.logger.info(f"データベースプロファイル {len(profiles)} 個を取得しました")
            return profiles

        except Exception as e:
            self.logger.error(f"データベースプロファイル取得エラー: {e}")
            return {}

    def _get_profile_config(self, section_name: str) -> Dict[str, Any]:
        """
        指定されたセクションからデータベース設定を取得
        
        Args:
            section_name: 設定セクション名
            
        Returns:
            データベース設定の辞書
        """
        try:
            return {
                'type': self.config.get(section_name, 'type', fallback='SQLite'),
                'host': self.config.get(section_name, 'host', fallback='localhost'),
                'port': self.config.getint(section_name, 'port', fallback=5432),
                'username': self.config.get(section_name, 'username', fallback='postgres'),
                'password': self.config.get(section_name, 'password', fallback=''),
                'db_name': self.config.get(section_name, 'db_name', fallback='jra_data.db'),
            }
        except Exception as e:
            self.logger.error(f"プロファイル設定取得エラー ({section_name}): {e}")
            return {'type': 'SQLite', 'db_name': 'jra_data.db'}

    def save_database_profile(self, profile_name: str, db_config: Dict[str, Any]) -> None:
        """
        データベースプロファイルを保存
        
        Args:
            profile_name: プロファイル名
            db_config: データベース設定
        """
        try:
            if profile_name == 'default':
                section_name = 'Database'
            else:
                section_name = f'Database_{profile_name}'

            if not self.config.has_section(section_name):
                self.config.add_section(section_name)

            for key, value in db_config.items():
                # ★修正★: DatabaseType Enumの場合は.valueを使用
                if isinstance(value, DatabaseType):
                    self.config.set(section_name, key, value.value)
                else:
                    self.config.set(section_name, key, str(value))

            self.save()
            self.logger.info(f"データベースプロファイル '{profile_name}' を保存しました")

            # プロファイルが更新された場合の通知
            if QT_AVAILABLE:
                self.database_config_updated.emit(db_config)

        except Exception as e:
            self.logger.error(f"データベースプロファイル保存エラー: {e}")
            raise

    def delete_database_profile(self, profile_name: str) -> None:
        """
        データベースプロファイルを削除
        
        Args:
            profile_name: 削除するプロファイル名
        """
        try:
            if profile_name == 'default':
                raise ValueError("デフォルトプロファイルは削除できません")

            section_name = f'Database_{profile_name}'
            if self.config.has_section(section_name):
                self.config.remove_section(section_name)
                self.save()
                self.logger.info(f"データベースプロファイル '{profile_name}' を削除しました")
            else:
                self.logger.warning(f"プロファイル '{profile_name}' が見つかりません")

        except Exception as e:
            self.logger.error(f"データベースプロファイル削除エラー: {e}")
            raise

    def get_active_database_profile(self) -> str:
        """
        現在アクティブなデータベースプロファイル名を取得
        
        Returns:
            アクティブなプロファイル名
        """
        try:
            return self.config.get('Application', 'active_database_profile', fallback='default')
        except Exception as e:
            self.logger.error(f"アクティブプロファイル取得エラー: {e}")
            return 'default'

    def set_active_database_profile(self, profile_name: str) -> None:
        """
        アクティブなデータベースプロファイルを設定
        
        Args:
            profile_name: アクティブにするプロファイル名
        """
        try:
            if not self.config.has_section('Application'):
                self.config.add_section('Application')

            self.config.set('Application', 'active_database_profile', profile_name)
            self.save()

            self.logger.info(f"アクティブデータベースプロファイルを '{profile_name}' に設定しました")

            # アクティブプロファイル変更の通知
            if QT_AVAILABLE:
                active_config = self.get_database_profile_config(profile_name)
                self.database_config_updated.emit(active_config)

        except Exception as e:
            self.logger.error(f"アクティブプロファイル設定エラー: {e}")
            raise

    def get_database_profile_config(self, profile_name: str) -> Dict[str, Any]:
        """
        指定されたプロファイルのデータベース設定を取得
        
        Args:
            profile_name: プロファイル名
            
        Returns:
            データベース設定の辞書
        """
        try:
            if profile_name == 'default':
                return self.get_db_config()
            else:
                section_name = f'Database_{profile_name}'
                if self.config.has_section(section_name):
                    return self._get_profile_config(section_name)
                else:
                    self.logger.warning(f"プロファイル '{profile_name}' が見つかりません。デフォルトを返します")
                    return self.get_db_config()

        except Exception as e:
            self.logger.error(f"プロファイル設定取得エラー ({profile_name}): {e}")
            return self.get_db_config()


# Singleton pattern for global access
_config_manager_instance: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """ConfigManagerのシングルトンインスタンスを取得"""
    global _config_manager_instance

    if _config_manager_instance is None:
        _config_manager_instance = ConfigManager()

    return _config_manager_instance


# 既存コードとの互換性のため SettingsManager エイリアスを提供
SettingsManager = ConfigManager
