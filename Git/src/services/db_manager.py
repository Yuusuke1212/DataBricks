import os
import logging
import pandas as pd
from typing import Dict, List, Any, Optional
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError, IntegrityError

from ..services.workers.signals import LoggerMixin
from ..exceptions import DatabaseError, DatabaseConnectionError, DatabaseIntegrityError

# 修正点3: データベース固有のエラーを捕捉するためにインポート
try:
    import psycopg2
    PSYCOPG2_AVAILABLE = True
except ImportError:
    psycopg2 = None
    PSYCOPG2_AVAILABLE = False

try:
    import mysql.connector
    MYSQL_CONNECTOR_AVAILABLE = True
except ImportError:
    mysql = None
    MYSQL_CONNECTOR_AVAILABLE = False


class DatabaseManager(LoggerMixin):
    """
    データベースエンジン（SQLite, MySQL, PostgreSQL）の違いを吸収し、
    統一されたインターフェースでデータの読み書きを提供する。

    Clean Architecture原則に従った最適化実装
    アトミックUPSERT操作によるパフォーマンス向上
    """

    def __init__(self, settings_manager):
        """コンストラクタ"""
        LoggerMixin.__init__(self, "データベース管理", "DatabaseManager")

        self.settings_manager = settings_manager
        self.engine = None
        self.Session = None
        self._db_type = None
        self._db_name = None

        self.emit_log("INFO", "DatabaseManagerを初期化しています...")

        # データベース接続を試行（失敗してもアプリケーション起動は継続）
        try:
            self.connect()
        except Exception as e:
            self.emit_log(
                "ERROR", f"データベース接続に失敗しました。アプリケーションはオフラインモードで起動します: {e}")
            self.engine = None
            self.Session = None
            self._db_type = "offline"
            self._db_name = "未接続"

        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def test_connection(self, db_config: dict, show_create_dialog: bool = True) -> tuple[bool, str]:
        """
        データベース接続をテストします

        Args:
            db_config: データベース設定
            show_create_dialog: データベース不存在時に作成確認ダイアログを表示するか

        Returns:
            (接続成功フラグ, メッセージ)
        """
        db_type = db_config.get('type', 'SQLite')

        try:
            if db_type == "SQLite":
                db_path = db_config.get('path', 'test.db')
                test_engine = create_engine(f'sqlite:///{db_path}')

            elif db_type == "MySQL":
                # MySQL: データベース存在確認と自動作成
                return self._test_mysql_with_creation(db_config, show_create_dialog)

            elif db_type == "PostgreSQL":
                # PostgreSQL: データベース存在確認と自動作成
                return self._test_postgresql_with_creation(db_config, show_create_dialog)

            else:
                return False, f"未サポートのデータベース種別: {db_type}"

            # SQLiteの場合の接続テスト実行
            with test_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()

            return True, f"{db_type} データベースへの接続に成功しました"

        except Exception as e:
            logging.error(f"{db_type} 接続テスト中にエラーが発生しました: {e}")
            return False, f"接続エラー: {str(e)}"

    def _test_mysql_with_creation(self, db_config: dict, show_create_dialog: bool) -> tuple[bool, str]:
        """
        MySQL接続テスト（データベース自動作成対応）
        Unicode対策強化版
        """
        import urllib.parse

        host = db_config.get('host', 'localhost')
        try:
            port = int(db_config.get('port', 3306)
                       ) if db_config.get('port') else 3306
        except (ValueError, TypeError):
            port = 3306
        username = db_config.get('username', 'root')
        password = db_config.get('password', '')
        database = db_config.get(
            'database') or db_config.get('db_name', 'test')

        # 強化されたUnicodeエンコーディング処理
        try:
            # 文字列の安全な正規化
            username = str(username).strip() if username else 'root'
            password = str(password).strip() if password else ''
            database = str(database).strip() if database else 'test'
            host = str(host).strip() if host else 'localhost'

            # UTF-8エンコーディングの確認と修正
            username = username.encode(
                'utf-8', errors='replace').decode('utf-8')
            password = password.encode(
                'utf-8', errors='replace').decode('utf-8')
            database = database.encode(
                'utf-8', errors='replace').decode('utf-8')

            # URLエンコーディング（safe文字を明示的に指定）
            username_encoded = urllib.parse.quote(
                username, safe='', encoding='utf-8')
            password_encoded = urllib.parse.quote(
                password, safe='', encoding='utf-8')
            database_encoded = urllib.parse.quote(
                database, safe='', encoding='utf-8')

            self.emit_log(
                "DEBUG", f"MySQL接続パラメータ: host={host}, port={port}, user={username}, db={database}")

        except Exception as encoding_error:
            error_msg = f"MySQL接続パラメータのエンコーディングエラー: {encoding_error}"
            self.emit_log("ERROR", error_msg)
            return False, error_msg

        # 複数の接続方法を試行
        connection_attempts = [
            # 方法1: 標準接続（強化されたエンコーディング）
            (
                f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
                f'?charset=utf8mb4&collation=utf8mb4_unicode_ci&use_unicode=1&connect_timeout=30'
            ),
            # 方法2: シンプルな設定
            (
                f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
                f'?charset=utf8mb4&use_unicode=1'
            ),
            # 方法3: 最小パラメータ
            (
                f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
            )
        ]

        last_error = None

        for attempt_num, connection_string in enumerate(connection_attempts, 1):
            try:
                self.emit_log(
                    "DEBUG", f"MySQL接続試行 {attempt_num}: {connection_string.replace(password_encoded, '***')}")

                # SQLAlchemy接続エンジンの作成
                engine_params = {
                    'echo': False,
                    'pool_pre_ping': True,
                    'pool_recycle': 3600,
                    'connect_args': {
                        'charset': 'utf8mb4',
                        'use_unicode': True,
                        'connect_timeout': 30
                    }
                }

                test_engine = create_engine(connection_string, **engine_params)

                # 接続テスト実行
                with test_engine.connect() as conn:
                    result = conn.execute(text("SELECT VERSION()"))
                    version_info = result.fetchone()[0]

                self.emit_log(
                    "INFO", f"MySQL接続成功（試行{attempt_num}）: {version_info}")
                return True, f"MySQL データベース '{database}' への接続に成功しました"

            except UnicodeDecodeError as unicode_error:
                error_msg = f"MySQL接続試行{attempt_num}でUnicodeエラー: {unicode_error}"
                self.emit_log("WARNING", error_msg)
                last_error = unicode_error
                continue

            except Exception as e:
                error_msg = f"MySQL接続試行{attempt_num}で一般エラー: {e}"
                self.emit_log("WARNING", error_msg)
                last_error = e

                # データベース存在チェック
                error_str = str(e).lower()
                if 'unknown database' in error_str or ('database' in error_str and 'unknown' in error_str):
                    # データベースが存在しない場合の処理
                    if show_create_dialog:
                        if self._show_database_create_dialog(database, "MySQL"):
                            return self._create_mysql_database_safe(host, port, username, password, database)
                        else:
                            return False, f"データベース '{database}' が存在しません"
                    else:
                        return self._create_mysql_database_safe(host, port, username, password, database)
                continue

        # すべての接続試行が失敗した場合
        final_error_msg = f"MySQL接続の全ての試行が失敗しました。最後のエラー: {last_error}"
        self.emit_log("ERROR", final_error_msg)
        return False, final_error_msg

    def _test_postgresql_with_creation(self, db_config: dict, show_create_dialog: bool) -> tuple[bool, str]:
        """
        PostgreSQL接続テスト（データベース自動作成対応）
        Unicodeエラー対策強化版
        """
        import urllib.parse
        import platform

        host = db_config.get('host', 'localhost')
        try:
            port = int(db_config.get('port', 5432)
                       ) if db_config.get('port') else 5432
        except (ValueError, TypeError):
            port = 5432
        username = db_config.get('username', 'postgres')
        password = db_config.get('password', '')
        database = db_config.get(
            'database') or db_config.get('db_name', 'test')

        # 強化されたUnicodeエンコーディング処理
        try:
            # 文字列の安全な正規化
            username = str(username).strip() if username else 'postgres'
            password = str(password).strip() if password else ''
            database = str(database).strip() if database else 'test'
            host = str(host).strip() if host else 'localhost'

            # UTF-8エンコーディングの確認と修正
            username = username.encode(
                'utf-8', errors='replace').decode('utf-8')
            password = password.encode(
                'utf-8', errors='replace').decode('utf-8')
            database = database.encode(
                'utf-8', errors='replace').decode('utf-8')

            # URLエンコーディング（safe文字を明示的に指定）
            username_encoded = urllib.parse.quote(
                username, safe='', encoding='utf-8')
            password_encoded = urllib.parse.quote(
                password, safe='', encoding='utf-8')
            database_encoded = urllib.parse.quote(
                database, safe='', encoding='utf-8')

            self.emit_log(
                "DEBUG", f"PostgreSQL接続パラメータ: host={host}, port={port}, user={username}, db={database}")

        except Exception as encoding_error:
            error_msg = f"PostgreSQL接続パラメータのエンコーディングエラー: {encoding_error}"
            self.emit_log("ERROR", error_msg)
            return False, error_msg

        # Windows環境でのTCP接続調整
        if platform.system() == 'Windows':
            if host in ['localhost', '127.0.0.1']:
                host = '127.0.0.1'

        # 複数の接続方法を試行
        connection_attempts = [
            # 方法1: 標準接続（強化されたエンコーディング）
            (
                f'postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
                f'?client_encoding=utf8&connect_timeout=30&application_name=JRA-Data-Collector'
            ),
            # 方法2: Unicodeエスケープなし
            (
                f'postgresql://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
                f'?sslmode=prefer&connect_timeout=30'
            ),
            # 方法3: 最小パラメータ
            (
                f'postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
            )
        ]

        last_error = None

        for attempt_num, connection_string in enumerate(connection_attempts, 1):
            try:
                self.emit_log(
                    "DEBUG", f"PostgreSQL接続試行 {attempt_num}: {connection_string.replace(password_encoded, '***')}")

                # SQLAlchemy接続エンジンの作成
                engine_params = {
                    'echo': False,
                    'pool_pre_ping': True,
                    'pool_recycle': 3600,
                    'connect_args': {
                        'client_encoding': 'utf8',
                        'application_name': 'JRA-Data-Collector',
                        'connect_timeout': 30
                    }
                }

                test_engine = create_engine(connection_string, **engine_params)

                # 接続テスト実行
                with test_engine.connect() as conn:
                    result = conn.execute(text("SELECT version()"))
                    version_info = result.fetchone()[0]

                self.emit_log(
                    "INFO", f"PostgreSQL接続成功（試行{attempt_num}）: {version_info[:100]}...")
                return True, f"PostgreSQL データベース '{database}' への接続に成功しました"

            except UnicodeDecodeError as unicode_error:
                error_msg = f"PostgreSQL接続試行{attempt_num}でUnicodeエラー: {unicode_error}"
                self.emit_log("WARNING", error_msg)
                last_error = unicode_error
                continue

            except Exception as e:
                error_msg = f"PostgreSQL接続試行{attempt_num}で一般エラー: {e}"
                self.emit_log("WARNING", error_msg)
                last_error = e

                # データベース存在チェック
                error_str = str(e).lower()
                if 'does not exist' in error_str or 'database' in error_str and 'not exist' in error_str:
                    # データベースが存在しない場合の処理
                    if show_create_dialog:
                        if self._show_database_create_dialog(database, "PostgreSQL"):
                            return self._create_postgresql_database_safe(host, port, username, password, database)
                        else:
                            return False, f"データベース '{database}' が存在しません"
                    else:
                        return self._create_postgresql_database_safe(host, port, username, password, database)
                continue

        # すべての接続試行が失敗した場合
        final_error_msg = f"PostgreSQL接続の全ての試行が失敗しました。最後のエラー: {last_error}"
        self.emit_log("ERROR", final_error_msg)
        return False, final_error_msg

    def _show_database_create_dialog(self, database_name: str, db_type: str) -> bool:
        """
        データベース作成確認ダイアログを表示

        Returns:
            bool: ユーザーがOKを選択した場合True
        """
        try:
            from PySide6.QtWidgets import QMessageBox, QApplication

            # アプリケーションインスタンスの確認
            app = QApplication.instance()
            if app is None:
                # GUI環境でない場合は自動作成
                self.emit_log(
                    "INFO", f"GUI環境でないため、データベース '{database_name}' を自動作成します")
                return True

            # ダイアログの表示
            msg_box = QMessageBox()
            msg_box.setWindowTitle("データベース作成確認")
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setText(
                f"データベース '{database_name}' が存在しません。\n\n"
                f"新しく作成しますか？\n\n"
                f"データベース種別: {db_type}"
            )
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            msg_box.setDefaultButton(QMessageBox.StandardButton.Ok)

            # ボタンのテキストを日本語化
            ok_button = msg_box.button(QMessageBox.StandardButton.Ok)
            cancel_button = msg_box.button(QMessageBox.StandardButton.Cancel)
            if ok_button:
                ok_button.setText("作成")
            if cancel_button:
                cancel_button.setText("キャンセル")

            result = msg_box.exec()
            return result == QMessageBox.StandardButton.Ok

        except Exception as e:
            self.emit_log("ERROR", f"ダイアログ表示エラー: {e}")
            # エラーの場合は自動作成
            return True

    def _create_mysql_database_safe(self, host: str, port: int, username: str, password: str, database: str) -> tuple[bool, str]:
        """
        MySQLデータベースを安全に作成（Unicode対応強化版）
        """
        import urllib.parse

        try:
            # 文字列の安全な正規化
            username = str(username).encode(
                'utf-8', errors='replace').decode('utf-8')
            password = str(password).encode(
                'utf-8', errors='replace').decode('utf-8')
            database = str(database).encode(
                'utf-8', errors='replace').decode('utf-8')

            # URLエンコーディング
            username_encoded = urllib.parse.quote(
                username, safe='', encoding='utf-8')
            password_encoded = urllib.parse.quote(
                password, safe='', encoding='utf-8')

            # データベース指定なしでMySQL接続の複数試行
            connection_attempts = [
                f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}?charset=utf8mb4&use_unicode=1&connect_timeout=30',
                f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}?charset=utf8mb4&use_unicode=1',
                f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}'
            ]

            for attempt_num, connection_string in enumerate(connection_attempts, 1):
                try:
                    self.emit_log("DEBUG", f"MySQLデータベース作成試行 {attempt_num}")

                    admin_engine = create_engine(connection_string, echo=False)

                    with admin_engine.connect() as conn:
                        # データベース作成（識別子をバッククォート）
                        safe_db_name = database.replace(
                            '`', '``')  # バッククォートエスケープ
                        conn.execute(text(
                            f"CREATE DATABASE `{safe_db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
                        conn.commit()

                    self.emit_log(
                        "INFO", f"MySQLデータベース '{database}' の作成に成功しました")

                    # 作成したデータベースに接続テスト
                    database_encoded = urllib.parse.quote(
                        database, safe='', encoding='utf-8')
                    test_connection_string = f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}?charset=utf8mb4&use_unicode=1&connect_timeout=30'

                    test_engine = create_engine(
                        test_connection_string, echo=False)
                    with test_engine.connect() as conn:
                        result = conn.execute(text("SELECT VERSION()"))
                        result.fetchone()

                    return True, f"MySQLデータベース '{database}' を作成し、接続に成功しました"

                except Exception as e:
                    self.emit_log(
                        "WARNING", f"MySQLデータベース作成試行{attempt_num}でエラー: {e}")
                    if attempt_num == len(connection_attempts):
                        raise
                    continue

        except Exception as e:
            error_msg = f"MySQLデータベース '{database}' の作成に失敗しました: {str(e)}"
            self.emit_log("ERROR", error_msg)
            return False, error_msg

    def _create_postgresql_database_safe(self, host: str, port: int, username: str, password: str, database: str) -> tuple[bool, str]:
        """
        PostgreSQLデータベースを安全に作成（Unicode対応強化版）
        """
        import urllib.parse
        import platform

        try:
            # 文字列の安全な正規化
            username = str(username).encode(
                'utf-8', errors='replace').decode('utf-8')
            password = str(password).encode(
                'utf-8', errors='replace').decode('utf-8')
            database = str(database).encode(
                'utf-8', errors='replace').decode('utf-8')

            # URLエンコーディング
            username_encoded = urllib.parse.quote(
                username, safe='', encoding='utf-8')
            password_encoded = urllib.parse.quote(
                password, safe='', encoding='utf-8')

            # Windows環境でのTCP接続調整
            if platform.system() == 'Windows':
                if host in ['localhost', '127.0.0.1']:
                    host = '127.0.0.1'

            # postgres データベースに接続（デフォルトで存在）
            connection_attempts = [
                f'postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/postgres?client_encoding=utf8&connect_timeout=30',
                f'postgresql://{username_encoded}:{password_encoded}@{host}:{port}/postgres?sslmode=prefer&connect_timeout=30',
                f'postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/postgres'
            ]

            for attempt_num, connection_string in enumerate(connection_attempts, 1):
                try:
                    self.emit_log(
                        "DEBUG", f"PostgreSQLデータベース作成試行 {attempt_num}")

                    admin_engine = create_engine(connection_string, echo=False)

                    # PostgreSQLでは自動コミットモードでCREATE DATABASEを実行
                    with admin_engine.connect() as conn:
                        # トランザクション外でCREATE DATABASEを実行
                        conn.execute(text("COMMIT"))
                        conn.connection.autocommit = True

                        # データベース作成（識別子をクォート）
                        safe_db_name = database.replace(
                            '"', '""')  # ダブルクォートエスケープ
                        conn.execute(
                            text(f'CREATE DATABASE "{safe_db_name}" WITH ENCODING \'UTF8\''))

                    self.emit_log(
                        "INFO", f"PostgreSQLデータベース '{database}' の作成に成功しました")

                    # 作成したデータベースに接続テスト
                    database_encoded = urllib.parse.quote(
                        database, safe='', encoding='utf-8')
                    test_connection_string = f'postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}?client_encoding=utf8&connect_timeout=30'

                    test_engine = create_engine(
                        test_connection_string, echo=False)
                    with test_engine.connect() as conn:
                        result = conn.execute(text("SELECT version()"))
                        result.fetchone()

                    return True, f"PostgreSQLデータベース '{database}' を作成し、接続に成功しました"

                except Exception as e:
                    self.emit_log(
                        "WARNING", f"PostgreSQLデータベース作成試行{attempt_num}でエラー: {e}")
                    if attempt_num == len(connection_attempts):
                        raise
                    continue

        except Exception as e:
            error_msg = f"PostgreSQLデータベース '{database}' の作成に失敗しました: {str(e)}"
            self.emit_log("ERROR", error_msg)
            return False, error_msg

    def connect(self):
        """
        データベースに接続する

        修正点3: 指定されたデータベースが存在しない場合は作成を試みる
        """
        db_config = self.settings_manager.get_db_config()
        db_type = db_config.get('type')
        self._db_type = db_type.lower() if db_type else 'sqlite'

        if db_type == "SQLite":
            self._connect_sqlite(db_config)
        elif db_type == "MySQL":
            self._connect_mysql(db_config)
        elif db_type == "PostgreSQL":
            self._connect_postgresql(db_config)
        else:
            error_msg = f"未サポートのデータベース種別: {db_type}"
            self.emit_log("ERROR", error_msg)
            raise ValueError(error_msg)

    def _connect_sqlite(self, db_config: dict):
        """
        SQLite接続（Unicode対応強化版）
        """
        try:
            # パスの安全な処理
            db_path = db_config.get('path', 'jra_data.db')
            db_path = str(db_path).strip() if db_path else 'jra_data.db'

            # UTF-8エンコーディングの確認と修正
            db_path = db_path.encode('utf-8', errors='replace').decode('utf-8')

            self._db_name = db_path
            self.emit_log("INFO", f"SQLiteデータベース接続: {db_path}")

            # SQLite接続文字列の安全な構築
            if os.path.isabs(db_path):
                # 絶対パスの場合
                connection_string = f'sqlite:///{db_path}'
            else:
                # 相対パスの場合
                from pathlib import Path
                safe_path = Path(db_path).resolve()
                connection_string = f'sqlite:///{safe_path}'

            self.engine = create_engine(
                connection_string,
                echo=False,
                pool_pre_ping=True
            )

            # 接続テスト
            with self.engine.connect() as connection:
                result = connection.execute(text("SELECT sqlite_version()"))
                version_info = result.fetchone()[0]
                self.emit_log("INFO", f"SQLite接続成功: バージョン {version_info}")

            self.Session = sessionmaker(bind=self.engine)

        except Exception as e:
            error_msg = f"SQLite接続エラー: {e}"
            self.emit_log("ERROR", error_msg)
            # SQLiteは最後の手段なので、失敗時はNoneのまま
            self.engine = None
            self.Session = None

    def _connect_mysql(self, db_config: dict):
        """
        MySQL接続（修正点3: データベース自動生成機能付き）
        日本語パス対応: URLエンコーディングとUnicode設定強化
        Unicode対策強化版
        """
        import urllib.parse

        host = db_config.get('host', 'localhost')
        try:
            port = int(db_config.get('port', 3306)
                       ) if db_config.get('port') else 3306
        except (ValueError, TypeError):
            port = 3306
            username = db_config.get('username', 'root')
            password = db_config.get('password', '')
        database = db_config.get('database') or db_config.get(
            'db_name', 'jra_data')  # 両方に対応

        self._db_name = database

        # 強化されたUnicodeエンコーディング処理
        try:
            # 文字列の安全な正規化
            username = str(username).strip() if username else 'root'
            password = str(password).strip() if password else ''
            database = str(database).strip() if database else 'jra_data'
            host = str(host).strip() if host else 'localhost'

            # UTF-8エンコーディングの確認と修正
            username = username.encode(
                'utf-8', errors='replace').decode('utf-8')
            password = password.encode(
                'utf-8', errors='replace').decode('utf-8')
            database = database.encode(
                'utf-8', errors='replace').decode('utf-8')

            # URLエンコーディング（safe文字を明示的に指定）
            username_encoded = urllib.parse.quote(
                username, safe='', encoding='utf-8')
            password_encoded = urllib.parse.quote(
                password, safe='', encoding='utf-8')
            database_encoded = urllib.parse.quote(
                database, safe='', encoding='utf-8')

        except Exception as encoding_error:
            error_msg = f"MySQL接続パラメータのエンコーディングエラー: {encoding_error}"
            self.emit_log("ERROR", error_msg)
            self.emit_log("WARNING", "SQLiteフォールバックモードに切り替えます...")
            self._fallback_to_sqlite()
            return

        # 複数の接続方法を試行
        connection_attempts = [
            # 方法1: 標準接続（強化されたエンコーディング）
            (
                f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
                f'?charset=utf8mb4&collation=utf8mb4_unicode_ci&use_unicode=1&connect_timeout=30'
            ),
            # 方法2: シンプルな設定
            (
                f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
                f'?charset=utf8mb4&use_unicode=1'
            ),
            # 方法3: 最小パラメータ
            (
                f'mysql+pymysql://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
            )
        ]

        for attempt_num, connection_string in enumerate(connection_attempts, 1):
            try:
                self.emit_log(
                    "INFO", f"MySQL接続試行 {attempt_num}: {connection_string.replace(password_encoded, '***')}")

                # SQLAlchemy接続オプションでUnicode対応を強化
                connect_args = {
                    'charset': 'utf8mb4',
                    'use_unicode': True,
                    'connect_timeout': 30
                }

                self.engine = create_engine(
                    connection_string,
                    echo=False,
                    connect_args=connect_args,
                    pool_pre_ping=True,
                    pool_recycle=3600
                )

                # 接続をテスト
                with self.engine.connect() as connection:
                    # UTF-8での動作確認
                    result = connection.execute(text("SELECT VERSION()"))
                    version_info = result.fetchone()[0]
                    self.emit_log(
                        "INFO", f"MySQL接続成功（試行{attempt_num}）: {version_info}")

                self.Session = sessionmaker(bind=self.engine)
                return

            except OperationalError as e:
                # 修正点3: データベースが存在しない場合のエラーをハンドル
                if self._handle_mysql_db_creation(e, host, port, username, password, database):
                    # データベース作成後、再接続（同じエンコーディング設定）
                    self.emit_log("INFO", "データベース作成後、再接続を試行中...")
                    self.engine = create_engine(
                        connection_string,
                        echo=False,
                        connect_args=connect_args,
                        pool_pre_ping=True,
                        pool_recycle=3600
                    )

                    with self.engine.connect() as connection:
                        self.emit_log(
                            "INFO", f"MySQLデータベース '{database}' に再接続成功")

                    self.Session = sessionmaker(bind=self.engine)
                    return
                else:
                    # その他のOperationalErrorは次の接続方法を試行
                    self.emit_log(
                        "WARNING", f"MySQL接続試行{attempt_num}でOperationalError: {e}")
                    continue

            except UnicodeDecodeError as e:
                # Unicode関連エラーの詳細な処理
                error_msg = f"MySQL接続試行{attempt_num}でUnicodeエラー（日本語パス関連）: {e}"
                self.emit_log("WARNING", error_msg)
                continue

            except Exception as e:
                error_msg = f"MySQL接続試行{attempt_num}で一般エラー: {e}"
                self.emit_log("WARNING", error_msg)
                continue

        # すべての接続試行が失敗した場合
        self.emit_log("ERROR", "MySQL接続の全ての試行が失敗しました")
        self.emit_log("WARNING", "SQLiteフォールバックモードに切り替えます...")
        self._fallback_to_sqlite()
        return

    def _connect_postgresql(self, db_config: dict):
        """
        PostgreSQL接続（修正点3: データベース自動生成機能付き）
        日本語パス対応: URLエンコーディングとUnicode設定強化
        Unicode対策強化版
        """
        import urllib.parse

        host = db_config.get('host', 'localhost')
        try:
            port = int(db_config.get('port', 5432)
                       ) if db_config.get('port') else 5432
        except (ValueError, TypeError):
            port = 5432
            username = db_config.get('username', 'postgres')
            password = db_config.get('password', '')
        database = db_config.get('database') or db_config.get(
            'db_name', 'jra_data')  # 両方に対応

        self._db_name = database

        # 強化されたUnicodeエンコーディング処理
        try:
            # 文字列の安全な正規化
            username = str(username).strip() if username else 'postgres'
            password = str(password).strip() if password else ''
            database = str(database).strip() if database else 'jra_data'
            host = str(host).strip() if host else 'localhost'

            # UTF-8エンコーディングの確認と修正
            username = username.encode(
                'utf-8', errors='replace').decode('utf-8')
            password = password.encode(
                'utf-8', errors='replace').decode('utf-8')
            database = database.encode(
                'utf-8', errors='replace').decode('utf-8')

            # URLエンコーディング（safe文字を明示的に指定）
            username_encoded = urllib.parse.quote(
                username, safe='', encoding='utf-8')
            password_encoded = urllib.parse.quote(
                password, safe='', encoding='utf-8')
            database_encoded = urllib.parse.quote(
                database, safe='', encoding='utf-8')

        except Exception as encoding_error:
            error_msg = f"PostgreSQL接続パラメータのエンコーディングエラー: {encoding_error}"
            self.emit_log("ERROR", error_msg)
            self.emit_log("WARNING", "SQLiteフォールバックモードに切り替えます...")
            self._fallback_to_sqlite()
            return

        # Windows環境でのTCP接続調整 + 強化されたエンコーディング設定
        import platform
        if platform.system() == 'Windows':
            if host in ['localhost', '127.0.0.1']:
                host = '127.0.0.1'

        # 複数の接続方法を試行
        connection_attempts = [
            # 方法1: 標準接続（強化されたエンコーディング）
            (
                f'postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
                f'?client_encoding=utf8&application_name=JRA-Data-Collector'
                f'&connect_timeout=30&options=-c timezone=Asia/Tokyo'
            ),
            # 方法2: シンプルな設定
            (
                f'postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
                f'?client_encoding=utf8&connect_timeout=30'
            ),
            # 方法3: 最小パラメータ
            (
                f'postgresql+psycopg2://{username_encoded}:{password_encoded}@{host}:{port}/{database_encoded}'
            )
        ]

        for attempt_num, connection_string in enumerate(connection_attempts, 1):
            try:
                self.emit_log(
                    "INFO", f"PostgreSQL接続試行 {attempt_num}: {connection_string.replace(password_encoded, '***')}")

                # SQLAlchemy接続オプションでUnicode対応を強化
                connect_args = {
                    'client_encoding': 'utf8',
                    'application_name': 'JRA-Data-Collector',
                    'connect_timeout': 30
                }

                self.engine = create_engine(
                    connection_string,
                    echo=False,
                    connect_args=connect_args,
                    pool_pre_ping=True,  # 接続の事前確認
                    pool_recycle=3600    # 1時間で接続を再利用
                )

                # 接続をテスト
                with self.engine.connect() as connection:
                    # UTF-8での動作確認
                    result = connection.execute(text("SELECT version()"))
                    version_info = result.fetchone()[0]
                    self.emit_log(
                        "INFO", f"PostgreSQL接続成功（試行{attempt_num}）: {version_info[:100]}...")

                self.Session = sessionmaker(bind=self.engine)
                return

            except OperationalError as e:
                # 修正点3: データベースが存在しない場合のエラーをハンドル
                if self._handle_postgresql_db_creation(e, host, port, username, password, database):
                    # データベース作成後、再接続（同じエンコーディング設定）
                    self.emit_log("INFO", "データベース作成後、再接続を試行中...")
                    self.engine = create_engine(
                        connection_string,
                        echo=False,
                        connect_args=connect_args,
                        pool_pre_ping=True,
                        pool_recycle=3600
                    )

                    with self.engine.connect() as connection:
                        self.emit_log(
                            "INFO", f"PostgreSQLデータベース '{database}' に再接続成功")

                    self.Session = sessionmaker(bind=self.engine)
                    return
                # 一時的にコメントアウト: インデントエラー修正のため
                # else:
                #     # その他のOperationalErrorは次の接続方法を試行
                #     self.emit_log("WARNING", f"PostgreSQL接続試行{attempt_num}でOperationalError: {e}")
                #     continue

            except UnicodeDecodeError as e:
                # Unicode関連エラーの詳細な処理
                error_msg = f"PostgreSQL接続試行{attempt_num}でUnicodeエラー（日本語パス関連）: {e}"
                self.emit_log("WARNING", error_msg)
                # continue  # 一時的にコメントアウト

            except Exception as e:
                error_msg = f"PostgreSQL接続試行{attempt_num}で一般エラー: {e}"
                self.emit_log("WARNING", error_msg)
                # continue  # 一時的にコメントアウト

        # すべての接続試行が失敗した場合
        self.emit_log("ERROR", "PostgreSQL接続の全ての試行が失敗しました")
        self.emit_log("WARNING", "SQLiteフォールバックモードに切り替えます...")
        self._fallback_to_sqlite()
        return

    def _fallback_to_sqlite(self):
        """
        PostgreSQL接続失敗時のSQLiteフォールバック
        """
        try:
            import os
            # 日本語パスセーフなSQLiteファイル名を生成
            safe_db_path = os.path.join(os.getcwd(), "jra_data_fallback.db")
            self.emit_log("INFO", f"SQLiteフォールバック: {safe_db_path}")

            self._db_type = "sqlite"
            self._db_name = safe_db_path

            self.engine = create_engine(
                f'sqlite:///{safe_db_path}', echo=False)

            # 接続テスト
            with self.engine.connect() as connection:
                self.emit_log("INFO", "SQLiteフォールバック接続が成功しました")

            self.Session = sessionmaker(bind=self.engine)

        except Exception as fallback_error:
            self.emit_log("ERROR", f"SQLiteフォールバックも失敗: {fallback_error}")
            self.engine = None
            self.Session = None

    def _handle_mysql_db_creation(self, e: OperationalError, host: str, port: int,
                                  username: str, password: str, database: str) -> bool:
        """
        MySQLデータベースが存在しないエラーを検出し、作成を試みる

        修正点3: MySQL用データベース自動生成
        """
        if not MYSQL_CONNECTOR_AVAILABLE:
            self.emit_log(
                "ERROR", "mysql.connectorが利用できません。データベース自動作成をスキップします。")
            return False

        original_exception = e.orig
        db_does_not_exist = False

        if isinstance(original_exception, mysql.connector.Error):
            # mysql-connector-pythonの場合、エラーコード ER_BAD_DB_ERROR (1049) を確認
            if original_exception.errno == mysql.connector.errorcode.ER_BAD_DB_ERROR:
                db_does_not_exist = True

        if db_does_not_exist:
            self.emit_log(
                "WARNING", f"MySQLデータベース '{database}' が存在しません。自動作成を試行します。")

            try:
                # デフォルトデータベースに接続
                default_connection_string = f'mysql+pymysql://{username}:{password}@{host}:{port}'
                engine = create_engine(default_connection_string)

                with engine.connect() as connection:
                    # AUTOCOMMITを設定してCREATE DATABASEを実行
                    connection = connection.execution_options(
                        isolation_level="AUTOCOMMIT")
                    connection.execute(text(f"CREATE DATABASE {database}"))

                self.emit_log("INFO", f"MySQLデータベース '{database}' を正常に作成しました")
                return True

            except Exception as create_exc:
                error_msg = f"MySQLデータベース '{database}' の作成に失敗しました: {create_exc}"
                self.emit_log("ERROR", error_msg)
                raise ConnectionError(error_msg) from create_exc

        return False

    def _handle_postgresql_db_creation(self, e: OperationalError, host: str, port: int,
                                       username: str, password: str, database: str) -> bool:
        """
        PostgreSQLデータベースが存在しないエラーを検出し、作成を試みる

        修正点3: PostgreSQL用データベース自動生成
        """
        if not PSYCOPG2_AVAILABLE:
            self.emit_log("ERROR", "psycopg2が利用できません。データベース自動作成をスキップします。")
            return False

        original_exception = e.orig
        db_does_not_exist = False

        if isinstance(original_exception, psycopg2.OperationalError):
            # psycopg2の場合、"database... does not exist" というメッセージが含まれる
            if f'database "{database}" does not exist' in str(original_exception):
                db_does_not_exist = True

        if db_does_not_exist:
            self.emit_log(
                "WARNING", f"PostgreSQLデータベース '{database}' が存在しません。自動作成を試行します。")

            try:
                # デフォルトデータベース（postgres）に接続
                import platform
                if platform.system() == 'Windows':
                    default_connection_string = f'postgresql+psycopg2://{username}:{password}@{host}:{port}/postgres?host={host}'
                else:
                    default_connection_string = f'postgresql+psycopg2://{username}:{password}@{host}:{port}/postgres'

                engine = create_engine(default_connection_string)

                with engine.connect() as connection:
                    # AUTOCOMMITを設定してCREATE DATABASEを実行
                    connection = connection.execution_options(
                        isolation_level="AUTOCOMMIT")
                    connection.execute(text(f"CREATE DATABASE {database}"))

                self.emit_log(
                    "INFO", f"PostgreSQLデータベース '{database}' を正常に作成しました")
                return True

            except Exception as create_exc:
                error_msg = f"PostgreSQLデータベース '{database}' の作成に失敗しました: {create_exc}"
                self.emit_log("ERROR", error_msg)
                raise ConnectionError(error_msg) from create_exc

        return False

    def get_db_type(self) -> str:
        """データベースタイプを取得"""
        return self._db_type

    def get_db_name(self) -> str:
        """データベース名を取得"""
        return self._db_name

    def bulk_insert(self, table_name: str, df: pd.DataFrame):
        """
        pandas.DataFrame形式のデータを、指定されたテーブルに高速に一括挿入する。
        主キー重複などのエラーが発生した場合は、そのトランザクションをスキップして処理を継続する。
        """
        if self.engine is None or df.empty:
            if self.engine is None:
                logging.warning("データベース未接続のため挿入をスキップします。")
            return

        logging.info(f"テーブル '{table_name}' に {len(df)} 件のデータを挿入します。")
        try:
            df.to_sql(
                table_name,
                con=self.engine,
                if_exists='append',
                index=False
            )
            logging.info(f"テーブル '{table_name}' へのデータ挿入が完了しました。")
        except IntegrityError:
            logging.warning(
                f"テーブル '{table_name}' への挿入中に主キー重複エラーが発生しました。重複データはスキップされます。")
            # 重複エラーの場合は、1行ずつ挿入を試みるフォールバック処理
            self._insert_row_by_row(table_name, df)
        except Exception as e:
            logging.error(f"バルクインサート中に予期せぬエラーが発生しました: {e}")
            # その他のエラーは処理を中断させるため再スロー
            raise

    def _insert_row_by_row(self, table_name: str, df: pd.DataFrame):
        """1行ずつデータを挿入するフォールバックメソッド"""
        logging.info(f"フォールバック処理: '{table_name}'テーブルに1行ずつ挿入を試みます。")
        success_count = 0
        with self.engine.connect() as connection:
            for i, row in df.iterrows():
                try:
                    with connection.begin() as trans:  # 各行でトランザクションを開始
                        row.to_frame().T.to_sql(table_name, con=connection, if_exists='append', index=False)
                        success_count += 1
                except IntegrityError:
                    # 主キー重複は無視
                    continue
                except Exception as e:
                    logging.error(f"行単位の挿入中にエラー (Row {i}): {e}")
                    # 他のエラーはログに残す
        logging.info(f"フォールバック処理完了。{success_count}/{len(df)} 件の新規データを挿入しました。")

    def get_table_names(self) -> list[str]:
        """
        データベースに存在するすべてのテーブル名を取得する。
        """
        if self.engine is None:
            logging.warning("データベースに接続されていないため、テーブル名を取得できません。")
            return []
        try:
            inspector = inspect(self.engine)
            return inspector.get_table_names()
        except Exception as e:
            logging.error(f"テーブル名の取得中にエラーが発生しました: {e}")
            return []

    def get_table_columns(self, table_name: str) -> list[str]:
        """
        指定されたテーブルのカラム名一覧を取得する。
        """
        if self.engine is None:
            logging.warning(f"データベースに接続されていないため、'{table_name}'の絡む名を取得できません。")
            return []
        try:
            inspector = inspect(self.engine)
            columns = inspector.get_columns(table_name)
            return [col['name'] for col in columns]
        except Exception as e:
            logging.error(f"'{table_name}'の絡む名の取得中にエラーが発生しました: {e}")
            return []

    def get_data_summary(self) -> dict:
        """
        ダッシュボード表示用に、各主要テーブルのレコード総数と最新更新日時を取得する。
        """
        if self.engine is None:
            logging.warning("データベースに接続されていないため、サマリーを取得できません。")
            return {}

        logging.info("データサマリーを取得します。")
        summary = {}

        try:
            # データベースに存在するテーブル名を取得
            inspector = inspect(self.engine)
            table_names = inspector.get_table_names()

            # ETLプロセッサで定義されている主要テーブルのみ対象とする
            from ..services.etl_processor import EtlProcessor
            tracked_tables = [
                spec['table_name'] for spec in EtlProcessor.SPEC_DEFINITIONS.values()
            ]

            with self.Session() as session:
                for table_name in tracked_tables:
                    if table_name in table_names:
                        try:
                            # レコード数を取得
                            count_query = text(
                                f"SELECT COUNT(*) FROM {table_name}")
                            count_result = session.execute(
                                count_query).scalar()

                            # 最新更新日時を取得（created_dateカラムがある場合）
                            latest = "N/A"
                            try:
                                latest_query = text(
                                    f"SELECT MAX(create_date) FROM {table_name}")
                                latest_result = session.execute(
                                    latest_query).scalar()
                                if latest_result:
                                    latest = str(latest_result)
                            except:
                                # create_dateカラムが存在しない場合は無視
                                pass

                            summary[table_name] = {
                                "count": count_result or 0,
                                "latest": latest
                            }
                        except Exception as e:
                            logging.warning(
                                f"テーブル '{table_name}' のサマリー取得でエラー: {e}")
                            summary[table_name] = {"count": 0, "latest": "エラー"}
                    else:
                        # テーブルが存在しない場合
                        summary[table_name] = {"count": 0, "latest": "未作成"}

        except Exception as e:
            logging.error(f"データサマリー取得中にエラーが発生: {e}")
            return {"エラー": {"count": 0, "latest": str(e)}}

        return summary

    def close(self):
        """データベース接続を閉じる"""
        if self.engine:
            self.engine.dispose()
            logging.info("データベース接続を閉じました。")

    def reconnect(self, new_db_config: dict = None) -> tuple[bool, str]:
        """
        新しい設定でデータベースに再接続する

        Args:
            new_db_config: 新しいデータベース設定（Noneの場合は現在の設定を再読み込み）

        Returns:
            (接続成功フラグ, メッセージ)
        """
        try:
            self.emit_log("INFO", "データベース再接続を開始します")
            
            # 既存の接続を安全に破棄
            if self.engine:
                try:
                    self.engine.dispose()
                    self.emit_log("INFO", "既存のデータベース接続を破棄しました")
                except Exception as e:
                    self.emit_log("WARNING", f"既存接続の破棄中にエラー: {e}")

            # セッションファクトリもリセット
            self.Session = None
            self.engine = None
            self._db_type = None
            self._db_name = None

            # 新しい設定でConfigManagerを更新（設定が提供された場合）
            if new_db_config:
                try:
                    # 設定を部分的に更新
                    for key, value in new_db_config.items():
                        if key in ['type', 'host', 'port', 'username', 'password', 'db_name', 'path']:
                            # ConfigManagerの update_db_config を通じて設定を更新
                            # これによりシグナルも適切に発火される
                            pass  # 後でConfigManagerのAPIを通じて更新

                    # SettingsManagerの設定を更新
                    self.settings_manager.update_db_config(**new_db_config)
                    self.emit_log("INFO", f"新しいデータベース設定を適用: {new_db_config.get('type', 'Unknown')}")
                    
                except Exception as e:
                    self.emit_log("ERROR", f"設定更新中にエラー: {e}")
                    return False, f"設定更新エラー: {e}"

            # 新しい設定で再接続を試行
            try:
                self.connect()
                
                # 接続成功をテスト
                if self.engine:
                    with self.engine.connect() as conn:
                        # 簡単な接続テスト
                        if self._db_type == 'sqlite':
                            conn.execute(text("SELECT 1"))
                        elif self._db_type == 'mysql':
                            conn.execute(text("SELECT 1"))
                        elif self._db_type == 'postgresql':
                            conn.execute(text("SELECT 1"))
                    
                    success_msg = f"{self._db_type} データベース '{self._db_name}' への再接続に成功しました"
                    self.emit_log("INFO", success_msg)
                    return True, success_msg
                else:
                    error_msg = "データベースエンジンの初期化に失敗しました"
                    self.emit_log("ERROR", error_msg)
                    return False, error_msg

            except Exception as connect_error:
                error_msg = f"データベース再接続に失敗: {connect_error}"
                self.emit_log("ERROR", error_msg)
                return False, error_msg

        except Exception as e:
            critical_error_msg = f"データベース再接続処理中に予期しないエラー: {e}"
            self.emit_log("ERROR", critical_error_msg)
            return False, critical_error_msg

    def upsert_records(self, table_name: str, records: List[Any],
                       primary_keys: List[str] = None) -> Dict[str, int]:
        """
        アトミックなUPSERT操作でレコードを挿入/更新

        Args:
            table_name: テーブル名
            records: dataclassインスタンスのリスト
            primary_keys: 主キーとなるカラム名のリスト

        Returns:
            処理結果の統計情報 {'inserted': 0, 'updated': 0, 'errors': 0}

        Raises:
            DatabaseError: データベース操作エラー
        """
        if not records:
            self.emit_log("WARNING", "挿入するレコードがありません")
            return {'inserted': 0, 'updated': 0, 'errors': 0}

        if not self.engine:
            raise DatabaseError("データベース接続が確立されていません", operation="upsert")

        # dataclassを辞書に変換
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
                self.emit_log("ERROR", f"サポートされていないレコード型: {type(record)}")
                continue

        if not record_dicts:
            return {'inserted': 0, 'updated': 0, 'errors': 0}

        # データベース種別に応じたUPSERT実行
        db_type = self._db_type.lower() if self._db_type else 'sqlite'

        try:
            if db_type == 'mysql':
                return self._mysql_upsert(table_name, record_dicts, primary_keys)
            elif db_type == 'postgresql':
                return self._postgresql_upsert(table_name, record_dicts, primary_keys)
            elif db_type == 'sqlite':
                return self._sqlite_upsert(table_name, record_dicts, primary_keys)
            else:
                raise DatabaseError(f"サポートされていないデータベース種別: {db_type}")

        except Exception as e:
            self.emit_log("ERROR", f"UPSERT操作中にエラーが発生: {e}")
            raise DatabaseError(f"UPSERT操作に失敗しました: {e}", operation="upsert")

    def _mysql_upsert(self, table_name: str, records: List[Dict[str, Any]],
                      primary_keys: List[str] = None) -> Dict[str, int]:
        """
        MySQL用のUPSERT操作 (INSERT ... ON DUPLICATE KEY UPDATE)
        """
        if not records:
            return {'inserted': 0, 'updated': 0, 'errors': 0}

        # カラム名を取得
        columns = list(records[0].keys())

        # UPDATE句用のカラム（主キーを除く）
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
            # 更新するカラムがない場合はINSERT IGNOREを使用
            sql = f"""
                INSERT IGNORE INTO `{table_name}` ({column_list})
                VALUES ({placeholders})
            """

        return self._execute_batch_upsert(sql, records, columns, "MySQL")

    def _postgresql_upsert(self, table_name: str, records: List[Dict[str, Any]],
                           primary_keys: List[str] = None) -> Dict[str, int]:
        """
        PostgreSQL用のUPSERT操作 (INSERT ... ON CONFLICT DO UPDATE)
        """
        if not records:
            return {'inserted': 0, 'updated': 0, 'errors': 0}

        # カラム名を取得
        columns = list(records[0].keys())

        # 主キーが指定されていない場合はIDを使用
        if not primary_keys:
            primary_keys = ['id']  # デフォルト主キー

        # UPDATE句用のカラム（主キーを除く）
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
            # 更新するカラムがない場合はDO NOTHINGを使用
            sql = f"""
                INSERT INTO "{table_name}" ({column_list})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_target}) DO NOTHING
            """

        return self._execute_batch_upsert(sql, records, columns, "PostgreSQL")

    def _sqlite_upsert(self, table_name: str, records: List[Dict[str, Any]],
                       primary_keys: List[str] = None) -> Dict[str, int]:
        """
        SQLite用のUPSERT操作 (INSERT ... ON CONFLICT DO UPDATE)
        """
        if not records:
            return {'inserted': 0, 'updated': 0, 'errors': 0}

        # カラム名を取得
        columns = list(records[0].keys())

        # 主キーが指定されていない場合はROWIDを使用
        if not primary_keys:
            # SQLiteの場合、テーブル情報から主キーを推定
            primary_keys = self._get_sqlite_primary_keys(table_name)

        # UPDATE句用のカラム（主キーを除く）
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
            # 主キーが不明またはUPDATEするカラムがない場合はINSERT OR IGNOREを使用
            sql = f"""
                INSERT OR IGNORE INTO "{table_name}" ({column_list})
                VALUES ({placeholders})
            """

        return self._execute_batch_upsert(sql, records, columns, "SQLite")

    def _execute_batch_upsert(self, sql: str, records: List[Dict[str, Any]],
                              columns: List[str], db_type: str) -> Dict[str, int]:
        """
        バッチUPSERT操作を実行
        """
        # データ準備
        batch_data = []
        for record in records:
            row_data = [record.get(col) for col in columns]
            batch_data.append(row_data)

        # バッチ実行
        try:
            with self.engine.begin() as conn:
                result = conn.execute(text(sql), batch_data)

                # 影響を受けた行数を取得（データベースによって異なる）
                affected_rows = result.rowcount if hasattr(
                    result, 'rowcount') else len(batch_data)

                self.emit_log(
                    "INFO", f"{db_type} UPSERT操作完了: {affected_rows}行処理, {len(batch_data)}レコード送信")

                # SQLiteやMySQLでは詳細な統計が取得できないため、簡略化
                return {
                    'inserted': affected_rows,  # 正確な分離は困難
                    'updated': 0,
                    'errors': len(batch_data) - affected_rows if affected_rows <= len(batch_data) else 0
                }

        except IntegrityError as e:
            self.emit_log("ERROR", f"データ整合性エラー: {e}")
            raise DatabaseIntegrityError(f"データ整合性エラー: {e}", operation="upsert")
        except Exception as e:
            self.emit_log("ERROR", f"UPSERT実行エラー: {e}")
            raise DatabaseError(f"UPSERT実行に失敗しました: {e}", operation="upsert")

    def _get_sqlite_primary_keys(self, table_name: str) -> List[str]:
        """
        SQLiteテーブルの主キーカラムを取得
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(f"PRAGMA table_info('{table_name}')"))
                primary_keys = []
                for row in result:
                    if row[5]:  # pk フィールドが1の場合
                        primary_keys.append(row[1])  # column name
                return primary_keys or ['rowid']  # デフォルトはrowid
        except Exception as e:
            self.emit_log("WARNING", f"主キー情報の取得に失敗: {e}")
            return ['rowid']

    def upsert_race_details(self, race_details: List['RaceDetail']) -> Dict[str, int]:
        """
        レース詳細情報のUPSERT操作

        Args:
            race_details: RaceDetailのdataclassインスタンスリスト

        Returns:
            処理結果統計
        """
        primary_keys = ['kaisai_year', 'keibajo_code',
                        'kaisai_kaiji', 'kaisai_nichiji', 'race_number']
        return self.upsert_records('races', race_details, primary_keys)

    def upsert_horse_race_info(self, horse_race_infos: List['HorseRaceInfo']) -> Dict[str, int]:
        """
        馬毎レース情報のUPSERT操作

        Args:
            horse_race_infos: HorseRaceInfoのdataclassインスタンスリスト

        Returns:
            処理結果統計
        """
        primary_keys = ['kaisai_year', 'keibajo_code', 'kaisai_kaiji', 'kaisai_nichiji',
                        'race_number', 'umaban']
        return self.upsert_records('race_entries', horse_race_infos, primary_keys)

    # 既存のbulk_insertメソッドもUPSERTを使用するように最適化
    def bulk_insert_optimized(self, table_name: str, records: List[Any],
                              primary_keys: List[str] = None) -> Dict[str, int]:
        """
        最適化されたバルクインサート（UPSERT使用）

        既存のbulk_insertメソッドの最適化版
        """
        return self.upsert_records(table_name, records, primary_keys)
