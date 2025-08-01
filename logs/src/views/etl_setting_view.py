import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# PySide6
from PySide6.QtCore import Qt, Signal, QThread, QTimer, Slot, QDate, QTime
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QButtonGroup,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
)

# qfluentwidgets components - レポート セクション3.2準拠
from qfluentwidgets import (
    TitleLabel,
    BodyLabel,
    SubtitleLabel,
    StrongBodyLabel,
    LineEdit,
    ComboBox,
    PrimaryPushButton,
    PushButton,
    CheckBox,
    RadioButton,
    CardWidget,
    InfoBar,
    InfoBarPosition,
    ProgressRing,
    CalendarPicker,
    TimePicker,
    ScrollArea,
)
from qfluentwidgets import FluentIcon as FIF


class DataRetrievalView(QWidget):
    """
    データ取得画面 - レポート セクション3.2準拠
    
    JVOpenメソッドの複雑なパラメータ指定を、
    直感的なグラフィカルコントロールに置き換え
    """
    
    # シグナル定義
    data_retrieval_requested = Signal(dict)  # データ取得要求
    cancel_requested = Signal()  # キャンセル要求

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setObjectName("DataRetrievalView")
        
        # 処理状態管理
        self.is_processing = False
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self._update_progress)
        
        self._init_ui()
        self._load_default_settings()

    def _init_ui(self):
        """レポート セクション3.2: データ取得画面レイアウトの実装"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        # タイトル
        title = TitleLabel("データ取得", self)
        layout.addWidget(title)

        # スクロール可能エリア
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)  # ExpandLayoutをQVBoxLayoutに変更
        scroll_layout.setSpacing(20)
        
        # 設定カードグループ
        self._create_data_type_card(scroll_layout)      # データ種別選択
        self._create_time_range_card(scroll_layout)     # 取得期間設定
        self._create_options_card(scroll_layout)        # 取得オプション
        self._create_progress_card(scroll_layout)       # 進捗表示
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        # 実行ボタンエリア
        self._create_action_buttons(layout)

    def _create_data_type_card(self, parent_layout):
        """データ種別選択カード - レポート セクション3.2準拠"""
        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # カードタイトル
        title = StrongBodyLabel("📊 データ種別選択")
        card_layout.addWidget(title)
        
        description = BodyLabel(
            "取得したいデータの種類を選択してください。\n"
            "複数のデータ種別を同時に選択することができます。"
        )
        description.setWordWrap(True)
        card_layout.addWidget(description)
        
        # データ種別選択UI（JV-Data仕様書のDataSpec IDを抽象化）
        self.data_type_tree = QTreeWidget()
        self.data_type_tree.setHeaderLabel("データ種別")
        self._populate_data_types()
        card_layout.addWidget(self.data_type_tree)
        
        parent_layout.addWidget(card)

    def _populate_data_types(self):
        """データ種別ツリーにカテゴリとデータ種別を追加"""
        # JV-Data仕様書に基づくデータ種別の階層構造
        data_categories = {
            "レース情報": {
                "RACE": "レース詳細",
                "ODDS": "オッズ情報", 
                "PAYOFF": "払戻情報"
            },
            "馬情報": {
                "HORSE": "馬基本情報",
                "BLOOD": "血統情報",
                "TRAIN": "調教情報"
            },
            "騎手・調教師": {
                "JOCKEY": "騎手情報",
                "TRAINER": "調教師情報"
            },
            "開催情報": {
                "SCHEDULE": "開催スケジュール",
                "WEATHER": "天候情報"
            }
        }
        
        for category, items in data_categories.items():
            category_item = QTreeWidgetItem(self.data_type_tree, [category])
            # ★修正★: setIconには列番号（0）とアイコンを渡す
            try:
                if hasattr(FIF, 'FOLDER') and hasattr(FIF.FOLDER, 'icon'):
                    category_item.setIcon(0, FIF.FOLDER.icon())
                else:
                    # フォールバック: アイコンなしで継続
                    pass
            except (AttributeError, TypeError) as e:
                logging.warning(f"カテゴリアイコン設定エラー: {e}")
            
            for data_id, data_name in items.items():
                child_item = QTreeWidgetItem(category_item, [data_name])
                # ★修正★: setIconには列番号（0）とアイコンを渡す
                try:
                    if hasattr(FIF, 'DOCUMENT') and hasattr(FIF.DOCUMENT, 'icon'):
                        child_item.setIcon(0, FIF.DOCUMENT.icon())
                    else:
                        # フォールバック: アイコンなしで継続
                        pass
                except (AttributeError, TypeError) as e:
                    logging.warning(f"データ仕様アイコン設定エラー: {e}")
                
                # データとチェック状態を設定
                child_item.setData(0, Qt.ItemDataRole.UserRole, data_id)
                child_item.setCheckState(0, Qt.CheckState.Unchecked)

    def _create_time_range_card(self, parent_layout):
        """取得期間設定カード"""
        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # カードタイトル
        title = StrongBodyLabel("📅 取得期間設定")
        card_layout.addWidget(title)
        
        description = BodyLabel(
            "データを取得する期間を指定してください。\n"
            "YYYYMMDD文字列の手入力は不要です。"
        )
        description.setWordWrap(True)
        card_layout.addWidget(description)
        
        # 期間設定フォーム
        form_layout = QFormLayout()
        
        # 開始日時
        start_layout = QHBoxLayout()
        self.start_date_picker = CalendarPicker()
        self.start_time_picker = TimePicker()
        
        # ★修正★: datetime.dateをQDateに変換して設定
        try:
            current_date = QDate.currentDate()
            self.start_date_picker.setDate(current_date)
        except Exception as e:
            logging.warning(f"開始日設定エラー: {e}")
            
        try:
            current_datetime = datetime.now()
            current_qtime = QTime(current_datetime.hour, current_datetime.minute, current_datetime.second)
            self.start_time_picker.setTime(current_qtime)
        except Exception as e:
            logging.warning(f"開始時刻設定エラー: {e}")
        
        start_layout.addWidget(self.start_date_picker)
        start_layout.addWidget(self.start_time_picker)
        start_layout.addStretch()
        
        form_layout.addRow("取得開始日時:", start_layout)
        
        # クイック選択ボタン
        quick_layout = QHBoxLayout()
        
        self.today_btn = PushButton("今日")
        self.today_btn.clicked.connect(lambda: self._set_quick_date(0))
        
        self.week_btn = PushButton("1週間前")
        self.week_btn.clicked.connect(lambda: self._set_quick_date(7))
        
        self.month_btn = PushButton("1ヶ月前")
        self.month_btn.clicked.connect(lambda: self._set_quick_date(30))
        
        quick_layout.addWidget(self.today_btn)
        quick_layout.addWidget(self.week_btn)
        quick_layout.addWidget(self.month_btn)
        quick_layout.addStretch()
        
        form_layout.addRow("クイック選択:", quick_layout)
        
        card_layout.addLayout(form_layout)
        parent_layout.addWidget(card)

    def _create_options_card(self, parent_layout):
        """取得オプション設定カード"""
        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # カードタイトル
        title = StrongBodyLabel("⚙️ 取得オプション")
        card_layout.addWidget(title)
        
        description = BodyLabel(
            "データ取得の方法を選択してください。\n"
            "通常は「差分データ」で最新の更新分のみを取得することを推奨します。"
        )
        description.setWordWrap(True)
        card_layout.addWidget(description)
        
        # RadioButtonグループでoption値を選択
        self.option_group = QButtonGroup()
        options_layout = QVBoxLayout()
        
        # 通常データ（差分）
        self.normal_radio = RadioButton("差分データ (推奨)")
        self.normal_radio.setChecked(True)  # デフォルト選択
        self.normal_radio.setToolTip("前回取得以降の新しいデータのみを取得します")
        self.option_group.addButton(self.normal_radio, 1)  # option=1
        options_layout.addWidget(self.normal_radio)
        
        # 今週データ
        self.thisweek_radio = RadioButton("今週データ")
        self.thisweek_radio.setToolTip("今週開催分のデータを取得します")
        self.option_group.addButton(self.thisweek_radio, 2)  # option=2
        options_layout.addWidget(self.thisweek_radio)
        
        # セットアップデータ
        self.setup_radio = RadioButton("セットアップデータ")
        self.setup_radio.setToolTip("初期セットアップ用の全データを取得します（時間がかかります）")
        self.option_group.addButton(self.setup_radio, 4)  # option=4
        options_layout.addWidget(self.setup_radio)
        
        card_layout.addLayout(options_layout)
        parent_layout.addWidget(card)

    def _create_progress_card(self, parent_layout):
        """進捗表示カード"""
        self.progress_card = CardWidget()
        card_layout = QVBoxLayout(self.progress_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # カードタイトル
        title = StrongBodyLabel("📈 進捗状況")
        card_layout.addWidget(title)
        
        # 進捗リング
        progress_layout = QHBoxLayout()
        self.progress_ring = ProgressRing()
        self.progress_ring.setFixedSize(50, 50)
        self.progress_ring.setVisible(False)
        
        self.progress_label = BodyLabel("待機中...")
        
        progress_layout.addWidget(self.progress_ring)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addStretch()
        
        card_layout.addLayout(progress_layout)
        
        # 進捗カードは最初は非表示
        self.progress_card.setVisible(False)
        parent_layout.addWidget(self.progress_card)

    def _create_action_buttons(self, parent_layout):
        """実行ボタンエリア"""
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # データ取得開始ボタン
        self.start_button = PrimaryPushButton("データ取得開始")
        self.start_button.setIcon(FIF.DOWNLOAD)
        self.start_button.setFixedHeight(40)
        self.start_button.clicked.connect(self._on_start_retrieval)
        
        # キャンセルボタン
        self.cancel_button = PushButton("キャンセル")
        self.cancel_button.setIcon(FIF.CANCEL)
        self.cancel_button.setFixedHeight(40)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._on_cancel_retrieval)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.start_button)
        parent_layout.addLayout(button_layout)

    def _load_default_settings(self):
        """デフォルト設定の読み込み"""
        # デフォルトで今日の日付を設定
        self._set_quick_date(0)

    @Slot(int)
    def _set_quick_date(self, days_back: int):
        """クイック日付設定"""
        target_date = datetime.now() - timedelta(days=days_back)
        
        # ★修正★: datetime.dateをQDateに変換
        try:
            target_qdate = QDate(target_date.year, target_date.month, target_date.day)
            self.start_date_picker.setDate(target_qdate)
        except Exception as e:
            logging.warning(f"日付設定エラー: {e}")
            
        try:
            if days_back == 0:
                current_datetime = datetime.now()
                current_qtime = QTime(current_datetime.hour, current_datetime.minute, current_datetime.second)
                self.start_time_picker.setTime(current_qtime)
            else:
                target_qtime = QTime(target_date.hour, target_date.minute, target_date.second)
                self.start_time_picker.setTime(target_qtime)
        except Exception as e:
            logging.warning(f"時刻設定エラー: {e}")

    def _gather_retrieval_settings(self) -> dict:
        """UI設定からJVOpenパラメータを構築"""
        # 選択されたデータ種別を収集
        selected_specs = []
        root = self.data_type_tree.invisibleRootItem()
        for i in range(root.childCount()):
            category_item = root.child(i)
            for j in range(category_item.childCount()):
                child_item = category_item.child(j)
                if child_item.checkState(0) == Qt.CheckState.Checked:
                    data_id = child_item.data(0, Qt.ItemDataRole.UserRole)
                    selected_specs.append(data_id)
        
        # 日時をJVOpen形式（YYYYMMDDhhmmss）に変換
        start_date = self.start_date_picker.date()
        start_time = self.start_time_picker.time()
        start_datetime = datetime.combine(start_date, start_time)
        fromtime = start_datetime.strftime("%Y%m%d%H%M%S")
        
        # 取得オプション
        option = self.option_group.checkedId()
        
        return {
            'dataspec_list': selected_specs,
            'fromtime': fromtime,
            'option': option,
            'start_datetime': start_datetime  # 表示用
        }

    def _validate_settings(self, settings: dict) -> bool:
        """設定の妥当性チェック"""
        if not settings['dataspec_list']:
            InfoBar.warning(
                title="設定エラー",
                content="少なくとも1つのデータ種別を選択してください。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False
        return True

    @Slot()
    def _on_start_retrieval(self):
        """データ取得開始"""
        if self.is_processing:
            return

        settings = self._gather_retrieval_settings()
        
        if not self._validate_settings(settings):
            return

        # UI状態を処理中に変更
        self.is_processing = True
        self.start_button.setVisible(False)
        self.cancel_button.setVisible(True)
        self.progress_card.setVisible(True)
        self.progress_ring.setVisible(True)
        
        # 進捗表示開始
        self.progress_timer.start(100)  # 100ms間隔で更新
        
        # データ取得要求を発行
        self.data_retrieval_requested.emit(settings)
        
        InfoBar.info(
            title="データ取得開始",
            content=f"{len(settings['dataspec_list'])}種類のデータ取得を開始しました。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    @Slot()
    def _on_cancel_retrieval(self):
        """データ取得キャンセル"""
        self.cancel_requested.emit()
        self._reset_ui_state()

    def _update_progress(self):
        """進捗表示更新（JVStatusから取得した情報を表示）"""
        # TODO: 実際のJVStatusからの進捗情報を取得
        # 現在はダミー実装
        pass

    def update_progress_status(self, progress_percent: int, status_text: str):
        """外部からの進捗状況更新"""
        if self.is_processing:
            self.progress_ring.setValue(progress_percent)
            self.progress_label.setText(status_text)

    def on_retrieval_completed(self, success: bool, message: str):
        """データ取得完了通知"""
        self._reset_ui_state()
        
        if success:
            InfoBar.success(
                title="データ取得完了",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        else:
            InfoBar.error(
                title="データ取得エラー",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )

    def _reset_ui_state(self):
        """UI状態をリセット"""
        self.is_processing = False
        self.progress_timer.stop()
        
        self.start_button.setVisible(True)
        self.cancel_button.setVisible(False)
        self.progress_card.setVisible(False)
        self.progress_ring.setVisible(False)
        self.progress_ring.setValue(0)
        self.progress_label.setText("待機中...")


# 後方互換性のためのエイリアス
EtlSettingView = DataRetrievalView
