"""
ダッシュボードビュー - UI/UX改善指示書準拠
情報ハブとしての役割を強化し、視覚的な階層と操作性を最適化。
"""

from datetime import datetime
from PySide6.QtCore import Signal, Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QScrollArea,
    QListWidgetItem,
    QTextEdit, # Added QTextEdit for activity log
)
from PySide6.QtGui import QPainter, QPen, QBrush, QColor

# QFluentWidgets components - UI/UX改善指示書準拠
from qfluentwidgets import (
    TitleLabel, CardWidget, PrimaryPushButton, PushButton, StrongBodyLabel, BodyLabel, CaptionLabel, ScrollArea, InfoBadge,
    InfoBar, InfoBarPosition, FluentIcon as FIF
)

from ..utils.theme_manager import get_theme_manager


class StatusIndicator(QWidget):
    """ステータス表示用インジケーター"""

    def __init__(self, status: str = "unknown", parent=None):
        super().__init__(parent)
        self.status = status
        self.setFixedSize(12, 12)

    def set_status(self, status: str):
        """ステータスを更新"""
        self.status = status
        self.update()

    def paintEvent(self, event):
        """ステータスに応じた色の円を描画"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # ステータスに応じた色設定
        colors = {
            "connected": "#39D85A",    # 緑（正常）
            "disconnected": "#FF5252", # 赤（エラー）
            "warning": "#FFD700",      # 黄（警告）
            "unknown": "#BDBDBD"       # グレー（不明）
        }

        color = colors.get(self.status, colors["unknown"])
        painter.setBrush(QBrush(QColor(color)))
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.drawEllipse(0, 0, 12, 12)


class DashboardView(QWidget):
    """
    ダッシュボードビュー - UI/UX改善指示書準拠
    情報ハブとしての役割を強化し、視覚的な階層と操作性を最適化。
    """

    # シグナル定義
    quick_action_requested = Signal(str)  # クイックアクション要求
    diff_button_clicked = Signal()  # 差分データ取得ボタン
    full_button_clicked = Signal()  # 全データ取得ボタン
    realtime_toggled = Signal(bool)  # リアルタイム監視切り替え
    active_database_changed = Signal(str)  # アクティブデータベース変更

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardView")
        self.theme_manager = get_theme_manager()

        # 状態管理
        self.jvlink_status = "unknown"
        self.last_sync_info = None
        self.recent_activities = []
        self.pending_activities = []

        # 更新タイマー
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_realtime_info)
        self.update_timer.start(30000)  # 30秒間隔で更新

        self._init_ui()
        self._load_initial_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(36, 20, 36, 12)
        title_label = TitleLabel("ホーム", title_container)
        title_layout.addWidget(title_label)
        layout.addWidget(title_container)

        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(36, 8, 36, 24)
        scroll_layout.setSpacing(16)
        scroll_widget.setObjectName("DashboardScrollWidget")
        scroll_area.setWidget(scroll_widget)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(16)

        self._create_database_card(grid_layout, 0, 0)
        self._create_jvlink_status_card(grid_layout, 0, 1)
        self._create_last_sync_card(grid_layout, 0, 2)

        self._create_quick_actions_card(grid_layout, 1, 0, 1, 3)
        self._create_activity_log_card(grid_layout, 2, 0, 1, 3)

        scroll_layout.addLayout(grid_layout)

    def _create_database_card(self, grid_layout, row, col):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.addWidget(StrongBodyLabel("💾 データベース"))

        self.db_info_label = BodyLabel("未接続")
        self.db_info_label.setWordWrap(True)
        layout.addWidget(self.db_info_label)

        self.db_connect_btn = PrimaryPushButton("データベース設定")
        self.db_connect_btn.setMinimumHeight(32)
        self.db_connect_btn.setIcon(FIF.SETTING)
        self.db_connect_btn.clicked.connect(self._show_database_settings)
        layout.addWidget(self.db_connect_btn)
        grid_layout.addWidget(card, row, col)

    def _create_jvlink_status_card(self, grid_layout, row, col):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.addWidget(StrongBodyLabel("🔗 JV-Link ステータス"))
        header_layout.addStretch()
        self.jvlink_badge_container = QWidget(card)
        self.jvlink_badge_layout = QHBoxLayout(self.jvlink_badge_container)
        self.jvlink_badge_layout.setContentsMargins(0,0,0,0)
        self.jvlink_badge = InfoBadge.info("不明")
        self.jvlink_badge_layout.addWidget(self.jvlink_badge)
        header_layout.addWidget(self.jvlink_badge_container)
        layout.addLayout(header_layout)

        self.jvlink_details = CaptionLabel("起動処理中です...")
        self.jvlink_details.setWordWrap(True)
        layout.addWidget(self.jvlink_details)
        grid_layout.addWidget(card, row, col)

    def _create_last_sync_card(self, grid_layout, row: int, col: int):
        """最終同期情報カード"""
        self.sync_card = CardWidget()
        card_layout = QVBoxLayout(self.sync_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        # カードタイトル
        title = StrongBodyLabel("📅 最終データ同期")
        card_layout.addWidget(title)

        # 同期情報表示
        self.last_sync_label = BodyLabel("同期情報を取得中...")
        card_layout.addWidget(self.last_sync_label)

        self.data_count_label = CaptionLabel("レコード数: --")
        card_layout.addWidget(self.data_count_label)

        # 同期実行ボタン
        self.sync_button = PushButton("同期状況を更新")
        self.sync_button.setIcon(FIF.SYNC)
        self.sync_button.clicked.connect(self._refresh_sync_info)
        card_layout.addWidget(self.sync_button)

        grid_layout.addWidget(self.sync_card, row, col)

    def _create_quick_actions_card(self, grid_layout, row, col, rowspan, colspan):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("⚡ クイックアクション"))

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)

        self.diff_data_btn = PrimaryPushButton("差分データを取得")
        self.diff_data_btn.setMinimumHeight(32)
        self.diff_data_btn.setIcon(FIF.DOWNLOAD)
        self.diff_data_btn.clicked.connect(self._on_diff_button_clicked)

        self.week_data_btn = PushButton("今週データを取得")
        self.week_data_btn.setMinimumHeight(32)
        self.week_data_btn.setIcon(FIF.CALENDAR)
        self.week_data_btn.clicked.connect(lambda: self.quick_action_requested.emit("get_week_data"))

        self.export_btn = PushButton("データを出力")
        self.export_btn.setMinimumHeight(32)
        self.export_btn.setIcon(FIF.SHARE)
        self.export_btn.clicked.connect(lambda: self.quick_action_requested.emit("export_data"))

        actions_layout.addWidget(self.diff_data_btn)
        actions_layout.addWidget(self.week_data_btn)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addStretch()
        layout.addLayout(actions_layout)
        grid_layout.addWidget(card, row, col, rowspan, colspan)

    def _create_activity_log_card(self, grid_layout, row, col, rowspan, colspan):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("📝 最近のアクティビティ"))

        self.activity_log = QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMinimumHeight(150)
        self.activity_log.setObjectName("ActivityLog")

        for entry in self.pending_activities:
            self.activity_log.append(entry)
        self.pending_activities = []

        layout.addWidget(self.activity_log)
        grid_layout.addWidget(card, row, col, rowspan, colspan)

    def _load_initial_data(self):
        """初期データの読み込み"""
        self._refresh_sync_info()
        self._add_activity("アプリケーション起動", "正常")

    @Slot()
    def _refresh_sync_info(self):
        """同期情報を更新"""
        # TODO: 実際のDBから最終同期情報を取得
        # 現在はダミーデータ
        self.last_sync_label.setText("最終同期: 2024年1月27日 19:30")
        self.data_count_label.setText("レコード数: 1,234件")

    def _update_realtime_info(self):
        """リアルタイム情報の更新"""
        # TODO: JV-Linkステータスの実際の確認
        pass

    def _add_activity(self, action: str, status: str):
        """アクティビティを追加"""
        timestamp = datetime.now().strftime("%H:%M")
        activity_text = f"{timestamp} - {action}: {status}"

        # リストの先頭に追加
        self.recent_activities.insert(0, activity_text)

        # 最大10件まで保持
        if len(self.recent_activities) > 10:
            self.recent_activities = self.recent_activities[:10]

        self._update_activity_display()

    def _update_activity_display(self):
        """アクティビティ表示を更新"""
        self.activity_list.clear()
        for activity in self.recent_activities:
            item = QListWidgetItem(activity)
            self.activity_list.addItem(item)

    def _show_database_settings(self):
        """データベース設定ダイアログを表示"""
        try:
            from PySide6.QtWidgets import QMessageBox

            # TODO: 実際のデータベース設定ダイアログを実装
            # 現在はプレースホルダーとしてメッセージボックスを表示
            QMessageBox.information(
                self,
                "データベース設定",
                "データベース設定機能は実装中です。\n設定画面からデータベース設定を行ってください。"
            )

            # 将来的にはここで実際の設定ダイアログを表示
            # self.database_settings_requested.emit()

        except Exception as e:
            logging.error(f"データベース設定表示エラー: {e}")

    def update_database_info(self, db_info: dict):
        """データベース情報を更新"""
        try:
            db_type = db_info.get('type', 'Unknown')
            db_host = db_info.get('host', 'localhost')
            db_name = db_info.get('db_name', 'unknown')

            # データベース情報ラベルを更新
            if hasattr(self, 'db_info_label'):
                self.db_info_label.setText(f"データベース: {db_type} ({db_host}:{db_name})")

        except Exception as e:
            logging.error(f"データベース情報更新エラー: {e}")

    def _show_detail_log(self):
        """詳細ログの表示"""
        # TODO: 詳細ログビューアーを開く
        InfoBar.info(
            title="詳細ログ",
            content="詳細ログビューアーは今後のバージョンで実装されます。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def update_jvlink_status(self, status: str, details: str = ""):
        """JV-Linkステータスを更新"""
        self.jvlink_status = status

        try:
            status_map = {
                "connected": ("success", "接続済み"),
                "disconnected": ("error", "未接続"),
                "warning": ("warning", "警告"),
                "unknown": ("info", "不明")
            }
            badge_type, status_text = status_map.get(status, ("info", "不明"))

            if hasattr(self, 'jvlink_badge') and self.jvlink_badge:
                self.jvlink_badge.deleteLater()

            badge_method = getattr(InfoBadge, badge_type)
            self.jvlink_badge = badge_method(status_text)
            self.jvlink_badge_layout.addWidget(self.jvlink_badge)

            if details:
                self.jvlink_details.setText(details)
        except Exception as e:
            logging.error(f"JV-Linkステータス更新エラー: {e}")

    def update_data_count(self, count: int):
        """データ件数を更新"""
        self.data_count_label.setText(f"レコード数: {count:,}件")

    def add_activity_log(self, action: str, status: str):
        """外部からアクティビティログを追加"""
        try:
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_entry = f"[{timestamp}] {action}: {status}"

            if hasattr(self, 'activity_log'):
                self.activity_log.append(log_entry)
            else:
                self.pending_activities.append(log_entry)

        except Exception as e:
            logging.error(f"アクティビティログ追加エラー: {e}")

    def update_progress(self, percent: int):
        """進捗更新（メインウィンドウから呼び出される）"""
        if percent > 0:
            self._add_activity("データ取得", f"進捗 {percent}%")

    def _on_diff_button_clicked(self):
        """差分データ取得ボタンがクリックされたときの処理"""
        try:
            logging.info("差分データ取得ボタンがクリックされました")
            self.diff_button_clicked.emit()
            self.quick_action_requested.emit("get_diff_data")
        except Exception as e:
            logging.error(f"差分データ取得ボタン処理エラー: {e}")

    def _on_full_button_clicked(self):
        """全データ取得ボタンがクリックされたときの処理"""
        try:
            logging.info("全データ取得ボタンがクリックされました")
            self.full_button_clicked.emit()
            self.quick_action_requested.emit("get_full_data")
        except Exception as e:
            logging.error(f"全データ取得ボタン処理エラー: {e}")

    def _on_realtime_toggled(self):
        """リアルタイム監視切り替えボタンがクリックされたときの処理"""
        try:
            # ボタンの状態を切り替え
            current_text = self.realtime_btn.text()
            is_on = "OFF" in current_text

            if is_on:
                self.realtime_btn.setText("リアルタイム監視: ON")
                play_icon = getattr(FIF, 'PLAY', None)
                if play_icon:
                    self.realtime_btn.setIcon(play_icon)
            else:
                self.realtime_btn.setText("リアルタイム監視: OFF")
                pause_icon = getattr(FIF, 'PAUSE', None)
                if pause_icon:
                    self.realtime_btn.setIcon(pause_icon)

            logging.info(f"リアルタイム監視切り替え: {'ON' if is_on else 'OFF'}")
            self.realtime_toggled.emit(is_on)

        except Exception as e:
            logging.error(f"リアルタイム監視切り替えエラー: {e}")

    def on_theme_changed(self, theme):
        """テーマ変更時の処理（将来拡張用）"""
        try:
            logging.debug(f"ダッシュボードでテーマが変更されました: {theme}")
        except Exception as e:
            logging.error(f"テーマ変更処理エラー: {e}")

    def update_dashboard_summary(self, summary: dict):
        """ダッシュボードサマリーの更新メソッド - AppControllerから呼び出される"""
        try:
            if not summary:
                return

            # データベース情報の更新
            if 'database' in summary:
                self.update_database_info(summary['database'])

            # JV-Link状態の更新
            if 'jvlink_status' in summary:
                self.update_jvlink_status(summary['jvlink_status'])

            # アクティビティログの更新
            if 'recent_activities' in summary:
                for activity in summary['recent_activities']:
                    self.add_activity_log(activity.get('action', ''), activity.get('status', ''))

            logging.debug("ダッシュボードサマリー更新完了")

        except Exception as e:
            logging.error(f"ダッシュボードサマリー更新エラー: {e}")

    def update_summary(self, summary: dict):
        """サマリー情報でダッシュボードを更新"""
        logging.debug(f"ダッシュボードサマリー受信: {summary}")
        try:
            if not summary:
                return

            # データベース情報の更新
            if 'database' in summary:
                self.update_database_info(summary['database'])

            # JV-Link状態の更新
            if 'jvlink_status' in summary:
                self.update_jvlink_status(summary['jvlink_status'])

            # アクティビティログの更新
            if 'recent_activities' in summary:
                for activity in summary['recent_activities']:
                    self.add_activity_log(activity.get('action', ''), activity.get('status', ''))

            logging.debug("ダッシュボードサマリー更新完了")

        except Exception as e:
            logging.error(f"ダッシュボードサマリー更新エラー: {e}")

    def refresh_summary(self):
        """サマリー情報をリフレッシュ"""
        try:
            # リフレッシュ処理の実装
            logging.debug("ダッシュボードサマリーをリフレッシュしています")
            # 実際のリフレッシュロジックはAppControllerから呼び出される

        except Exception as e:
            logging.error(f"サマリーリフレッシュエラー: {e}")

    def __getattr__(self, name):
        """
        未実装メソッドの動的ハンドリング - method missing パターン
        
        参考: https://keegoo.github.io/notes/2018/03/12/method-missing-in-python.html
        """
        def _method_missing(*args, **kwargs):
            logging.warning(f"DashboardView: 未実装メソッド '{name}' が呼び出されました")
            logging.debug(f"引数: args={args}, kwargs={kwargs}")

            # ダッシュボードビュー固有の未実装メソッド処理
            if name.startswith('update_') or name.startswith('refresh_'):
                logging.info(f"表示更新メソッド '{name}' の呼び出しをスキップしました")
                return True
            elif name.startswith('get_') or name.startswith('fetch_'):
                logging.info(f"データ取得メソッド '{name}' は空の結果を返しました")
                return {}
            elif name.endswith('_clicked') or name.endswith('_toggled'):
                logging.info(f"イベントメソッド '{name}' は None を返しました")
                return None
            elif name.startswith('add_') or name.startswith('set_'):
                logging.info(f"設定メソッド '{name}' の呼び出しをスキップしました")
                return True
            else:
                logging.info(f"その他のメソッド '{name}' は None を返しました")
                return None

        return _method_missing
