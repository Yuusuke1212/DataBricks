"""
ダッシュボードビュー - レポート セクション3.1準拠

アプリケーション起動時の情報ハブとして、
システムの健全性と最新状況を直感的かつ迅速に把握できる画面
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
from PySide6.QtCore import Signal, Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QSizePolicy,
    QScrollArea,
    QFrame,
    QListWidget,
    QListWidgetItem,
)
from PySide6.QtGui import QFont, QPainter, QPen, QBrush, QColor

# QFluentWidgets components - レポート セクション3.1準拠
from qfluentwidgets import (
    TitleLabel,
    SubtitleLabel,
    CardWidget,
    PrimaryPushButton,
    PushButton,
    ProgressRing,
    StrongBodyLabel,
    BodyLabel,
    CaptionLabel,
    ScrollArea,
    InfoBar,
    InfoBarPosition,
)
from qfluentwidgets import FluentIcon as FIF

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
    ダッシュボードビュー - レポート セクション3.1準拠
    
    アプリケーションの情報ハブとして以下の機能を提供：
    - JV-Linkステータス表示
    - 最終同期情報表示
    - クイックアクション
    - アクティビティログ
    """
    
    # シグナル定義
    quick_action_requested = Signal(str)  # クイックアクション要求

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("DashboardView")
        self.theme_manager = get_theme_manager()
        
        # 状態管理
        self.jvlink_status = "unknown"
        self.last_sync_info = None
        self.recent_activities = []
        
        # 更新タイマー
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self._update_realtime_info)
        self.update_timer.start(30000)  # 30秒間隔で更新
        
        self._init_ui()
        self._load_initial_data()

    def _init_ui(self):
        """レポート セクション3.1: ダッシュボードレイアウトの実装"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        # タイトル
        title = TitleLabel("ホーム", self)
        layout.addWidget(title)

        # スクロール可能エリア
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)  # ExpandLayoutをQVBoxLayoutに変更
        scroll_layout.setSpacing(20)
        
        # QGridLayoutで情報モジュールを配置
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)
        
        # 第1行: JV-Linkステータス + 最終同期情報
        self._create_jvlink_status_card(grid_layout, 0, 0)
        self._create_last_sync_card(grid_layout, 0, 1)
        
        # 第2行: クイックアクション + アクティビティログ
        self._create_quick_actions_card(grid_layout, 1, 0)
        self._create_activity_log_card(grid_layout, 1, 1)
        
        scroll_layout.addLayout(grid_layout)
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

    def _create_jvlink_status_card(self, grid_layout, row: int, col: int):
        """JV-Linkステータスカード"""
        self.jvlink_card = CardWidget()
        card_layout = QVBoxLayout(self.jvlink_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        # カードタイトル
        title = StrongBodyLabel("🔗 JV-Link ステータス")
        card_layout.addWidget(title)
        
        # ステータス表示エリア
        status_layout = QHBoxLayout()
        
        self.jvlink_indicator = StatusIndicator("unknown")
        self.jvlink_status_label = BodyLabel("初期化中...")
        
        status_layout.addWidget(self.jvlink_indicator)
        status_layout.addWidget(self.jvlink_status_label)
        status_layout.addStretch()
        
        card_layout.addLayout(status_layout)
        
        # 詳細情報
        self.jvlink_details = CaptionLabel("サービスキー: 未設定")
        self.jvlink_details.setWordWrap(True)
        card_layout.addWidget(self.jvlink_details)
        
        grid_layout.addWidget(self.jvlink_card, row, col)

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

    def _create_quick_actions_card(self, grid_layout, row: int, col: int):
        """クイックアクションカード"""
        self.actions_card = CardWidget()
        card_layout = QVBoxLayout(self.actions_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # カードタイトル
        title = StrongBodyLabel("⚡ クイックアクション")
        card_layout.addWidget(title)
        
        description = CaptionLabel("よく使う操作をワンクリックで実行")
        card_layout.addWidget(description)
        
        # アクションボタン群
        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(8)
        
        # 差分データ取得
        self.diff_data_btn = PrimaryPushButton("差分データを取得")
        self.diff_data_btn.setIcon(FIF.DOWNLOAD)
        self.diff_data_btn.clicked.connect(lambda: self.quick_action_requested.emit("get_diff_data"))
        actions_layout.addWidget(self.diff_data_btn)
        
        # 今週データ取得
        self.week_data_btn = PushButton("今週データを取得")
        self.week_data_btn.setIcon(FIF.CALENDAR)
        self.week_data_btn.clicked.connect(lambda: self.quick_action_requested.emit("get_week_data"))
        actions_layout.addWidget(self.week_data_btn)
        
        # データエクスポート
        self.export_btn = PushButton("データをエクスポート")
        self.export_btn.setIcon(FIF.SHARE)
        self.export_btn.clicked.connect(lambda: self.quick_action_requested.emit("export_data"))
        actions_layout.addWidget(self.export_btn)
        
        card_layout.addLayout(actions_layout)
        grid_layout.addWidget(self.actions_card, row, col)

    def _create_activity_log_card(self, grid_layout, row: int, col: int):
        """アクティビティログカード"""
        self.activity_card = CardWidget()
        card_layout = QVBoxLayout(self.activity_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # カードタイトル
        title = StrongBodyLabel("📝 最近のアクティビティ")
        card_layout.addWidget(title)
        
        # アクティビティリスト
        self.activity_list = QListWidget()
        self.activity_list.setFixedHeight(200)
        card_layout.addWidget(self.activity_list)
        
        # 詳細ログボタン
        self.detail_log_btn = PushButton("詳細ログを表示")
        self.detail_log_btn.setIcon(FIF.DOCUMENT)
        self.detail_log_btn.clicked.connect(self._show_detail_log)
        card_layout.addWidget(self.detail_log_btn)
        
        grid_layout.addWidget(self.activity_card, row, col)

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
        self.jvlink_indicator.set_status(status)
        
        status_messages = {
            "connected": "接続済み",
            "disconnected": "未接続",
            "warning": "警告",
            "unknown": "不明"
        }
        
        self.jvlink_status_label.setText(status_messages.get(status, "不明"))
        if details:
            self.jvlink_details.setText(details)

    def update_data_count(self, count: int):
        """データ件数を更新"""
        self.data_count_label.setText(f"レコード数: {count:,}件")

    def add_activity_log(self, action: str, status: str):
        """外部からアクティビティログを追加"""
        self._add_activity(action, status)

    def update_progress(self, percent: int):
        """進捗更新（メインウィンドウから呼び出される）"""
        if percent > 0:
            self._add_activity("データ取得", f"進捗 {percent}%")

    def on_theme_changed(self, theme):
        """テーマ変更時の処理"""
        # テーマに応じてカードのスタイルを調整
        pass
