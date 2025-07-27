from PyQt5.QtCore import pyqtSignal as Signal, Qt, QPropertyAnimation, QEasingCurve
# Widgets
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QSizePolicy,
    QScrollArea,
    QProgressBar,
    QFrame,
    QSplitter,
)
from PyQt5.QtGui import QPainter, QPen, QBrush, QFont
from PyQt5.QtCore import QRect

# QFluentWidgets components
from qfluentwidgets import (
    SubtitleLabel,
    CardWidget,
    PrimaryPushButton,
    PushButton,
    ToggleButton,
    ProgressRing,
    StrongBodyLabel,
    BodyLabel,
    CaptionLabel,
)
from qfluentwidgets import FluentIcon as FIF

from .setup_dialog import SetupDialog
from .log_viewer_widget import LogViewerWidget

# 構造化ログレコードのインポート
from ..services.workers.signals import LogRecord

# DashboardView
# ------------------------------------------------------------


class TaskProgressWidget(QFrame):
    """
    個別タスクの進捗を表示するウィジェット

    タスク名、ステータス、プログレスバーを含む複合ウィジェット
    """

    def __init__(self, task_name: str, worker_name: str, parent=None):
        super().__init__(parent)
        self.task_name = task_name
        self.worker_name = worker_name
        self.setFrameStyle(QFrame.Box)
        self.setFixedHeight(80)
        self.setStyleSheet("""
            TaskProgressWidget {
                border: 1px solid #e0e0e0;
                border-radius: 6px;
                background-color: #fafafa;
                margin: 2px;
            }
            TaskProgressWidget:hover {
                background-color: #f0f0f0;
            }
        """)

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # ヘッダー行: タスク名とワーカー名
        header_layout = QHBoxLayout()

        self.task_label = StrongBodyLabel(self.task_name)
        self.worker_label = CaptionLabel(f"[{self.worker_name}]")
        self.worker_label.setStyleSheet("color: #666666;")

        header_layout.addWidget(self.task_label)
        header_layout.addStretch()
        header_layout.addWidget(self.worker_label)

        # ステータス行: ステータステキストと進捗率
        status_layout = QHBoxLayout()

        self.status_label = BodyLabel("待機中")
        self.status_label.setStyleSheet("color: #808080;")

        self.progress_text = CaptionLabel("0%")
        self.progress_text.setStyleSheet("color: #666666; font-weight: bold;")

        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.progress_text)

        # プログレスバー
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 3px;
                background-color: #e0e0e0;
            }
            QProgressBar::chunk {
                border-radius: 3px;
                background-color: #0078d4;
            }
        """)

        layout.addLayout(header_layout)
        layout.addLayout(status_layout)
        layout.addWidget(self.progress_bar)

    def update_progress(self, percentage: int, status_message: str):
        """進捗とステータスを更新"""
        self.progress_bar.setValue(max(0, min(100, percentage)))
        self.progress_text.setText(f"{percentage}%")
        self.status_label.setText(status_message)

        # ステータスに応じて色を変更
        if "エラー" in status_message or "失敗" in status_message:
            self.status_label.setStyleSheet("color: #d13438;")
            self.setStyleSheet(self.styleSheet() + """
                TaskProgressWidget { border-color: #d13438; background-color: #fdf2f2; }
            """)
        elif "完了" in status_message:
            self.status_label.setStyleSheet("color: #107c10;")
            self.setStyleSheet(self.styleSheet() + """
                TaskProgressWidget { border-color: #107c10; background-color: #f3f9f1; }
            """)
        elif percentage > 0:
            self.status_label.setStyleSheet("color: #0078d4;")


class DonutProgressWidget(QWidget):
    """
    ドーナツ型の統合進捗インジケータ

    全タスクの平均進捗を表示し、滑らかなアニメーションを提供
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(120, 120)
        self._value = 0
        self._target_value = 0

        # アニメーション
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value
        self.update()

    value = property(get_value, set_value)

    def setValue(self, target_value):
        """アニメーション付きで値を設定"""
        if target_value != self._target_value:
            self._target_value = target_value
            self.animation.setStartValue(self._value)
            self.animation.setEndValue(target_value)
            self.animation.start()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRect(10, 10, 100, 100)

        # 背景の円
        painter.setPen(QPen(Qt.lightGray, 8))
        painter.drawEllipse(rect)

        # 進捗の円弧
        if self._value > 0:
            painter.setPen(QPen(Qt.blue, 8))
            start_angle = 90 * 16  # 上から開始
            span_angle = -int((self._value / 100.0) * 360 * 16)  # 時計回り
            painter.drawArc(rect, start_angle, span_angle)

        # 中央のテキスト
        painter.setPen(Qt.black)
        font = QFont()
        font.setPointSize(16)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, f"{int(self._value)}%")


class DashboardView(CardWidget):
    """
    ダッシュボード画面。
    データ取得状況のサマリーや、処理のトリガーとなるボタンを配置する。

    Phase 3 Update: 動的マルチタスク進捗ダッシュボード統合
    """
    full_setup_requested = Signal(str)  # *現在未使用*（将来、ダイアログ内で日付を選択し返す用途）
    diff_button_clicked = Signal()      # 差分取得ボタン押下
    full_button_clicked = Signal()      # 一括取得ボタン押下
    realtime_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('DashboardView')

        # タスク進捗管理
        self.task_widgets = {}  # task_name -> TaskProgressWidget
        self.total_tasks = 0
        self.completed_tasks = 0

        # === Page Header ===
        self.vBoxLayout = QVBoxLayout(self)
        self.titleLabel = SubtitleLabel("データ同期", self)

        # Operation buttons with improved styling
        self.diff_button = PrimaryPushButton(FIF.SYNC, "差分データを取得", self)
        self.diff_button.setFixedHeight(40)
        self.full_button = PushButton(FIF.DOWNLOAD, "一括データを取得", self)
        self.full_button.setFixedHeight(40)
        self.realtime_button = ToggleButton(FIF.PLAY, "速報受信開始", self)
        self.realtime_button.setFixedHeight(40)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.titleLabel)
        header_layout.addStretch(1)
        header_layout.addWidget(self.diff_button)
        header_layout.addWidget(self.full_button)
        header_layout.addWidget(self.realtime_button)

        # === Content area ===
        content_layout = QHBoxLayout()

        # Left: Data status card with improved styling
        self.status_card = CardWidget(self)
        status_card_title = StrongBodyLabel("📊 データ取得状況", self.status_card)
        status_layout = QVBoxLayout(self.status_card)
        status_layout.addWidget(status_card_title)
        status_layout.addSpacing(8)

        self.table = QTableWidget(0, 3, self.status_card)
        self.table.setHorizontalHeaderLabels(["データ種別", "レコード数", "最新日時"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.table.setAlternatingRowColors(True)
        status_layout.addWidget(self.table)

        # Right: Dynamic Multi-Task Progress Dashboard
        self.progress_card = CardWidget(self)
        self.progress_card.setFixedWidth(320)
        progress_card_title = StrongBodyLabel(
            "⚡ マルチタスク処理状況", self.progress_card)
        progress_layout = QVBoxLayout(self.progress_card)
        progress_layout.addWidget(progress_card_title)
        progress_layout.addSpacing(8)

        # 統合進捗インジケータ
        overall_layout = QHBoxLayout()
        self.donut_progress = DonutProgressWidget(self.progress_card)

        overall_info_layout = QVBoxLayout()
        self.overall_status_label = StrongBodyLabel("待機中", self.progress_card)
        self.task_count_label = BodyLabel("0 / 0 タスク", self.progress_card)
        self.task_count_label.setStyleSheet("color: #666666;")

        overall_info_layout.addWidget(self.overall_status_label)
        overall_info_layout.addWidget(self.task_count_label)
        overall_info_layout.addStretch()

        overall_layout.addWidget(self.donut_progress)
        overall_layout.addLayout(overall_info_layout)
        overall_layout.addStretch()

        progress_layout.addLayout(overall_layout)
        progress_layout.addSpacing(12)

        # 個別タスク進捗エリア (スクロール可能)
        tasks_title = BodyLabel("個別タスク:", self.progress_card)
        tasks_title.setStyleSheet("font-weight: bold; color: #333333;")
        progress_layout.addWidget(tasks_title)

        self.tasks_scroll_area = QScrollArea(self.progress_card)
        self.tasks_scroll_area.setWidgetResizable(True)
        self.tasks_scroll_area.setFixedHeight(200)
        self.tasks_scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                background-color: #ffffff;
            }
        """)

        self.tasks_container = QWidget()
        self.tasks_layout = QVBoxLayout(self.tasks_container)
        self.tasks_layout.setContentsMargins(4, 4, 4, 4)
        self.tasks_layout.setSpacing(4)
        self.tasks_layout.addStretch()  # 初期状態では下部にスペース

        self.tasks_scroll_area.setWidget(self.tasks_container)
        progress_layout.addWidget(self.tasks_scroll_area)

        # Assemble content layout
        content_layout.addWidget(self.status_card, stretch=3)
        content_layout.addSpacing(12)
        content_layout.addWidget(self.progress_card, stretch=1)

        # 修正点4: データベース接続情報カードを追加
        self.db_info_card = self._create_db_info_card()
        content_layout.addWidget(self.db_info_card, stretch=1)

        # Root layout
        self.vBoxLayout.addLayout(header_layout)
        self.vBoxLayout.addSpacing(12)

        # メインコンテンツを分割（上：データ状況・進捗、下：ログビューア）
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.setHandleWidth(8)
        main_splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #e0e0e0;
                border-radius: 2px;
            }
            QSplitter::handle:hover {
                background-color: #c0c0c0;
            }
        """)

        # 上部：既存のコンテンツエリア
        content_widget = QWidget()
        content_widget.setLayout(content_layout)
        main_splitter.addWidget(content_widget)

        # 下部：ログビューアエリア
        self.log_viewer = LogViewerWidget()
        main_splitter.addWidget(self.log_viewer)

        # 分割比率を設定（上部70%, 下部30%）
        main_splitter.setSizes([700, 300])

        self.vBoxLayout.addWidget(main_splitter, stretch=1)

        # === Connections ===
        self.diff_button.clicked.connect(self.diff_button_clicked)
        self.full_button.clicked.connect(self.full_button_clicked)
        self.realtime_button.toggled.connect(self.realtime_toggled)

        # ログビューア接続
        self.log_viewer.log_exported.connect(self._on_log_exported)

    def _create_db_info_card(self) -> CardWidget:
        """
        修正点4: データベース接続情報表示カードを作成
        """
        db_card = CardWidget(self)
        db_card.setFixedWidth(280)

        # カードタイトル
        db_card_title = StrongBodyLabel("🗄️ データベース接続", db_card)

        # レイアウト
        db_layout = QVBoxLayout(db_card)
        db_layout.addWidget(db_card_title)
        db_layout.addSpacing(8)

        # 接続状態表示
        status_layout = QHBoxLayout()
        status_layout.addWidget(BodyLabel("接続状態:"))
        self.db_status_label = BodyLabel("未接続")
        self.db_status_label.setStyleSheet(
            "color: #d13438; font-weight: bold;")  # 初期状態は赤
        status_layout.addWidget(self.db_status_label)
        status_layout.addStretch()
        db_layout.addLayout(status_layout)

        # データベースタイプ表示
        type_layout = QHBoxLayout()
        type_layout.addWidget(BodyLabel("タイプ:"))
        self.db_type_label = BodyLabel("未設定")
        self.db_type_label.setStyleSheet("color: #666666;")
        type_layout.addWidget(self.db_type_label)
        type_layout.addStretch()
        db_layout.addLayout(type_layout)

        # データベース名表示
        name_layout = QHBoxLayout()
        name_layout.addWidget(BodyLabel("名前:"))
        self.db_name_label = BodyLabel("未設定")
        self.db_name_label.setStyleSheet("color: #666666;")
        name_layout.addWidget(self.db_name_label)
        name_layout.addStretch()
        db_layout.addLayout(name_layout)

        # テーブル数表示
        tables_layout = QHBoxLayout()
        tables_layout.addWidget(BodyLabel("テーブル数:"))
        self.db_tables_label = BodyLabel("0")
        self.db_tables_label.setStyleSheet("color: #666666;")
        tables_layout.addWidget(self.db_tables_label)
        tables_layout.addStretch()
        db_layout.addLayout(tables_layout)

        # 最終更新時刻表示
        updated_layout = QHBoxLayout()
        updated_layout.addWidget(BodyLabel("最終更新:"))
        self.db_updated_label = CaptionLabel("未更新")
        self.db_updated_label.setStyleSheet("color: #999999;")
        updated_layout.addWidget(self.db_updated_label)
        updated_layout.addStretch()
        db_layout.addLayout(updated_layout)

        # 空白を追加してバランス調整
        db_layout.addStretch()

        return db_card

    # ------------------------------------------------------------------
    # Multi-Task Progress Management
    # ------------------------------------------------------------------

    def add_task(self, task_name: str, worker_name: str):
        """新しいタスクを進捗ダッシュボードに追加"""
        if task_name not in self.task_widgets:
            task_widget = TaskProgressWidget(task_name, worker_name)
            self.task_widgets[task_name] = task_widget

            # スクロールエリアに追加 (最後のstretchの前に挿入)
            self.tasks_layout.insertWidget(
                self.tasks_layout.count() - 1, task_widget)
            self.total_tasks += 1
            self._update_task_count()

    def update_task_progress(self, task_name: str, percentage: int, status_message: str):
        """個別タスクの進捗を更新"""
        if task_name in self.task_widgets:
            self.task_widgets[task_name].update_progress(
                percentage, status_message)
            self._update_overall_progress()

    def complete_task(self, task_name: str, success: bool):
        """タスクの完了を記録"""
        if task_name in self.task_widgets:
            status = "完了" if success else "エラー"
            self.task_widgets[task_name].update_progress(
                100 if success else 0, status)
            if success:
                self.completed_tasks += 1
            self._update_overall_progress()
            self._update_task_count()

    def clear_all_tasks(self):
        """すべてのタスクをクリア"""
        for widget in self.task_widgets.values():
            self.tasks_layout.removeWidget(widget)
            widget.deleteLater()

        self.task_widgets.clear()
        self.total_tasks = 0
        self.completed_tasks = 0
        self._update_overall_progress()
        self._update_task_count()

    def _update_overall_progress(self):
        """統合進捗インジケータを更新"""
        if not self.task_widgets:
            self.donut_progress.setValue(0)
            self.overall_status_label.setText("待機中")
            return

        total_progress = sum(
            widget.progress_bar.value()
            for widget in self.task_widgets.values()
        )
        overall_percentage = total_progress / \
            len(self.task_widgets) if self.task_widgets else 0

        self.donut_progress.setValue(int(overall_percentage))

        if overall_percentage == 100:
            self.overall_status_label.setText("すべて完了")
        elif overall_percentage > 0:
            self.overall_status_label.setText("処理中...")
        else:
            self.overall_status_label.setText("開始待機中")

    def _update_task_count(self):
        """タスク数表示を更新"""
        self.task_count_label.setText(
            f"{self.completed_tasks} / {self.total_tasks} タスク完了")

    # ------------------------------------------------------------------
    # Log Viewer Integration
    # ------------------------------------------------------------------

    def add_log_record(self, log_record: LogRecord):
        """ログレコードをログビューアに追加"""
        self.log_viewer.add_log_record(log_record)

    def add_log_records(self, log_records: list):
        """複数のログレコードを一括追加"""
        self.log_viewer.add_log_records(log_records)

    def clear_logs(self):
        """ログビューアのログをクリア"""
        self.log_viewer.clear_logs()

    def _on_log_exported(self, message: str):
        """ログエクスポート完了時の処理"""
        # ステータスバーやトーストでメッセージを表示
        if hasattr(self.parent(), 'statusBar'):
            self.parent().statusBar().showMessage(message, 5000)

    # ------------------------------------------------------------------
    # Database Info Management (修正点4)
    # ------------------------------------------------------------------

    def update_db_info(self, db_info: dict):
        """
        修正点4: AppControllerから提供された情報でDB接続情報を更新

        Args:
            db_info: {
                'connected': bool,
                'type': str,
                'name': str,
                'tables_count': int,
                'last_updated': str (ISO format)
            }
        """
        connected = db_info.get('connected', False)
        db_type = db_info.get('type', 'N/A')
        db_name = db_info.get('name', 'N/A')
        tables_count = db_info.get('tables_count', 0)
        last_updated = db_info.get('last_updated', '未更新')

        # 接続状態を更新
        if connected:
            self.db_status_label.setText("接続中")
            self.db_status_label.setStyleSheet(
                "color: #107c10; font-weight: bold;")  # 緑色
        else:
            self.db_status_label.setText("未接続")
            self.db_status_label.setStyleSheet(
                "color: #d13438; font-weight: bold;")  # 赤色

        # データベースタイプを更新
        if db_type != 'N/A':
            self.db_type_label.setText(db_type.capitalize())
            self.db_type_label.setStyleSheet(
                "color: #333333; font-weight: normal;")
        else:
            self.db_type_label.setText("未設定")
            self.db_type_label.setStyleSheet("color: #666666;")

        # データベース名を更新
        if db_name != 'N/A':
            # 長いパスの場合は末尾を表示
            if len(db_name) > 20:
                display_name = "..." + db_name[-17:]
            else:
                display_name = db_name
            self.db_name_label.setText(display_name)
            self.db_name_label.setToolTip(db_name)  # フルパスをツールチップで表示
            self.db_name_label.setStyleSheet(
                "color: #333333; font-weight: normal;")
        else:
            self.db_name_label.setText("未設定")
            self.db_name_label.setStyleSheet("color: #666666;")

        # テーブル数を更新
        self.db_tables_label.setText(str(tables_count))
        if tables_count > 0:
            self.db_tables_label.setStyleSheet(
                "color: #0078d4; font-weight: bold;")
        else:
            self.db_tables_label.setStyleSheet("color: #666666;")

        # 最終更新時刻を更新
        if last_updated != '未更新':
            try:
                from datetime import datetime
                # ISO形式の時刻をパース
                if isinstance(last_updated, str):
                    dt = datetime.fromisoformat(
                        last_updated.replace('Z', '+00:00'))
                    formatted_time = dt.strftime('%H:%M:%S')
                else:
                    formatted_time = last_updated

                self.db_updated_label.setText(formatted_time)
                self.db_updated_label.setStyleSheet("color: #666666;")
            except Exception:
                self.db_updated_label.setText("更新済み")
                self.db_updated_label.setStyleSheet("color: #666666;")
        else:
            self.db_updated_label.setText("未更新")
            self.db_updated_label.setStyleSheet("color: #999999;")

    def show_db_error(self, error_message: str):
        """データベースエラー時の表示"""
        self.db_status_label.setText("エラー")
        self.db_status_label.setStyleSheet(
            "color: #d13438; font-weight: bold;")
        self.db_status_label.setToolTip(error_message)

        # その他の情報をクリア
        self.db_type_label.setText("未設定")
        self.db_name_label.setText("未設定")
        self.db_tables_label.setText("0")
        self.db_updated_label.setText("エラー")

    # ------------------------------------------------------------------
    # Legacy Public methods (maintained for compatibility)
    # ------------------------------------------------------------------

    def set_table_data(self, rows: list[tuple[str, int, str]]):
        """Update status table with a list of tuples."""
        self.table.setRowCount(len(rows))
        for row_idx, (data_type, count, latest) in enumerate(rows):
            self.table.setItem(row_idx, 0, QTableWidgetItem(str(data_type)))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(count)))
            self.table.setItem(row_idx, 2, QTableWidgetItem(str(latest)))

    def update_progress(self, value: int, text: str | None = None):
        """Legacy method: Update overall progress (for compatibility)."""
        self.donut_progress.setValue(value)
        if text is not None:
            self.overall_status_label.setText(text)

    def update_realtime_button_state(self, is_watching: bool):
        """速報受信ボタンの表示を更新する"""
        if is_watching:
            self.realtime_button.setText("受信停止")
            self.realtime_button.setIcon(FIF.PAUSE)
            if not self.realtime_button.isChecked():
                self.realtime_button.setChecked(True)
        else:
            self.realtime_button.setText("速報受信開始")
            self.realtime_button.setIcon(FIF.PLAY)
            if self.realtime_button.isChecked():
                self.realtime_button.setChecked(False)

    def update_dashboard_summary(self, summary: dict):
        """ダッシュボードのデータサマリーテーブルを更新する"""
        table_data = []
        for table_name, info in summary.items():
            count = info.get('count', 0)
            latest = info.get('latest', 'N/A')
            if latest == 'N/A' or latest is None:
                latest = '未取得'
            table_data.append((table_name, count, latest))

        self.set_table_data(table_data)
