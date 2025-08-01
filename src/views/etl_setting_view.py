import logging
from datetime import datetime, timedelta

# PySide6
from PySide6.QtCore import Qt, Signal, QTimer, Slot, QDate, QTime
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QButtonGroup,
    QTreeWidgetItemIterator
)

# qfluentwidgets components - レポート セクション3.2準拠
from qfluentwidgets import (
    TitleLabel,
    BodyLabel,
    StrongBodyLabel,
    ComboBox,
    PrimaryPushButton,
    PushButton,
    RadioButton,
    CardWidget,
    InfoBar,
    InfoBarPosition,
    ProgressRing,
    CalendarPicker,
    TimePicker,
    ScrollArea,
    FluentIcon as FIF
)


class DataRetrievalView(QWidget):
    """
    データ取得画面 - UI/UX改善指示書準拠
    CalendarPicker/TimePickerを導入し、直感的な操作性を実現。
    """

    # シグナル定義
    data_retrieval_requested = Signal(dict)  # データ取得要求
    cancel_requested = Signal()  # キャンセル要求
    save_rule_requested = Signal(dict)  # ルール保存要求
    delete_rule_requested = Signal(str)  # ルール削除要求

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.setObjectName("DataRetrievalView")

        # 処理状態管理
        self.is_processing = False
        self.progress_timer = QTimer(self)
        self.progress_timer.timeout.connect(self._update_progress)

        self._init_ui()
        self._load_default_settings()

    def _init_ui(self):
        """UIの初期化 - 8pxスペーシングシステムとコントラスト改善を適用"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- タイトル ---
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(36, 20, 36, 12)
        title_label = TitleLabel("データ取得", title_container)
        title_layout.addWidget(title_label)
        layout.addWidget(title_container)

        # --- スクロールエリア ---
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(36, 8, 36, 24)
        scroll_layout.setSpacing(16)
        scroll_widget.setObjectName("DataRetrievalScrollWidget")
        scroll_area.setWidget(scroll_widget)

        # --- 設定カードグループ ---
        self._create_rule_management_card(scroll_layout)
        self._create_time_range_card(scroll_layout)
        self._create_data_type_card(scroll_layout)
        self._create_options_card(scroll_layout)
        self._create_progress_card(scroll_layout)

        # --- 実行ボタンエリア ---
        self._create_action_buttons(layout)

    def _create_rule_management_card(self, parent_layout):
        """ルール管理カード - レポート セクション3.2準拠"""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("📝 取得ルールの管理"))
        layout.addWidget(BodyLabel("頻繁に使う取得設定をルールとして保存できます。"))

        rule_layout = QHBoxLayout()
        self.rule_combo = ComboBox()
        self.rule_combo.setPlaceholderText("ルールを選択または新規作成...")
        self.rule_combo.setMinimumHeight(32)

        self.save_rule_button = PrimaryPushButton("保存")
        self.save_rule_button.setMinimumHeight(32)
        self.save_rule_button.clicked.connect(self._on_save_rule)

        self.delete_rule_button = PushButton("削除")
        self.delete_rule_button.setMinimumHeight(32)
        self.delete_rule_button.clicked.connect(self._on_delete_rule)

        rule_layout.addWidget(self.rule_combo, 1)
        rule_layout.addWidget(self.save_rule_button)
        rule_layout.addWidget(self.delete_rule_button)
        layout.addLayout(rule_layout)
        parent_layout.addWidget(card)

    def _create_data_type_card(self, parent_layout):
        """データ種別選択カード - レポート セクション3.2準拠"""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)
        layout.addWidget(StrongBodyLabel("📊 データ種別の選択"))
        layout.addWidget(BodyLabel("取得したいデータの種類をチェックしてください。"))

        self.data_type_tree = QTreeWidget()
        self.data_type_tree.setHeaderHidden(True)
        self._populate_data_types()
        layout.addWidget(self.data_type_tree)

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
        """取得期間設定カード - CalendarPicker/TimePickerで再設計"""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("📅 取得期間の設定"))
        layout.addWidget(BodyLabel("データを取得する開始日時を正確に指定します。"))

        # 日時選択
        picker_layout = QHBoxLayout()
        self.start_date_picker = CalendarPicker()
        self.start_date_picker.setMinimumHeight(32)
        self.start_time_picker = TimePicker()
        self.start_time_picker.setMinimumHeight(32)
        picker_layout.addWidget(self.start_date_picker)
        picker_layout.addWidget(self.start_time_picker)
        picker_layout.addStretch()
        layout.addLayout(picker_layout)

        # クイック選択
        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(8)
        self.today_btn = PushButton("今日")
        self.today_btn.setMinimumHeight(32)
        self.today_btn.clicked.connect(lambda: self._set_quick_date(0))
        self.week_btn = PushButton("1週間前")
        self.week_btn.setMinimumHeight(32)
        self.week_btn.clicked.connect(lambda: self._set_quick_date(7))
        self.month_btn = PushButton("1ヶ月前")
        self.month_btn.setMinimumHeight(32)
        self.month_btn.clicked.connect(lambda: self._set_quick_date(30))

        quick_layout.addWidget(BodyLabel("クイック選択:"))
        quick_layout.addWidget(self.today_btn)
        quick_layout.addWidget(self.week_btn)
        quick_layout.addWidget(self.month_btn)
        quick_layout.addStretch()
        layout.addLayout(quick_layout)

        parent_layout.addWidget(card)

    def _create_options_card(self, parent_layout):
        """取得オプション設定カード"""
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("⚙️ 取得オプション"))
        layout.addWidget(BodyLabel(
            "データ取得の方法を選択してください。\n"
            "通常は「差分データ」で最新の更新分のみを取得することを推奨します。"
        ))

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

        layout.addLayout(options_layout)
        parent_layout.addWidget(card)

    def _create_progress_card(self, parent_layout):
        """進捗表示カード"""
        self.progress_card = CardWidget()
        layout = QVBoxLayout(self.progress_card)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("📈 進捗状況"))

        # 進捗リング
        progress_layout = QHBoxLayout()
        self.progress_ring = ProgressRing()
        self.progress_ring.setFixedSize(50, 50)
        self.progress_ring.setVisible(False)

        self.progress_label = BodyLabel("待機中...")

        progress_layout.addWidget(self.progress_ring)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addStretch()

        layout.addLayout(progress_layout)

        # 進捗カードは最初は非表示
        self.progress_card.setVisible(False)
        parent_layout.addWidget(self.progress_card)

    def _create_action_buttons(self, parent_layout):
        """実行ボタンエリア"""
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(36, 12, 36, 12)
        button_layout.addStretch()

        # データ取得開始ボタン
        self.start_button = PrimaryPushButton("データ取得を開始")
        self.start_button.setMinimumHeight(36)
        self.start_button.setIcon(FIF.DOWNLOAD)
        self.start_button.clicked.connect(self._on_start_retrieval)

        # キャンセルボタン
        self.cancel_button = PushButton("キャンセル")
        self.cancel_button.setMinimumHeight(36)
        self.cancel_button.setIcon(FIF.CANCEL)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self._on_cancel_retrieval)

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.start_button)
        parent_layout.addWidget(button_container)

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
        """UI設定からJVOpenパラメータを構築 - 新UI対応"""
        selected_specs = []
        iterator = QTreeWidgetItemIterator(self.data_type_tree)
        while iterator.value():
            item = iterator.value()
            if item.childCount() == 0 and item.checkState(0) == Qt.CheckState.Checked:
                data_id = item.data(0, Qt.ItemDataRole.UserRole)
                if data_id:
                    selected_specs.append(data_id)
            iterator += 1

        start_date = self.start_date_picker.getDate()
        start_time = self.start_time_picker.getTime()

        start_datetime = datetime.combine(start_date, start_time)
        fromtime = start_datetime.strftime("%Y%m%d%H%M%S")

        option = self.option_group.checkedId()

        return {
            'dataspec_list': selected_specs,
            'fromtime': fromtime,
            'option': option,
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

    @Slot()
    def _on_save_rule(self):
        """ルール保存ボタンがクリックされたときの処理"""
        try:
            # 現在の設定を収集
            rule_data = self._gather_retrieval_settings()
            rule_name = self.rule_combo.currentText() or f"ルール_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            rule_data['name'] = rule_name

            logging.info(f"ルール保存要求: {rule_name}")
            self.save_rule_requested.emit(rule_data)

        except Exception as e:
            logging.error(f"ルール保存エラー: {e}")

    @Slot()
    def _on_delete_rule(self):
        """ルール削除ボタンがクリックされたときの処理"""
        try:
            rule_name = self.rule_combo.currentText()
            if not rule_name:
                return

            logging.info(f"ルール削除要求: {rule_name}")
            self.delete_rule_requested.emit(rule_name)

        except Exception as e:
            logging.error(f"ルール削除エラー: {e}")

    def set_rules(self, rules: list):
        """ETLルールの設定メソッド - AppControllerから呼び出される"""
        try:
            self.rule_combo.clear()
            for rule in rules:
                if isinstance(rule, dict) and 'name' in rule:
                    self.rule_combo.addItem(rule['name'])
                elif isinstance(rule, str):
                    self.rule_combo.addItem(rule)

            logging.debug(f"ルール設定完了: {len(rules)}個のルール")

        except Exception as e:
            logging.error(f"ルール設定エラー: {e}")

    def load_rules(self, rules: list):
        """ETLルールの読み込みメソッド - 別名実装"""
        self.set_rules(rules)

    def update_rules(self, rules: list):
        """ETLルールの更新メソッド - 別名実装"""
        self.set_rules(rules)

    def _save_current_settings(self):
        pass

    def __getattr__(self, name):
        """
        未実装メソッドの動的ハンドリング - method missing パターン
        
        参考: https://keegoo.github.io/notes/2018/03/12/method-missing-in-python.html
        """
        def _method_missing(*args, **kwargs):
            logging.warning(f"DataRetrievalView: 未実装メソッド '{name}' が呼び出されました")
            logging.debug(f"引数: args={args}, kwargs={kwargs}")

            # データ取得ビュー固有の未実装メソッド処理
            if name.startswith('set_') or name.startswith('load_') or name.startswith('update_'):
                logging.info(f"データ設定関連メソッド '{name}' の呼び出しをスキップしました")
                return True
            elif name.startswith('get_') or name.startswith('gather_'):
                logging.info(f"データ取得メソッド '{name}' は空の結果を返しました")
                return {}
            elif name.endswith('_requested') or name.endswith('_clicked'):
                logging.info(f"イベントメソッド '{name}' は None を返しました")
                return None
            else:
                logging.info(f"その他のメソッド '{name}' は None を返しました")
                return None

        return _method_missing


# 後方互換性のためのエイリアス
EtlSettingView = DataRetrievalView
