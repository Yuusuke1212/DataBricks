from __future__ import annotations
from typing import TYPE_CHECKING, List, Dict, Any
import logging
from datetime import datetime, timedelta
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QDialog

from ..services.settings_manager import SettingsManager
from ..services.db_manager import DatabaseManager
from ..services.jvlink_manager import JvLinkManager
from ..services.etl_processor import EtlProcessor, EtlDataPipeline
from ..services.export_manager import ExportManager

# State Machine パターンのインポート
from ..services.state_machine.base import AppState
from ..services.state_machine.states import IdleState

# Phase 3: Worker Pipeline 統合
from ..services.workers.pipeline_coordinator import PipelineCoordinator
from ..services.workers.base import ProgressInfo

# 統一シグナルシステムと構造化ログ
from ..services.workers.signals import WorkerSignals, LogRecord, ProgressInfo as NewProgressInfo, TaskResult

if TYPE_CHECKING:
    from ..views.main_window import MainWindow
    from ..views.setup_dialog import SetupDialog
    from ..views.settings_view import SettingsView
    from ..views.etl_setting_view import EtlSettingView


class AppController(QObject):
    """
    アプリケーション全体のコントローラー。
    UI(View)とビジネスロジック(Service)間の調整役。

    State Machineパターンのコンテキストとして機能し、
    アプリケーションのライフサイクルを厳格に管理します。

    Phase 3: Worker Pipeline統合により高性能並列処理をサポート
    """

    def __init__(self, main_window: MainWindow = None, parent=None):
        super().__init__(parent)

        # 構造化ログ機能を追加
        from ..services.workers.signals import LoggerMixin
        self.logger = LoggerMixin("アプリケーション制御", "AppController")

        # State Machine 初期化
        self._state: AppState = None

        # 基本設定
        self.main_window = main_window
        self.settings_manager = SettingsManager()

        # データベース接続初期化（エラーハンドリング付き）
        try:
            self.db_manager = DatabaseManager(self.settings_manager)
        except Exception as e:
            self.emit_log("ERROR", f"データベースマネージャー初期化エラー: {e}")
            self.db_manager = None

        # アーキテクチャ対応のJV-Linkマネージャーを使用
        try:
            from ..services.jvlink_adapter import create_jvlink_manager
            self.jvlink_manager = create_jvlink_manager()
            logging.info("アーキテクチャ対応JV-Linkマネージャーを初期化しました")
        except ImportError:
            # フォールバック: 従来のマネージャーを使用
            self.jvlink_manager = JvLinkManager()
            logging.warning("従来のJV-Linkマネージャーを使用します")

        self.etl_processor = EtlProcessor()
        self.export_manager = ExportManager(self.db_manager)

        # Phase 3: PipelineCoordinator 初期化
        self.pipeline_coordinator = self._initialize_pipeline_coordinator()

        # 既存のETLパイプライン（下位互換性のため維持）
        self.etl_pipeline = EtlDataPipeline(
            self.etl_processor, self.db_manager)
        self.etl_pipeline.item_processed.connect(
            self._on_pipeline_item_processed)
        self.etl_pipeline.pipeline_finished.connect(self._on_pipeline_finished)
        self.etl_pipeline.pipeline_error.connect(self._on_pipeline_error)

        # 状態管理
        self.current_data_specs = []  # 複数のデータ種別を管理
        self.is_watching_realtime = False
        self.pipeline_total_expected = 0  # パイプラインで処理予定の総件数
        self.pipeline_processed_count = 0  # パイプラインで処理済みの件数

        # Phase 3 Update: 構造化ログとマルチタスク管理
        self.active_tasks: Dict[str, Dict[str, Any]] = {}  # タスク名 -> タスク情報
        self.log_records: List[LogRecord] = []  # 構造化ログのマスターリスト

        self._setup_enhanced_logging()

        # 初期化状態管理フラグ（無限ループ対策）
        self._is_initializing = False

        # State Machineを初期状態（Idle）に設定
        self.transition_to(IdleState())

    def _setup_enhanced_logging(self):
        """強化されたログ設定を行う"""
        import os
        from datetime import datetime

        # ログディレクトリの作成
        log_dir = os.path.join(
            os.path.dirname(
                os.path.dirname(
                    os.path.dirname(__file__))),
            "logs")
        os.makedirs(log_dir, exist_ok=True)

        # ログファイル名（日付付き）
        log_filename = f"jra_data_collector_{
            datetime.now().strftime('%Y%m%d')}.log"
        log_filepath = os.path.join(log_dir, log_filename)

        # ルートロガーの設定
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)

        # 既存のハンドラーをクリア
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # 詳細なフォーマッター
        detailed_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)8s] %(name)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # シンプルなフォーマッター（コンソール用）
        simple_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )

        # ファイルハンドラー（詳細ログ）
        file_handler = logging.FileHandler(log_filepath, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)

        # コンソールハンドラー（重要なログのみ）
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        root_logger.addHandler(console_handler)

        # 起動ログ
        logging.info("=" * 60)
        logging.info("JRA-Data Collector アプリケーションを開始しました")
        logging.info(f"ログファイル: {log_filepath}")
        logging.info(f"ログレベル: ファイル=DEBUG, コンソール=INFO")
        logging.info("=" * 60)

    def transition_to(self, state: AppState) -> None:
        """
        新しい状態に遷移する

        Args:
            state: 遷移先の状態オブジェクト
        """
        try:
            # 現在の状態の終了処理
            if self._state:
                self._state.on_exit()

            # 新しい状態の設定
            self._state = state
            self._state.context = self

            # 新しい状態の開始処理
            self._state.on_enter()

            logging.info(f"State transition completed: -> {state.name}")

        except Exception as e:
            logging.error(f"State transition failed: {e}")
            # 遷移に失敗した場合はエラー状態に遷移
            from ..services.state_machine.states import ErrorState
            if not isinstance(state, ErrorState):  # 無限ループを防ぐ
                self._force_transition_to_error(e)

    def _force_transition_to_error(self, error: Exception) -> None:
        """エラー状態への強制遷移（循環参照を避けるための内部メソッド）"""
        try:
            from ..services.state_machine.states import ErrorState
            self._state = ErrorState(error)
            self._state.context = self
            self._state.on_enter()
        except Exception as critical_error:
            logging.critical(
                f"Critical error during error state transition: {critical_error}")

    @property
    def state(self) -> AppState:
        """現在の状態を取得"""
        return self._state

    @property
    def state_name(self) -> str:
        """現在の状態名を取得"""
        return self._state.name if self._state else "Unknown"

    # === UI からのコールバック（State Machineに委譲）===

    def request_start(self, params: dict = None) -> None:
        """
        処理開始要求（UIからの呼び出し）

        Args:
            params: 処理パラメータ
        """
        if self._state:
            self._state.start_processing(params)
        else:
            logging.error("No state available to handle start request")

    def request_cancel(self) -> None:
        """
        処理キャンセル要求（UIからの呼び出し）
        """
        if self._state:
            self._state.cancel_processing()
        else:
            logging.error("No state available to handle cancel request")

    def initialize_app(self):
        """
        アプリケーションの初期化処理（シーケンス図「シナリオ1」に相当）
        main_windowが設定された後に呼び出す。

        JV-Link自動起動を無効化：ユーザーが必要な時のみ手動で接続
        """
        # 初期化フラグを設定（シグナル・スロットループ対策）
        self._is_initializing = True
        
        try:
            logging.info("アプリケーションの初期化を開始します。")

            # シグナル接続
            self.initialize_connections()

            # 1. 設定の読み込み (SettingsManagerはコンストラクタで読み込み済み)

            # 2. データベースへの接続 (DBManagerのコンストラクタで実行済み)

            # 3. JV-Link設定はレジストリで管理（JVSetUIProperties()で設定）
            logging.info(
                "JV-Link設定はWindowsレジストリで管理されます。設定画面から公式ダイアログを開いて設定してください。")

            # 4. 初期のダッシュボード更新
            summary = self.db_manager.get_data_summary()
            if hasattr(
                    self.main_window,
                    'dashboard_view') and self.main_window.dashboard_view:
                self.main_window.dashboard_view.update_dashboard_summary(summary)

            logging.info("アプリケーションの初期化が完了しました。")
            
        except Exception as e:
            logging.error(f"アプリケーション初期化中にエラーが発生しました: {e}")
            raise
        finally:
            # 初期化完了後、フラグを解除
            self._is_initializing = False

    def initialize_connections(self):
        """UIとコントローラー間のシグナル・スロット接続を確立する"""
        logging.info("UIとコントローラーの接続を初期化します。")

        # JV-Link Manager
        self.jvlink_manager.data_received.connect(self.on_data_received)
        self.jvlink_manager.operation_finished.connect(
            self.on_operation_finished)
        self.jvlink_manager.error_occurred.connect(self.on_error_occurred)
        self.jvlink_manager.realtime_event_received.connect(
            self.on_realtime_event_received)

        # Export Manager
        self.export_manager.export_progress.connect(self.on_export_progress)
        self.export_manager.export_finished.connect(self.on_export_finished)
        self.export_manager.export_error.connect(self.on_export_error)

        # SettingsView
        self.main_window.settings_view.settings_saved.connect(
            self.save_settings)
        self.main_window.settings_view.db_test_requested.connect(
            self.test_db_connection)
        self.main_window.settings_view.jvlink_dialog_requested.connect(
            self.open_jvlink_settings_dialog)

        # EtlSettingView
        self.main_window.etl_setting_view.save_rule_requested.connect(
            self.save_etl_rule)
        self.main_window.etl_setting_view.delete_rule_requested.connect(
            self.delete_etl_rule)
        self.main_window.etl_setting_view.rule_combo.currentTextChanged.connect(
            self.on_etl_rule_selected)

        # DashboardView
        self.main_window.dashboard_view.diff_button_clicked.connect(
            self.start_diff_update)
        self.main_window.dashboard_view.full_button_clicked.connect(
            self.show_setup_dialog)
        self.main_window.dashboard_view.realtime_toggled.connect(
            self.toggle_realtime_watch)

        # SetupDialog は Controller 側でモーダル表示するためシグナル接続不要

        # ExportView
        self.main_window.export_view.export_requested.connect(
            self.start_export)

        # ConfigManager設定変更通知の接続（新機能）
        if hasattr(self.settings_manager, 'database_config_updated'):
            self.settings_manager.database_config_updated.connect(
                self.on_database_config_updated)
        if hasattr(self.settings_manager, 'settings_saved'):
            self.settings_manager.settings_saved.connect(
                self.on_settings_saved)

        # Phase 3 Update: Pipeline Coordinator接続（統一シグナル）
        if hasattr(self, 'pipeline_coordinator') and self.pipeline_coordinator:
            # pipeline_coordinatorが統一シグナルを発行する場合の接続
            # （実装時には、PipelineCoordinatorも統一シグナルシステムに更新する）
            pass

        # UIの初期設定を読み込む
        self.load_and_apply_settings()

        # 修正点4: 初期化時にDB情報を更新
        self._update_dashboard_db_info()

    def emit_log(self, level: str, message: str, context=None):
        """LoggerMixinのemit_logを委譲"""
        self.logger.emit_log(level, message, context)

    def connect_jvlink_manually(self) -> bool:
        """
        JV-Linkへの手動接続

        レジストリに保存されたJV-Link設定（JVSetUIProperties()で設定）を
        自動的に読み込んで初期化を行います。
        """
        try:
            self.emit_log("INFO", "JV-Link手動接続を開始します。")

            # JV-Linkマネージャーの初期化（レジストリから設定を自動読み込み）
            success = self.jvlink_manager.initialize()
            if success:
                self.emit_log("INFO", "JV-Link接続が正常に完了しました。")
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage("JV-Link接続が完了しました。", 3000)
                return True
            else:
                error_msg = ("JV-Link接続に失敗しました。\n\n"
                             "JV-Link設定ダイアログ（設定画面）で正しい設定を行ってください。")
                self.emit_log("WARNING", error_msg)
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage("JV-Link接続に失敗しました。設定を確認してください。", 5000)
                return False
        except Exception as e:
            self.emit_log("ERROR", f"JV-Link手動接続中にエラー: {e}")
            return False

    def start_setup_data_acquisition(self):
        """
        セットアップデータ取得を開始（従来のメソッド - 下位互換性のため）
        JVOpen option=4 (セットアップデータ)
        """
        # デフォルトのデータ種別でセットアップを実行
        default_data_types = ["RACE", "SE", "HR", "KS"]
        return self.start_setup_data_acquisition_with_types("19860101", default_data_types)
    
    def start_setup_data_acquisition_with_types(self, from_date: str, selected_data_types: list):
        """
        指定されたデータ種別でセットアップデータ取得を開始
        
        Args:
            from_date: 取得開始日（YYYYMMDD形式）
            selected_data_types: 取得するデータ種別のリスト
        """
        # JV-Link初期化チェック
        if not self.jvlink_manager.is_initialized():
            if not self.connect_jvlink_manually():
                return False

        # データ取得中でないことを確認
        if not self.jvlink_manager.can_start_data_operation():
            error_msg = f"データ取得を開始できません。現在の状態: {
                self.jvlink_manager.current_state.value}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(error_msg, 5000)
            return False

        try:
            self.emit_log("INFO", f"セットアップデータ取得を開始: 開始日={from_date}, データ種別={selected_data_types}")
            self._show_status_message("セットアップデータ取得を開始しています...", 0)

            # オプション4（セットアップデータ）で選択されたデータ種別を取得
            # from_dateが指定されている場合は開始日として使用、空の場合は全期間
            formatted_date = f"{from_date}000000" if from_date else ""
            
            self.jvlink_manager.get_data_async(
                option=4,
                from_date=formatted_date,
                data_spec_list=selected_data_types
            )
            return True

        except Exception as e:
            error_msg = f"セットアップデータ取得開始エラー: {e}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(error_msg, 5000)
            return False

    def start_differential_data_acquisition(self):
        """
        差分データ取得を開始（従来のメソッド - 下位互換性のため）
        JVOpen option=1 (差分データ)
        """
        # デフォルトのデータ種別で差分更新を実行
        default_data_types = ["RACE", "SE", "HR", "KS"]
        return self.start_differential_data_acquisition_with_types(default_data_types)
    
    def start_differential_data_acquisition_with_types(self, selected_data_types: list):
        """
        指定されたデータ種別で差分データ取得を開始
        
        Args:
            selected_data_types: 取得するデータ種別のリスト（例: ["RACE", "SE", "HR"]）
        """
        # JV-Link初期化チェック
        if not self.jvlink_manager.is_initialized():
            if not self.connect_jvlink_manually():
                return False

        # データ取得中でないことを確認
        if not self.jvlink_manager.can_start_data_operation():
            error_msg = f"データ取得を開始できません。現在の状態: {
                self.jvlink_manager.current_state.value}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(error_msg, 5000)
            return False

        try:
            # 最終更新タイムスタンプを取得
            last_timestamp = self.settings_manager.get_last_file_timestamp()
            if not last_timestamp:
                self.emit_log("WARNING", "最終更新タイムスタンプが未設定のため、全データを取得します")
                last_timestamp = ""

            self.emit_log("INFO", f"差分データ取得を開始: タイムスタンプ={last_timestamp}, データ種別={selected_data_types}")
            self._show_status_message("差分データ取得を開始しています...", 0)

            # オプション1（差分データ）で選択されたデータ種別を取得
            self.jvlink_manager.get_data_async(
                option=1,
                from_date=last_timestamp,
                data_spec_list=selected_data_types
            )
            return True

        except Exception as e:
            error_msg = f"差分データ取得開始エラー: {e}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(error_msg, 5000)
            return False

    # === 設定変更通知の処理（新機能）===

    @Slot(dict)
    def on_database_config_updated(self, db_config: dict):
        """
        データベース設定変更通知を受信し、再接続とUI更新を実行 (ループ対策済み)
        
        Args:
            db_config: 更新されたデータベース設定辞書
        """
        # 初期化中は処理をスキップ（無限ループ対策）
        if self._is_initializing:
            return
            
        self.emit_log("INFO", f"データベース設定変更を検知: {db_config.get('type', 'Unknown')} データベース")
        
        # settings_managerからのシグナルを一時的にブロックし、再入を防ぐ
        is_blocked = self.settings_manager.signalsBlocked()
        self.settings_manager.blockSignals(True)
        
        try:
            if not self.db_manager:
                self.emit_log("INFO", "DatabaseManagerを新規作成します")
                self.db_manager = DatabaseManager(self.settings_manager)
            else:
                # 既存のDatabaseManagerで再接続を試行
                self.emit_log("INFO", "既存のDatabaseManagerで再接続を実行中...")
                self.db_manager.reconnect(db_config)
            
            # UI更新と状態確認（この処理が副作用で再保存をトリガーしていた）
            self._update_dashboard_db_info()
            self._ensure_database_tables()
            
            self._show_status_message("データベース設定が正常に更新されました。", 3000)

        except Exception as e:
            critical_error_msg = f"データベース設定更新処理中にエラー: {e}"
            self.emit_log("ERROR", critical_error_msg, {"exception": str(e)})
            self._show_status_message(f"データベース設定更新に失敗しました: {e}", 10000)
            # エラー発生時もUIを更新して状態を反映
            self._update_dashboard_db_info()

        finally:
            # 処理が成功しても失敗しても、必ずシグナルのブロックを解除する
            self.settings_manager.blockSignals(is_blocked)

    def _ensure_database_tables(self):
        """
        データベーステーブルの存在を確認し、必要に応じて作成
        """
        try:
            if self.db_manager and self.db_manager.engine:
                from ..models.tables import Base
                Base.metadata.create_all(self.db_manager.engine)
                self.emit_log("INFO", "データベーステーブルの初期化が完了しました")
        except Exception as e:
            self.emit_log("WARNING", f"テーブル作成エラー: {e}")

    def _show_status_message(self, message: str, timeout: int = 5000):
        """
        ステータスバーにメッセージを表示（ヘルパーメソッド）
        
        Args:
            message: 表示するメッセージ
            timeout: 表示時間（ミリ秒）
        """
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(message, timeout)

    @Slot()
    def on_settings_saved(self):
        """
        設定保存完了通知を受信 (ループ対策済み)
        """
        # 初期化中は処理をスキップ（無限ループ対策）
        if self._is_initializing:
            return
            
        logging.info("設定保存が完了しました。")

        # settings_managerからのシグナルを一時的にブロックし、再入を防ぐ
        is_blocked = self.settings_manager.signalsBlocked()
        self.settings_manager.blockSignals(True)
        
        try:
            # UIの初期設定を再読み込み
            self.load_and_apply_settings()

            # ダッシュボードを更新
            self._update_dashboard_db_info()
            
        except Exception as e:
            self.emit_log("ERROR", f"設定保存後処理中にエラー: {e}")
        
        finally:
            # 処理が成功しても失敗しても、必ずシグナルのブロックを解除する
            self.settings_manager.blockSignals(is_blocked)

    def _update_dashboard_db_info(self):
        """
        ダッシュボードのデータベース接続情報を更新（強化版）
        設定変更後の接続状態確認とUI反映を行う
        """
        try:
            if not hasattr(self.main_window, 'dashboard_view'):
                self.emit_log("WARNING", "ダッシュボードビューが見つかりません")
                return

            if not self.db_manager:
                # DatabaseManagerが存在しない場合
                self.emit_log("WARNING", "DatabaseManagerが存在しません")
                offline_info = {
                    'connected': False,
                    'type': 'オフライン',
                    'name': '未接続',
                    'tables_count': 0,
                    'last_updated': datetime.now().isoformat()
                }
                self.main_window.dashboard_view.update_db_info(offline_info)
                return

            # データベース基本情報を取得
            db_type = self.db_manager.get_db_type() or 'Unknown'
            db_name = self.db_manager.get_db_name() or 'Unknown'
            
            self.emit_log("INFO", f"ダッシュボードDB情報更新: {db_type} - {db_name}")

            # 接続状態の確認
            is_connected = False
            error_message = ""
            
            try:
                if self.db_manager.engine:
                    # エンジンが存在する場合は簡単な接続テストを実行
                    with self.db_manager.engine.connect() as conn:
                        # データベース種別に応じたテストクエリ
                        if db_type.lower() == 'sqlite':
                            conn.execute(text("SELECT sqlite_version()"))
                        elif db_type.lower() == 'mysql':
                            conn.execute(text("SELECT VERSION()"))
                        elif db_type.lower() == 'postgresql':
                            conn.execute(text("SELECT version()"))
                        else:
                            conn.execute(text("SELECT 1"))
                    
                    is_connected = True
                    self.emit_log("INFO", f"データベース接続確認成功: {db_type}")
                    
                else:
                    error_message = "データベースエンジンが初期化されていません"
                    self.emit_log("WARNING", error_message)
                    
            except Exception as conn_error:
                error_message = f"データベース接続テストエラー: {conn_error}"
                self.emit_log("WARNING", error_message)
                is_connected = False

            # テーブル数とデータサマリーを取得
            tables_count = 0
            data_summary = {}
            
            if is_connected:
                try:
                    data_summary = self.db_manager.get_data_summary()
                    tables_count = len(data_summary) if data_summary else 0
                    self.emit_log("INFO", f"データサマリー取得成功: {tables_count}テーブル")
                    
                except Exception as summary_error:
                    error_message = f"データサマリー取得エラー: {summary_error}"
                    self.emit_log("WARNING", error_message)

            # ダッシュボード用のDB情報を構築
            db_info = {
                'connected': is_connected,
                'type': db_type,
                'name': db_name,
                'tables_count': tables_count,
                'last_updated': datetime.now().isoformat(),
                'error_message': error_message if error_message else None
            }

            # ダッシュボードを更新
            self.main_window.dashboard_view.update_db_info(db_info)
            
            # データサマリーも更新（接続されている場合）
            if is_connected and data_summary:
                self.main_window.dashboard_view.update_dashboard_summary(data_summary)

            self.emit_log("INFO", f"ダッシュボードDB情報更新完了: {db_type} ({db_name}) - 接続状態: {is_connected}")

        except Exception as e:
            critical_error_msg = f"ダッシュボードDB情報更新で予期しないエラー: {e}"
            self.emit_log("ERROR", critical_error_msg)

            # クリティカルエラー時のフォールバック情報
            fallback_info = {
                'connected': False,
                'type': 'システムエラー',
                'name': 'N/A',
                'tables_count': 0,
                'last_updated': datetime.now().isoformat(),
                'error_message': str(e)
            }

            try:
                if hasattr(self.main_window, 'dashboard_view'):
                    self.main_window.dashboard_view.update_db_info(fallback_info)
            except Exception as fallback_error:
                self.emit_log("CRITICAL", f"フォールバック情報更新も失敗: {fallback_error}")

    def handle_db_connection_success(self):
        """
        修正点4: データベース接続成功時の処理
        """
        self.emit_log("INFO", "データベース接続が正常に確立されました")
        self._update_dashboard_db_info()

        # 必要に応じてテーブル作成
        try:
            from ..models.tables import Base
            Base.metadata.create_all(self.db_manager.engine)
            self.emit_log("INFO", "データベーステーブルの初期化が完了しました")

            # テーブル作成後、情報を再更新
            self._update_dashboard_db_info()

        except Exception as e:
            self.emit_log("ERROR", f"テーブル作成エラー: {e}")

    def handle_db_connection_error(self, error_message: str):
        """
        修正点4: データベース接続エラー時の処理
        """
        self.emit_log("ERROR", f"データベース接続エラー: {error_message}")

        # エラー状態をダッシュボードに反映
        if hasattr(self.main_window, 'dashboard_view'):
            self.main_window.dashboard_view.show_db_error(str(e))

    # 修正点2: ErrorStateからのシグナルを受信するスロット
    @Slot(str, str)
    def show_error_dialog(self, title: str, message: str):
        """
        修正点2: エラーダイアログを表示するスロット
        UIスレッドで安全に実行される
        """
        from PySide6.QtWidgets import QMessageBox

        # QMessageBoxはUIコンポーネントなので、親ウィジェットを指定するのが望ましい
        QMessageBox.critical(self.main_window, title, message)

        self.emit_log("INFO", f"エラーダイアログ表示: {title}")

    def refresh_db_info(self):
        """
        修正点4: DB情報の手動更新（設定変更後など）
        """
        self.emit_log("INFO", "データベース情報を手動で更新します")
        self._update_dashboard_db_info()

    # === Phase 3: 構造化ログとマルチタスク進捗管理 ===

    @Slot(object)
    def on_structured_log_received(self, log_record: LogRecord):
        """構造化ログレコードを受信して処理"""
        # マスターリストに追加
        self.log_records.append(log_record)

        # ダッシュボードのログビューアに送信
        if hasattr(self.main_window, 'dashboard_view'):
            self.main_window.dashboard_view.add_log_record(log_record)

        # 重要なログレベルの場合は追加処理
        if log_record.level in ['ERROR', 'CRITICAL']:
            self._handle_critical_log(log_record)

    @Slot(object)
    def on_progress_received(self, progress_info: NewProgressInfo):
        """進捗情報を受信して処理"""
        # ダッシュボードのマルチタスク進捗を更新
        if hasattr(self.main_window, 'dashboard_view'):
            dashboard = self.main_window.dashboard_view

            # タスクが未登録の場合は追加
            if progress_info.task_name not in self.active_tasks:
                dashboard.add_task(
                    progress_info.task_name,
                    progress_info.worker_name)
                self.active_tasks[progress_info.task_name] = {
                    'worker_name': progress_info.worker_name,
                    'start_time': datetime.now(),
                    'status': 'running'
                }

            # 進捗を更新
            dashboard.update_task_progress(
                progress_info.task_name,
                progress_info.percentage,
                progress_info.status_message
            )

    @Slot(str, str, str)
    def on_status_received(
            self,
            task_name: str,
            worker_name: str,
            status_message: str):
        """ステータス更新を受信して処理"""
        # ダッシュボードの該当タスクステータスを更新
        if hasattr(self.main_window, 'dashboard_view'):
            # 現在の進捗率を維持してステータスのみ更新
            dashboard = self.main_window.dashboard_view
            if task_name in dashboard.task_widgets:
                current_progress = dashboard.task_widgets[task_name].progress_bar.value(
                )
                dashboard.update_task_progress(
                    task_name, current_progress, status_message)

    @Slot(object)
    def on_task_finished(self, result: TaskResult):
        """タスク完了結果を受信して処理"""
        # アクティブタスクの状態を更新
        if result.task_name in self.active_tasks:
            self.active_tasks[result.task_name]['status'] = 'completed' if result.success else 'error'
            self.active_tasks[result.task_name]['end_time'] = datetime.now()

        # ダッシュボードのタスク完了状態を更新
        if hasattr(self.main_window, 'dashboard_view'):
            self.main_window.dashboard_view.complete_task(
                result.task_name, result.success)

        # 完了ログを記録
        completion_log = LogRecord(
            timestamp=datetime.now(),
            level='INFO' if result.success else 'ERROR',
            task_name=result.task_name,
            worker_name=result.worker_name,
            message=f"タスク完了: {
                result.items_processed}アイテム処理, {
                result.records_written}レコード書き込み, {
                result.processing_time:.2f}秒")
        self.on_structured_log_received(completion_log)

    @Slot(str, str, str)
    def on_error_received(
            self,
            task_name: str,
            worker_name: str,
            error_message: str):
        """エラーを受信して処理"""
        # エラーログを作成
        error_log = LogRecord(
            timestamp=datetime.now(),
            level='ERROR',
            task_name=task_name,
            worker_name=worker_name,
            message=error_message
        )
        self.on_structured_log_received(error_log)

        # タスクの状態を更新
        if task_name in self.active_tasks:
            self.active_tasks[task_name]['status'] = 'error'

        # ダッシュボードのタスクエラー状態を更新
        if hasattr(self.main_window, 'dashboard_view'):
            self.main_window.dashboard_view.update_task_progress(
                task_name, 0, f"エラー: {error_message}")

    def _handle_critical_log(self, log_record: LogRecord):
        """重要なログの追加処理"""
        # エラーダイアログ表示などの処理
        if log_record.level == 'CRITICAL':
            # クリティカルエラーの場合は即座に通知
            logging.critical(
                f"[{log_record.task_name}|{log_record.worker_name}] {log_record.message}")

        # 状態機械への通知（必要に応じて）
        if hasattr(self._state, 'handle_critical_error'):
            self._state.handle_critical_error(log_record)

    def clear_all_tasks(self):
        """すべてのアクティブタスクをクリア"""
        self.active_tasks.clear()
        if hasattr(self.main_window, 'dashboard_view'):
            self.main_window.dashboard_view.clear_all_tasks()
            self.main_window.dashboard_view.clear_logs()

    def get_active_task_summary(self) -> Dict[str, Any]:
        """アクティブタスクのサマリーを取得"""
        total_tasks = len(self.active_tasks)
        completed_tasks = sum(
            1 for task in self.active_tasks.values() if task['status'] == 'completed')
        error_tasks = sum(
            1 for task in self.active_tasks.values() if task['status'] == 'error')
        running_tasks = total_tasks - completed_tasks - error_tasks

        return {
            'total': total_tasks,
            'completed': completed_tasks,
            'error': error_tasks,
            'running': running_tasks
        }

    # === 既存UIメソッドをState Machineパターンに適合（段階的移行）===

    def show_setup_dialog(self):
        """
        セットアップデータ取得設定ダイアログを表示
        ユーザーが日付とデータ種別を選択してからデータ取得を開始
        """
        self.emit_log("INFO", "セットアップデータ取得設定ダイアログを表示します")

        try:
            # 新しいデータ選択ダイアログを表示
            from ..views.data_selection_dialog import DataSelectionDialog
            
            dialog = DataSelectionDialog(mode="setup", parent=self.main_window)
            
            if dialog.exec() == QDialog.Accepted:
                # ダイアログでOKが選択された場合
                selection_summary = dialog.get_selection_summary()
                start_date = selection_summary.get("start_date", "")
                selected_data_types = selection_summary.get("data_types", [])
                
                self.emit_log("INFO", f"セットアップデータ取得設定完了: 開始日={start_date}, データ種別={len(selected_data_types)}種類")
                
                if not selected_data_types:
                    self._show_status_message("データ種別が選択されていません。", 5000)
                    return False
                
                # 選択内容の確認ダイアログ
                data_names = [DataSelectionDialog.get_data_type_name(dt) for dt in selected_data_types]
                confirmation_text = (
                    f"以下の設定でセットアップデータ取得を開始しますか？\n\n"
                    f"開始日: {start_date}\n"
                    f"データ種別: {', '.join(data_names[:5])}"
                    f"{'...' if len(data_names) > 5 else ''} "
                    f"(合計{len(data_names)}種類)\n\n"
                    f"※ 大量のデータをダウンロードするため、時間がかかる場合があります。"
                )
                
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self.main_window,
                    'セットアップデータ取得確認',
                    confirmation_text,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # セットアップデータ取得を開始（統合データ取得フレームワーク使用）
                    return self.start_data_acquisition(
                        mode="setup",
                        from_date=start_date,
                        selected_data_types=selected_data_types
                    )
                else:
                    self.emit_log("INFO", "ユーザーによりセットアップデータ取得がキャンセルされました")
                    return False
            else:
                # ダイアログでキャンセルが選択された場合
                self.emit_log("INFO", "セットアップデータ取得設定がキャンセルされました")
                return False
                
        except Exception as e:
            error_msg = f"セットアップデータ取得設定中にエラー: {e}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(f"設定エラー: {e}", 8000)
            return False

    def start_diff_update(self):
        """
        差分データ更新設定ダイアログを表示
        ユーザーがデータ種別を選択してから差分更新を開始
        """
        self.emit_log("INFO", "差分データ更新設定ダイアログを表示します")

        try:
            # 新しいデータ選択ダイアログを表示
            from ..views.data_selection_dialog import DataSelectionDialog
            
            dialog = DataSelectionDialog(mode="differential", parent=self.main_window)
            
            if dialog.exec() == QDialog.Accepted:
                # ダイアログでOKが選択された場合
                selection_summary = dialog.get_selection_summary()
                selected_data_types = selection_summary.get("data_types", [])
                
                self.emit_log("INFO", f"差分データ更新設定完了: データ種別={len(selected_data_types)}種類")
                
                if not selected_data_types:
                    self._show_status_message("データ種別が選択されていません。", 5000)
                    return False
                
                # 最終更新タイムスタンプを取得
                last_timestamp = self.settings_manager.get_last_file_timestamp()
                if not last_timestamp:
                    warning_msg = "最終更新タイムスタンプが設定されていません。まずセットアップデータを取得することを推奨します。"
                    self.emit_log("WARNING", warning_msg)
                    
                    from PySide6.QtWidgets import QMessageBox
                    reply = QMessageBox.question(
                        self.main_window,
                        '差分更新確認',
                        f"{warning_msg}\n\n続行しますか？",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    
                    if reply != QMessageBox.Yes:
                        return False
                    
                    last_timestamp = ""  # 空の場合は全データ取得
                
                # 選択内容の確認
                data_names = [DataSelectionDialog.get_data_type_name(dt) for dt in selected_data_types]
                confirmation_text = (
                    f"以下の設定で差分データ更新を開始しますか？\n\n"
                    f"最終更新: {last_timestamp or '未設定（全データ取得）'}\n"
                    f"データ種別: {', '.join(data_names[:5])}"
                    f"{'...' if len(data_names) > 5 else ''} "
                    f"(合計{len(data_names)}種類)"
                )
                
                from PySide6.QtWidgets import QMessageBox
                reply = QMessageBox.question(
                    self.main_window,
                    '差分データ更新確認',
                    confirmation_text,
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes  # 差分更新はデフォルトでYes
                )
                
                if reply == QMessageBox.Yes:
                    # 差分データ取得を開始（統合データ取得フレームワーク使用）
                    return self.start_data_acquisition(
                        mode="accumulated",
                        selected_data_types=selected_data_types
                    )
                else:
                    self.emit_log("INFO", "ユーザーにより差分データ更新がキャンセルされました")
                    return False
            else:
                # ダイアログでキャンセルが選択された場合
                self.emit_log("INFO", "差分データ更新設定がキャンセルされました")
                return False
                
        except Exception as e:
            error_msg = f"差分データ更新設定中にエラー: {e}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(f"設定エラー: {e}", 8000)
            return False

    def start_full_setup(self, from_date: str, selected_data_types: list):
        """
        「一括データを取得」の処理を開始する
        
        Args:
            from_date: 取得開始日（YYYYMMDD形式）
            selected_data_types: 取得するデータ種別のリスト
        """
        self.emit_log("INFO", f"一括データ取得を開始: 開始日={from_date}, データ種別数={len(selected_data_types)}")
        
        # 新しいセットアップメソッドを使用
        return self.start_setup_data_acquisition_with_types(from_date, selected_data_types)

    # === State Machineとの互換性のための補助メソッド ===

    def _is_idle_state(self) -> bool:
        """現在の状態がアイドル状態かどうかを判定"""
        return self._state and self._state.name == "Idle"

    def _can_start_processing(self) -> bool:
        """処理開始が可能かどうかを判定"""
        return self._state and self._state._can_start_processing()

    def _can_cancel_processing(self) -> bool:
        """処理キャンセルが可能かどうかを判定"""
        return self._state and self._state._can_cancel_processing()

    # === 既存のエラーハンドリングメソッド（State Machine対応）===

    @Slot(str)
    def on_error_occurred(self, error_message: str):
        """
        JV-Linkエラー発生時の処理

        Args:
            error_message: エラーメッセージ
        """
        logging.error(f"JV-Linkエラーが発生しました: {error_message}")

        # ステータスバーにエラー表示
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(
                f"エラー: {error_message}", 5000)

        # JV-Link状態の確認とリセット
        if hasattr(self.jvlink_manager, 'current_state'):
            current_state = self.jvlink_manager.current_state
            logging.info(f"エラー発生時のJV-Link状態: {current_state.value}")

            # エラー状態の場合は手動でリセットが必要であることを通知
            if current_state.value == "ERROR":
                error_msg = "JV-Linkがエラー状態です。再度接続を試行してください。"
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(error_msg, 8000)

    # === 既存のデータ処理メソッド（State Machine対応）===

    @Slot(list)
    def on_data_received(self, raw_data_list: list):
        """
        JvLinkManagerからデータを受け取った時のスロット。
        データをETLパイプラインに送信する。
        Args:
            raw_data_list: (data_spec, raw_data)のタプルのリスト
        """
        if not raw_data_list:
            logging.info("受信データが空でした。")
            # パイプラインが起動していれば終了マーカーを送信
            if self.etl_pipeline.is_running:
                self.etl_pipeline.finish_production()
            return

        logging.info(f"データ受信: 総件数: {len(raw_data_list)}")

        # パイプラインが実行中でない場合は開始
        if not self.etl_pipeline.is_running:
            # 現在選択されているETLルールを取得
            active_rule_name = self.main_window.etl_setting_view.rule_combo.currentText()
            all_rules = self.settings_manager.load_etl_rules()
            active_rule = all_rules.get(active_rule_name, {})

            self.etl_pipeline.start_pipeline(active_rule)

        # 総処理予定件数を更新
        self.pipeline_total_expected += len(raw_data_list)
        self.pipeline_processed_count = 0

        # データをパイプラインに送信
        for data_spec, raw_data in raw_data_list:
            self.etl_pipeline.add_data(data_spec, raw_data)

        # データ送信完了をマーク
        self.etl_pipeline.finish_production()

    @Slot(str)
    def on_operation_finished(self, last_timestamp: str):
        """
        データ取得操作の完了処理

        Args:
            last_timestamp: 最終ファイルタイムスタンプ
        """
        logging.info(f"データ取得が完了しました。最終タイムスタンプ: {last_timestamp}")

        try:
            # 最終タイムスタンプを設定に保存
            if last_timestamp and last_timestamp != "キャンセル":
                self.settings_manager.update_last_file_timestamp(
                    last_timestamp)
                logging.info(f"最終タイムスタンプを更新しました: {last_timestamp}")

            # ダッシュボードの更新
            if hasattr(self.main_window, 'dashboard_view'):
                summary = self.db_manager.get_data_summary()
                self.main_window.dashboard_view.update_dashboard_summary(
                    summary)

            # データベース情報の更新
            self._update_dashboard_db_info()

            # ステータスバーの更新
            if hasattr(self.main_window, 'statusBar'):
                if last_timestamp == "キャンセル":
                    self.main_window.statusBar().showMessage("データ取得がキャンセルされました。", 3000)
                else:
                    self.main_window.statusBar().showMessage("データ取得が完了しました。", 3000)

        except Exception as e:
            logging.error(f"データ取得完了処理中にエラー: {e}")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(f"完了処理エラー: {e}", 5000)

    # === キャンセル機能（State Machine対応）===

    def cancel_current_operation(self):
        """
        現在実行中の処理をキャンセルする（既存機能との互換性を保持）
        """
        self.request_cancel()

    # === 既存のエクスポート機能（State Machine対応）===

    @Slot(dict)
    def start_export(self, params: dict):
        """ExportViewからのリクエストを受けてエクスポートを開始する"""
        # アイドル状態でない場合は開始しない
        if not self._is_idle_state():
            logging.warning(f"エクスポートは現在実行できません。現在の状態: {self.state_name}")
            return

        logging.info("エクスポート処理の開始をExportManagerに依頼します。")
        self.export_manager.start_export(params)
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage("エクスポートを開始しました...")

    @Slot(str)
    def on_export_finished(self, message: str):
        """エクスポート完了をUIに反映する"""
        logging.info(f"[Export Finished] {message}")
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(message, 5000)

        # State MachineのIDLE状態に戻す
        from ..services.state_machine.states import IdleState
        self.transition_to(IdleState())

    @Slot(str)
    def on_export_error(self, message: str):
        """エクスポートエラーをUIに反映する"""
        logging.error(f"[Export Error] {message}")
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(message, 5000)

        # State MachineのIDLE状態に戻す
        from ..services.state_machine.states import IdleState
        self.transition_to(IdleState())

    # === パイプライン関連メソッド（既存機能との統合）===

    @Slot(str, int)
    def _on_pipeline_item_processed(
            self,
            data_spec: str,
            processed_count: int):
        """パイプラインでアイテムが処理された時のスロット"""
        self.pipeline_processed_count += processed_count

        # 進捗を更新
        if self.pipeline_total_expected > 0:
            progress = min(
                100,
                (self.pipeline_processed_count *
                 100) //
                self.pipeline_total_expected)
            if hasattr(self.main_window, 'dashboard_view'):
                self.main_window.dashboard_view.update_progress(
                    progress, f"処理中: {data_spec}")

        logging.info(
            f"パイプライン処理進捗: {data_spec}, {processed_count} 件処理, " f"合計: {
                self.pipeline_processed_count}/{
                self.pipeline_total_expected}")

    @Slot()
    def _on_pipeline_finished(self):
        """パイプライン処理完了時のスロット"""
        logging.info("ETLパイプラインの処理が完了しました。")

        # 進捗を100%に更新
        if hasattr(self.main_window, 'dashboard_view'):
            self.main_window.dashboard_view.update_progress(100, "ETL処理完了")

        # データサマリーを更新
        summary = self.db_manager.get_data_summary()
        self.main_window.dashboard_view.update_dashboard_summary(summary)

        # パイプライン統計をリセット
        self.pipeline_total_expected = 0
        self.pipeline_processed_count = 0

    @Slot(str)
    def _on_pipeline_error(self, error_message: str):
        """パイプラインでエラーが発生した時のスロット"""
        logging.error(f"ETLパイプラインエラー: {error_message}")

        # State Machineのエラーハンドリングを使用
        error = RuntimeError(f"ETL Pipeline Error: {error_message}")
        context_info = {"source": "EtlPipeline", "message": error_message}

        if self._state:
            self._state.handle_error(error, context_info)
        else:
            # フォールバック：直接エラー状態に遷移
            from ..services.state_machine.states import ErrorState
            self.transition_to(ErrorState(error, context_info))

    def cleanup(self):
        """アプリケーション終了時のクリーンアップ処理"""
        logging.info("クリーンアップ処理を実行します。")

        # 実行中の処理をキャンセル
        if not self._is_idle_state():
            logging.info("実行中の処理をキャンセルしてからクリーンアップします。")
            self.request_cancel()

            # キャンセル完了を待つ（最大3秒）
            import time
            timeout = 3.0
            start_time = time.time()
            while not self._is_idle_state() and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if not self._is_idle_state():
                logging.warning("キャンセル完了を待つのがタイムアウトしました。強制終了します。")

        # ETLパイプラインの停止
        if self.etl_pipeline.is_running:
            self.etl_pipeline.cancel_pipeline()

        self.db_manager.close()
        self.jvlink_manager.close()

    # --- Export Slots ---
    # === データベース設定チェック機能（State Machineで使用）===

    def _check_database_config(self) -> bool:
        """
        データベース設定が適切に設定されているかをチェックする
        Returns:
            bool: 設定が有効な場合True、無効な場合False
        """
        try:
            db_config = self.settings_manager.get_db_config()
            if not db_config:
                self._show_config_error("データベース設定が見つかりません。設定画面で接続情報を設定してください。")
                return False

            db_type = db_config.get('type', '')
            if not db_type:
                self._show_config_error(
                    "データベースの種類が設定されていません。設定画面で接続情報を設定してください。")
                return False

            if db_type == "SQLite":
                db_path = db_config.get('path', '')
                if not db_path or db_path.strip() == '':
                    self._show_config_error(
                        "SQLiteデータベースファイルのパスが設定されていません。設定画面で接続情報を設定してください。")
                    return False
            else:  # MySQL or PostgreSQL
                host = db_config.get('host', '')
                username = db_config.get('username', '')
                db_name = db_config.get('db_name', '')

                if not host or host.strip() == '':
                    self._show_config_error(
                        "データベースのホスト名が設定されていません。設定画面で接続情報を設定してください。")
                    return False
                if not username or username.strip() == '':
                    self._show_config_error(
                        "データベースのユーザー名が設定されていません。設定画面で接続情報を設定してください。")
                    return False
                if not db_name or db_name.strip() == '':
                    self._show_config_error(
                        "データベース名が設定されていません。設定画面で接続情報を設定してください。")
                    return False

            return True

        except Exception as e:
            self._show_config_error(f"データベース設定の確認中にエラーが発生しました: {str(e)}")
            return False

    def _show_config_error(self, message: str):
        """設定エラーメッセージを表示する"""
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.warning(
            self.main_window,
            "設定エラー",
            message
        )
        logging.warning(f"Database config error: {message}")

    # === リアルタイム監視機能（既存機能との統合）===

    @Slot(bool)
    def toggle_realtime_watch(self, is_checked):
        """速報受信の開始/停止を切り替える"""
        if is_checked:
            self.start_realtime_watch()
        else:
            self.stop_realtime_watch()

    def start_realtime_watch(self):
        """速報イベントの監視を開始する"""
        # JV-Linkの初期化状態をチェック
        if not self.jvlink_manager.is_initialized():
            error_msg = "JV-Linkが初期化されていません。まず設定画面からJV-Linkを初期化してください。"
            logging.error(error_msg)
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(error_msg, 5000)

            # 速報ボタンを無効状態に戻す
            if hasattr(self.main_window, 'dashboard_view'):
                self.main_window.dashboard_view.update_realtime_button_state(
                    False)
            return

        # データベースにデータが存在するかチェック
        try:
            summary = self.db_manager.get_data_summary()
            if not summary or all(info.get('count', 0) ==
                                  0 for info in summary.values()):
                error_msg = "データベースにデータが存在しません。まずセットアップまたは差分データを取得してください。"
                logging.warning(error_msg)
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(error_msg, 5000)

                # 速報ボタンを無効状態に戻す
                if hasattr(self.main_window, 'dashboard_view'):
                    self.main_window.dashboard_view.update_realtime_button_state(
                        False)
                return
        except Exception as e:
            logging.error(f"データベース状態確認エラー: {e}")

        logging.info("速報イベントの監視開始を指示します。")
        try:
            self.jvlink_manager.watch_realtime_events_async()
        except Exception as e:
            logging.error(f"速報監視開始エラー: {e}")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(
                    f"速報監視開始エラー: {e}", 5000)

            # 速報ボタンを無効状態に戻す
            if hasattr(self.main_window, 'dashboard_view'):
                self.main_window.dashboard_view.update_realtime_button_state(
                    False)

    def stop_realtime_watch(self):
        """速報イベントの監視を停止する"""
        logging.info("速報イベントの監視停止を指示します。")
        try:
            self.jvlink_manager.stop_watching_events()
        except Exception as e:
            logging.error(f"速報監視停止エラー: {e}")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(
                    f"速報監視停止エラー: {e}", 5000)

    @Slot(list)
    def on_realtime_event_received(self, event_data: list):
        """速報イベント受信後の処理"""
        # data_specはイベントデータ自身から特定する必要がある
        # ここでは仮に 'REALTIME' とする
        data_spec = "REALTIME"
        logging.info(
            f"速報イベントを処理します: Spec={data_spec}, Data length={len(event_data[0])}")

        # ETL処理 (ログ出力のみ)
        transformed_dfs = self.etl_processor.transform(event_data, data_spec)
        logging.info(f"ETL結果: {transformed_dfs.keys()}")

        # DB保存 (ログ出力のみ)
        for table_name, df in transformed_dfs.items():
            logging.info(
                f"テーブル '{table_name}' に {
                    len(df)} 件の速報データを保存します（ログのみ）。")
            # self.db_manager.bulk_insert(table_name, df)

    @Slot()
    def on_realtime_watch_started(self):
        """速報監視開始時の処理"""
        logging.info("UIに監視開始を通知します。")
        self.is_watching_realtime = True
        if hasattr(self.main_window, 'dashboard_view'):
            dashboard = self.main_window.dashboard_view
            if hasattr(dashboard, 'update_realtime_button_state'):
                dashboard.update_realtime_button_state(
                    self.is_watching_realtime)

    @Slot()
    def on_realtime_watch_stopped(self):
        """速報監視停止時の処理"""
        logging.info("UIに監視停止を通知します。")
        self.is_watching_realtime = False
        if hasattr(self.main_window, 'dashboard_view'):
            dashboard = self.main_window.dashboard_view
            if hasattr(dashboard, 'update_realtime_button_state'):
                dashboard.update_realtime_button_state(
                    self.is_watching_realtime)

    # === 進捗更新機能（既存機能との統合）===

    @Slot(int)
    def on_progress_updated(self, percent: int):
        """データ取得の進捗をUIに反映する"""
        logging.info(f"データ取得進捗: {percent}%")

        # State Machineに進捗情報を通知
        if self._state:
            progress_info = {
                "percent": percent,
                "message": f"データ取得中... {percent}%"}
            self._state.handle_progress_update(progress_info)

        # UIに進捗を反映
        if hasattr(self.main_window, 'dashboard_view'):
            dashboard = self.main_window.dashboard_view
            if hasattr(dashboard, 'update_progress'):
                dashboard.update_progress(percent, f"データ取得中... {percent}%")

        # ステータスメッセージも更新
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(f"データ取得中... {percent}%")

    # === エクスポート進捗機能 ===

    @Slot(str)
    def on_export_progress(self, message: str):
        """エクスポートの進捗をUIに反映する"""
        logging.info(f"[Export Progress] {message}")
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(message)

    # === 設定管理機能（既存機能との統合）===

    @Slot(dict)
    def save_settings(self, settings: dict):
        """
        SettingsViewから受け取った設定を保存する
        JV-Link設定はJVSetUIProperties()で直接レジストリに保存されるため除外
        """
        try:
            self.emit_log("INFO", "設定が保存されました。適用処理を開始します。")
            
            # データベース設定の更新
            if 'database' in settings:
                db_config = settings['database']
                
                # SettingsManagerで設定を更新
                self.settings_manager.update_db_config(**db_config)
                logging.info("データベース設定が更新されました。")
                
                # データベース設定を更新し、再接続を試行
                success, message = self.db_manager.reconnect(db_config)
                
                # ダッシュボードのDB情報を常に更新して最新の状態を反映
                self._update_dashboard_db_info()
                
                if success:
                    self._show_status_message("データベース設定が正常に適用されました。", 5000)
                else:
                    # 再接続失敗時にエラーダイアログを表示
                    self.show_error_message_box("データベース再接続失敗", message)

            # その他の設定（データベース以外）
            for section, section_data in settings.items():
                if section not in ['database'] and isinstance(
                        section_data, dict):
                    for key, value in section_data.items():
                        self.settings_manager.set_value(
                            section, key, str(value))

            logging.info("設定が正常に保存されました。")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage("設定を保存しました。", 3000)

        except Exception as e:
            logging.error(f"設定の保存中にエラーが発生: {e}")
            self.show_error_message_box("設定保存エラー", f"設定の保存中にエラーが発生しました: {e}")
            if hasattr(self.main_window, 'statusBar'):
                self.main_window.statusBar().showMessage(f"設定保存エラー: {e}", 5000)

    @Slot(dict)
    def test_db_connection(self, db_settings: dict):
        """
        データベース接続テストを実行し、結果をUIに表示する

        存在しないデータベースの場合は作成確認ダイアログを表示
        """
        logging.info(f"データベース接続テストを開始します: {db_settings.get('type')}")

        # show_create_dialog=True でダイアログ表示を有効化
        success, message = self.db_manager.test_connection(
            db_settings, show_create_dialog=True)

        if hasattr(self.main_window, 'settings_view'):
            self.main_window.settings_view.show_test_result(success, message)

    def load_and_apply_settings(self):
        """設定を読み込み、各コンポーネントに適用する"""
        settings = self.settings_manager.get_all()
        if hasattr(self.main_window, 'settings_view'):
            self.main_window.settings_view.set_current_settings(settings)

        # 必要に応じて他のマネージャーにも設定を適用
        self.db_manager.reconnect(settings.get('database'))

        # ETL Rules
        self.load_and_set_etl_rules()

    # === ETL設定管理機能 ===

    @Slot(str, dict)
    def save_etl_rule(self, rule_name: str, rule_data: dict):
        """ETLルールを保存する"""
        self.settings_manager.save_etl_rule(rule_name, rule_data)
        self.load_and_set_etl_rules()  # UIを更新
        if hasattr(self.main_window, 'etl_setting_view'):
            self.main_window.etl_setting_view.rule_combo.setCurrentText(
                rule_name)
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(
                f"ETLルール '{rule_name}' を保存しました。", 3000)

    @Slot(str)
    def delete_etl_rule(self, rule_name: str):
        """ETLルールを削除する"""
        self.settings_manager.delete_etl_rule(rule_name)
        self.load_and_set_etl_rules()  # UIを更新
        if hasattr(self.main_window, 'statusBar'):
            self.main_window.statusBar().showMessage(
                f"ETLルール '{rule_name}' を削除しました。", 3000)

    def load_and_set_etl_rules(self):
        """保存されているETLルールを読み込み、UIにセットする"""
        rules = self.settings_manager.load_etl_rules()
        if hasattr(self.main_window, 'etl_setting_view'):
            self.main_window.etl_setting_view.set_rules(rules)

    @Slot(str)
    def on_etl_rule_selected(self, rule_name: str):
        """ETLルールが選択されたときに、ルール詳細をUIに反映する"""
        if rule_name and rule_name != "＜新規作成＞":
            rules = self.settings_manager.load_etl_rules()
            rule_data = rules.get(rule_name)
            if rule_data and hasattr(self.main_window, 'etl_setting_view'):
                self.main_window.etl_setting_view.set_rule_data(rule_data)

    # === State Machine統合のためのデバッグ機能 ===

    def get_debug_info(self) -> dict:
        """デバッグ情報を取得"""
        return {
            "current_state": self.state_name,
            "can_start_processing": self._can_start_processing(),
            "can_cancel_processing": self._can_cancel_processing(),
            "is_idle": self._is_idle_state(),
            "pipeline_running": self.etl_pipeline.is_running if hasattr(
                self.etl_pipeline,
                'is_running') else False,
            "realtime_watching": self.is_watching_realtime,
            "current_data_specs": self.current_data_specs}

    def _initialize_pipeline_coordinator(self) -> PipelineCoordinator:
        """
        PipelineCoordinatorを初期化

        Returns:
            PipelineCoordinator: 初期化されたコーディネーター
        """
        try:
            # パイプライン設定の取得
            pipeline_config = self._get_pipeline_configuration()

            # PipelineCoordinator作成
            coordinator = PipelineCoordinator(
                jvlink_manager=self.jvlink_manager,
                etl_processor=self.etl_processor,
                db_manager=self.db_manager,
                settings_manager=self.settings_manager,
                progress_callback=self._on_worker_progress,
                error_callback=self._on_worker_error,
                pipeline_config=pipeline_config
            )

            logging.info("PipelineCoordinator initialized successfully")
            return coordinator

        except Exception as e:
            logging.error(f"Failed to initialize PipelineCoordinator: {e}")
            # フォールバック: 基本設定でリトライ
            try:
                coordinator = PipelineCoordinator(
                    jvlink_manager=self.jvlink_manager,
                    etl_processor=self.etl_processor,
                    db_manager=self.db_manager,
                    settings_manager=self.settings_manager,
                    progress_callback=self._on_worker_progress,
                    error_callback=self._on_worker_error
                )
                logging.warning(
                    "PipelineCoordinator initialized with fallback configuration")
                return coordinator
            except Exception as fallback_error:
                logging.critical(
                    f"Critical: PipelineCoordinator initialization failed: {fallback_error}")
                raise

    def _get_pipeline_configuration(self) -> dict:
        """
        パイプライン設定を取得

        Returns:
            dict: パイプライン設定
        """
        try:
            # Settings Managerから設定を取得
            config = self.settings_manager.get_all_settings()

            # パフォーマンス設定の抽出
            pipeline_config = {
                'raw_queue_size': config.get(
                    'pipeline_raw_queue_size', 1000), 'processed_queue_size': config.get(
                    'pipeline_processed_queue_size', 500), 'etl_batch_size': config.get(
                    'pipeline_etl_batch_size', 10), 'db_batch_size': config.get(
                    'pipeline_db_batch_size', 100), 'db_commit_interval': config.get(
                        'pipeline_db_commit_interval', 1000)}

            logging.info(f"Pipeline configuration loaded: {pipeline_config}")
            return pipeline_config

        except Exception as e:
            logging.warning(f"Failed to load pipeline configuration: {e}")
            # デフォルト設定を返す
            default_config = {
                'raw_queue_size': 1000,
                'processed_queue_size': 500,
                'etl_batch_size': 10,
                'db_batch_size': 100,
                'db_commit_interval': 1000
            }
            logging.info(
                f"Using default pipeline configuration: {default_config}")
            return default_config

    def _on_worker_progress(self, progress: ProgressInfo) -> None:
        """
        Worker からの進捗更新を処理

        Args:
            progress: Worker進捗情報
        """
        try:
            # State Machine に進捗を通知
            if self._state:
                self._state.handle_progress_update(progress)

            # UI への進捗反映
            self._update_ui_progress(progress)

            # 詳細ログ（デバッグレベル）
            logging.debug(
                f"Worker progress: {progress.worker_name} - {progress.percentage:.1f}% "
                f"({progress.current_item}/{progress.total_items}) - {progress.message}"
            )

        except Exception as e:
            logging.error(f"Error handling worker progress: {e}")

    def _on_worker_error(self, worker_name: str, error: Exception) -> None:
        """
        Worker からのエラーを処理

        Args:
            worker_name: エラーが発生したワーカー名
            error: 発生したエラー
        """
        try:
            logging.error(f"Worker error from {worker_name}: {error}")

            # State Machine にエラーを通知
            if self._state:
                self._state.handle_pipeline_error(worker_name, error)

            # UI にエラー表示
            self._update_ui_error(worker_name, error)

        except Exception as e:
            logging.critical(f"Critical error in worker error handler: {e}")

    def _update_ui_progress(self, progress: ProgressInfo) -> None:
        """
        UIに進捗情報を反映

        Args:
            progress: 進捗情報
        """
        try:
            if self.main_window:
                # Dashboard View の進捗更新
                if hasattr(self.main_window, 'dashboard_view'):
                    dashboard = self.main_window.dashboard_view
                    if hasattr(dashboard, 'update_progress'):
                        dashboard.update_progress(
                            progress.percentage, progress.message)

                # ステータスバーの更新
                if hasattr(self.main_window, 'statusBar'):
                    status_message = f"{
                        progress.worker_name}: {
                        progress.message}"
                    self.main_window.statusBar().showMessage(status_message)

        except Exception as e:
            logging.debug(f"UI progress update failed: {e}")

    def _update_ui_error(self, worker_name: str, error: Exception) -> None:
        """
        UIにエラー情報を表示

        Args:
            worker_name: エラーが発生したワーカー名
            error: 発生したエラー
        """
        try:
            if self.main_window:
                # エラーダイアログまたは通知の表示
                error_message = f"ワーカー '{worker_name}' でエラーが発生しました:\n{
                    str(error)}"

                # ステータスバーにエラー表示
                if hasattr(self.main_window, 'statusBar'):
                    self.main_window.statusBar().showMessage(
                        f"エラー: {error_message}")

                # Dashboard View にエラー表示
                if hasattr(self.main_window, 'dashboard_view'):
                    dashboard = self.main_window.dashboard_view
                    if hasattr(dashboard, 'show_error'):
                        dashboard.show_error(error_message)

        except Exception as e:
            logging.debug(f"UI error update failed: {e}")

    def start_high_performance_pipeline(
            self,
            data_params: dict,
            etl_rules: dict = None) -> bool:
        """
        高性能 Worker Pipeline を開始

        Args:
            data_params: データ取得パラメータ
            etl_rules: ETL処理ルール

        Returns:
            bool: 開始に成功した場合 True
        """
        try:
            # 新しい高性能状態に遷移
            from ..services.state_machine.pipeline_states import PipelineProcessingState

            # ETLルールの準備
            if etl_rules is None:
                etl_rules = self._get_default_etl_rules()

            # PipelineProcessingState に遷移
            pipeline_state = PipelineProcessingState(data_params, etl_rules)
            self.transition_to(pipeline_state)

            logging.info("High-performance pipeline started successfully")
            return True

        except Exception as e:
            logging.error(f"Failed to start high-performance pipeline: {e}")
            return False

    def _get_default_etl_rules(self) -> dict:
        """
        デフォルトETLルールを取得

        Returns:
            dict: ETLルール
        """
        return {
            'data_validation': True,
            'duplicate_check': True,
            'auto_commit': True,
            'batch_processing': True
        }

    def get_pipeline_performance_stats(self) -> dict:
        """
        パイプラインのパフォーマンス統計を取得

        Returns:
            dict: パフォーマンス統計
        """
        try:
            if self.pipeline_coordinator:
                return self.pipeline_coordinator.get_pipeline_stats()
            else:
                logging.warning("PipelineCoordinator not available for stats")
                return {}
        except Exception as e:
            logging.error(f"Failed to get pipeline stats: {e}")
            return {}

    def is_high_performance_mode(self) -> bool:
        """
        高性能モードかどうかを判定

        Returns:
            bool: 高性能モードの場合 True
        """
        try:
            if self._state:
                return "PipelineProcessing" in self._state.name
            return False
        except Exception:
            return False

    def open_jvlink_settings_dialog(self):
        """JV-Link設定ダイアログを開く"""
        logging.info("JV-Link公式設定ダイアログを開きます。")

        try:
            # JV-Linkマネージャーが利用可能かチェック
            if not hasattr(self.jvlink_manager,
                           'jvlink') or self.jvlink_manager.jvlink is None:
                # JV-Linkが初期化されていない場合、COMオブジェクトのみ作成
                try:
                    import win32com.client
                    import pythoncom

                    # 一時的にCOMオブジェクトを作成
                    pythoncom.CoInitialize()
                    jvlink_temp = win32com.client.Dispatch("JVDTLab.JVLink")

                    # JV-Link設定ダイアログを開く
                    result = jvlink_temp.JVSetUIProperties()

                    # リソース解放
                    jvlink_temp = None
                    pythoncom.CoUninitialize()

                except Exception as com_error:
                    logging.error(f"JV-Link COMオブジェクトの作成に失敗: {com_error}")
                    error_msg = ("JV-Link設定ダイアログを開くことができませんでした。\n\n"
                                 "JV-Linkが正しくインストールされているか確認してください。\n"
                                 f"エラー詳細: {com_error}")
                    if hasattr(self.main_window, 'settings_view'):
                        self.main_window.settings_view.show_jvlink_dialog_result(
                            False, error_msg)
                    return
            else:
                # JV-Linkが既に初期化されている場合
                result = self.jvlink_manager.jvlink.JVSetUIProperties()

            # 結果の判定
            if result == 0:
                success_msg = ("JV-Link設定が正常に完了しました。\n\n"
                               "設定はWindowsレジストリに保存され、"
                               "次回のデータ取得時に自動的に使用されます。")
                logging.info("JV-Link設定ダイアログが正常に完了しました。")
                if hasattr(self.main_window, 'settings_view'):
                    self.main_window.settings_view.show_jvlink_dialog_result(
                        True, success_msg)
            elif result == -100:
                cancel_msg = "JV-Link設定がキャンセルされました。"
                logging.info("JV-Link設定ダイアログがキャンセルされました。")
                if hasattr(self.main_window, 'settings_view'):
                    self.main_window.settings_view.show_jvlink_dialog_result(
                        False, cancel_msg)
            else:
                error_msg = f"JV-Link設定でエラーが発生しました。エラーコード: {result}"
                logging.error(f"JV-Link設定ダイアログでエラー: {result}")
                if hasattr(self.main_window, 'settings_view'):
                    self.main_window.settings_view.show_jvlink_dialog_result(
                        False, error_msg)

        except Exception as e:
            logging.error(f"JV-Link設定ダイアログの開催中にエラー: {e}")
            error_msg = f"予期しないエラーが発生しました: {e}"
            if hasattr(self.main_window, 'settings_view'):
                self.main_window.settings_view.show_jvlink_dialog_result(
                    False, error_msg)

    # === 統合データ取得フレームワーク（報告書フェーズ1.2実装） ===
    
    def start_data_acquisition(self, mode: str, from_date: str = "", selected_data_types: list = None) -> bool:
        """
        統合データ取得フレームワーク
        
        EveryDB2と同等の機能を提供する統一的なデータ取得インターフェース
        
        Args:
            mode: データ取得モード ('setup', 'accumulated', 'realtime')
            from_date: 取得開始日（YYYYMMDD形式、setupモードで使用）
            selected_data_types: 取得するデータ種別のリスト
            
        Returns:
            bool: 取得開始の成功/失敗
        """
        # デフォルトデータ種別の設定
        if selected_data_types is None:
            if mode == 'setup':
                selected_data_types = ["RACE", "SE", "HR", "UM", "KS"]  # セットアップ推奨
            elif mode == 'accumulated':
                selected_data_types = ["RACE", "SE", "HR"]  # 差分更新推奨
            elif mode == 'realtime':
                selected_data_types = ["RACE", "SE"]  # 当該週データ
            else:
                raise ValueError(f"不正なデータ取得モード: {mode}")
        
        # JV-Linkパラメータのマッピング（報告書表1に基づく）
        if mode == 'setup':
            return self._execute_setup_acquisition(from_date, selected_data_types)
        elif mode == 'accumulated':
            return self._execute_accumulated_acquisition(selected_data_types)
        elif mode == 'realtime':
            return self._execute_realtime_acquisition(selected_data_types)
        else:
            error_msg = f"サポートされていないデータ取得モード: {mode}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(error_msg, 5000)
            return False
    
    def _execute_setup_acquisition(self, from_date: str, selected_data_types: list) -> bool:
        """
        セットアップデータ取得の実行（JVOpen option=4）
        
        Args:
            from_date: 取得開始日（YYYYMMDD形式）
            selected_data_types: データ種別リスト
        """
        try:
            # JV-Link初期化チェック
            if not self.jvlink_manager.is_initialized():
                if not self.connect_jvlink_manually():
                    return False

            # データ取得中でないことを確認
            if not self.jvlink_manager.can_start_data_operation():
                error_msg = f"データ取得を開始できません。現在の状態: {self.jvlink_manager.current_state.value}"
                self.emit_log("ERROR", error_msg)
                self._show_status_message(error_msg, 5000)
                return False

            self.emit_log("INFO", f"セットアップデータ取得開始: 開始日={from_date}, データ種別={selected_data_types}")
            self._show_status_message("セットアップデータ取得を開始しています...", 0)

            # fromtimeパラメータの設定（報告書仕様に従い）
            formatted_date = f"{from_date}000000" if from_date else "19860101000000"
            
            self.jvlink_manager.get_data_async(
                option=4,  # セットアップデータ（ダイアログ無し）
                from_date=formatted_date,
                data_spec_list=selected_data_types
            )
            return True

        except Exception as e:
            error_msg = f"セットアップデータ取得開始エラー: {e}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(error_msg, 5000)
            return False
    
    def _execute_accumulated_acquisition(self, selected_data_types: list) -> bool:
        """
        蓄積系（差分）データ取得の実行（JVOpen option=1）
        
        Args:
            selected_data_types: データ種別リスト
        """
        try:
            # JV-Link初期化チェック
            if not self.jvlink_manager.is_initialized():
                if not self.connect_jvlink_manually():
                    return False

            # データ取得中でないことを確認
            if not self.jvlink_manager.can_start_data_operation():
                error_msg = f"データ取得を開始できません。現在の状態: {self.jvlink_manager.current_state.value}"
                self.emit_log("ERROR", error_msg)
                self._show_status_message(error_msg, 5000)
                return False

            self.emit_log("INFO", f"蓄積系データ取得開始: データ種別={selected_data_types}")
            self._show_status_message("蓄積系データ取得を開始しています...", 0)

            self.jvlink_manager.get_data_async(
                option=1,  # 通常データ（差分更新）
                data_spec_list=selected_data_types
            )
            return True

        except Exception as e:
            error_msg = f"蓄積系データ取得開始エラー: {e}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(error_msg, 5000)
            return False
    
    def _execute_realtime_acquisition(self, selected_data_types: list) -> bool:
        """
        速報系データ取得の実行（JVOpen option=2）
        
        Args:
            selected_data_types: データ種別リスト
        """
        try:
            # JV-Link初期化チェック
            if not self.jvlink_manager.is_initialized():
                if not self.connect_jvlink_manually():
                    return False

            # データ取得中でないことを確認
            if not self.jvlink_manager.can_start_data_operation():
                error_msg = f"データ取得を開始できません。現在の状態: {self.jvlink_manager.current_state.value}"
                self.emit_log("ERROR", error_msg)
                self._show_status_message(error_msg, 5000)
                return False

            self.emit_log("INFO", f"速報系データ取得開始: データ種別={selected_data_types}")
            self._show_status_message("速報系データ取得を開始しています...", 0)

            # 当該週の開始日時を計算（日曜日開始）
            from datetime import datetime, timedelta
            today = datetime.now()
            days_since_sunday = today.weekday() + 1  # 月曜日=0なので+1で日曜日基準に
            sunday = today - timedelta(days=days_since_sunday)
            week_start = sunday.strftime("%Y%m%d") + "000000"

            self.jvlink_manager.get_data_async(
                option=2,  # 今週データ
                from_date=week_start,
                data_spec_list=selected_data_types
            )
            return True

        except Exception as e:
            error_msg = f"速報系データ取得開始エラー: {e}"
            self.emit_log("ERROR", error_msg)
            self._show_status_message(error_msg, 5000)
            return False

    # === ユーザー通知ヘルパーメソッド ===

    def show_error_message_box(self, title: str, message: str):
        """
        ユーザーにエラーメッセージボックスを表示する
        
        Args:
            title: エラーダイアログのタイトル
            message: エラーメッセージの内容
        """
        try:
            from PySide6.QtWidgets import QMessageBox
            
            if self.main_window:
                QMessageBox.critical(self.main_window, title, message)
            else:
                # メインウィンドウが利用できない場合はログに記録
                self.emit_log("ERROR", f"{title}: {message}")
                
        except Exception as e:
            # GUI表示に失敗した場合はログにフォールバック
            self.emit_log("ERROR", f"エラーメッセージ表示失敗 - {title}: {message} (原因: {e})")
