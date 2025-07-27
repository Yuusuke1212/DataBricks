from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QStackedWidget, QLabel, QHBoxLayout, QStatusBar
from qfluentwidgets import (NavigationInterface, NavigationItemPosition, MessageBox,
                            SubtitleLabel, setTheme, Theme, FluentWindow, NavigationAvatarWidget,
                            setFont, TitleLabel, InfoBar, InfoBarPosition, BodyLabel)
from qfluentwidgets import FluentIcon as FIF

from .dashboard_view import DashboardView
from .setup_dialog import SetupDialog
from .export_view import ExportView
from .settings_view import SettingsView
from .etl_setting_view import EtlSettingView
from typing import Optional


class CustomStatusBar(QStatusBar):
    """FluentWindow用のカスタムステータスバー"""

    def __init__(self, parent: Optional['QWidget'] = None):
        # QStatusBarの適切な初期化
        super().__init__(parent)
        self.initUI()
        self.message_timer = QTimer()
        self.message_timer.setSingleShot(True)
        self.message_timer.timeout.connect(self.clearMessage)

    def initUI(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        self.status_label = BodyLabel("Ready", self)
        self.status_label.setStyleSheet("""
            QLabel {
                color: #888;
                font-size: 12px;
                padding: 2px 5px;
            }
        """)

        layout.addWidget(self.status_label)
        layout.addStretch()

        # ステータスバーのスタイル
        self.setStyleSheet("""
            CustomStatusBar {
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)
        self.setFixedHeight(25)

    def showMessage(self, message: str, timeout: int = 0):
        """メッセージを表示"""
        self.status_label.setText(message)

        if timeout > 0:
            self.message_timer.start(timeout)

    def clearMessage(self):
        """メッセージをクリア"""
        self.status_label.setText("Ready")


class MainWindow(FluentWindow):

    def __init__(self, app_controller=None):
        super().__init__()
        self.app_controller = app_controller

        self.initWindow()
        self.initStatusBar()
        # app_controllerがNoneでもUIの骨格だけは作れるようにする
        if self.app_controller:
            self.initialize_views()

    def initialize_views(self):
        """依存関係のあるViewを初期化する"""
        if not self.app_controller:
            return

        print("  ↳ DashboardView 作成前")
        self.dashboard_view = DashboardView(self)
        print("  ↳ DashboardView 作成後")

        print("  ↳ SetupDialog 作成前")
        self.setup_dialog = SetupDialog(self)
        print("  ↳ SetupDialog 作成後")

        print("  ↳ ExportView 作成前")
        self.export_view = ExportView(
            self.app_controller.db_manager.get_table_names(), self)
        print("  ↳ ExportView 作成後")

        print("  ↳ SettingsView 作成前")
        self.settings_view = SettingsView(self)
        print("  ↳ SettingsView 作成後")

        print("  ↳ EtlSettingView 作成前")
        self.etl_setting_view = EtlSettingView(
            self.app_controller.db_manager, self)
        print("  ↳ EtlSettingView 作成後")

        print("  ↳ initNavigation() 呼び出し前")
        self.initNavigation()
        print("  ↳ initNavigation() 呼び出し後")

    def _icon(self, attr: str, fallback: str = "MORE"):
        """Return icon attr if exists else fallback icon."""
        return getattr(FIF, attr, getattr(FIF, fallback))

    def initNavigation(self):
        """ナビゲーション項目をセットアップする"""
        self.addSubInterface(self.dashboard_view,
                             self._icon("DASHBOARD"), 'ダッシュボード')
        self.addSubInterface(
            self.export_view, self._icon("SAVE_AS"), 'データエクスポート')
        self.addSubInterface(self.etl_setting_view,
                             self._icon("EDIT"), 'ETL設定')
        self.navigationInterface.addSeparator()
        self.addSubInterface(self.settings_view, self._icon(
            "SETTING"), 'アプリ設定', position=NavigationItemPosition.BOTTOM)

    def initialize_connections(self):
        """コントローラーとのシグナル接続を行う"""
        if not self.app_controller:
            return
        # このメソッドは、main.pyでcontrollerの初期化が終わった後に呼び出される
        self.app_controller.initialize_connections()

    def initWindow(self):
        self.resize(1200, 900)
        # ウィンドウアイコンとタイトル
        if hasattr(FIF, "DATABASE"):
            self.setWindowIcon(FIF.DATABASE.icon())
        else:
            # 古い qfluentwidgets には DATABASE が無い場合がある
            # 代替として SAVE_AS アイコンを使用
            self.setWindowIcon(FIF.SAVE_AS.icon())

        self.setWindowTitle("JRA-Data Collector")

        # Fluent Design アプリケーションのスタイル設定
        setTheme(Theme.DARK)
        self.navigationInterface.setAcrylicEnabled(True)
        self.navigationInterface.setExpandWidth(200)

        # ウィンドウを画面中央に配置
        desktop = self.screen().availableGeometry()
        w, h = desktop.width(), desktop.height()
        self.move(w // 2 - self.width() // 2, h // 2 - self.height() // 2)

        # ステータスバーのスタイル調整は initStatusBar() で実行

    def initStatusBar(self):
        """カスタムステータスバーを初期化"""
        self.custom_status_bar = CustomStatusBar(self)
        self.custom_status_bar.showMessage("JRA-Data Collector へようこそ")

        # FluentWindowの下部に配置するため、適切な親ウィジェットを見つけて配置
        # 最も安全な方法: 固定位置に配置し、ウィンドウサイズに合わせて調整
        self.custom_status_bar.setParent(self)
        self.positionStatusBar()

    def positionStatusBar(self):
        """ステータスバーを適切な位置に配置"""
        if hasattr(self, 'custom_status_bar'):
            # ウィンドウの下端にステータスバーを配置
            status_height = 25
            self.custom_status_bar.setGeometry(
                0,
                self.height() - status_height,
                self.width(),
                status_height
            )
            self.custom_status_bar.show()

    def resizeEvent(self, event):
        """ウィンドウサイズ変更時にステータスバーの位置を調整"""
        super().resizeEvent(event)
        self.positionStatusBar()

    def statusBar(self):
        """標準のstatusBar()メソッドを模倣"""
        return self.custom_status_bar

    def update_progress(self, percent: int):
        """プログレスバーの進捗率を更新する"""
        if hasattr(self, 'dashboard_view') and self.dashboard_view:
            self.dashboard_view.update_progress(percent)

    def show_error_dialog(self, error_message: str):
        """エラーダイアログを表示する"""
        from qfluentwidgets import MessageBox
        MessageBox(
            "エラー",
            error_message,
            self
        ).exec()

    def show_critical_error_dialog(self, title: str, message: str):
        """重大なエラーダイアログを表示する"""
        from qfluentwidgets import MessageBox
        MessageBox(
            title,
            message,
            self
        ).exec()

    def addSubInterface(self, widget: QWidget, icon, text: str, position=NavigationItemPosition.TOP):
        self.stackedWidget.addWidget(widget)
        self.navigationInterface.addItem(
            routeKey=widget.objectName(),
            icon=icon,
            text=text,
            onClick=lambda: self.switchTo(widget),
            position=position,
            tooltip=text
        )

    def switchTo(self, widget):
        self.stackedWidget.setCurrentWidget(widget)
