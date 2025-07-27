import logging

# PySide6
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QFormLayout,
    QFileDialog,
)

# qfluentwidgets components
from qfluentwidgets import (
    TitleLabel,
    BodyLabel,
    SubtitleLabel,
    StrongBodyLabel,
    LineEdit,
    ComboBox,
    PrimaryPushButton,
    CheckBox,
    CardWidget,
    InfoBar,
    InfoBarPosition,
)
from qfluentwidgets import FluentIcon as FIF


class EtlSettingView(QWidget):
    """
    ETL設定画面のUI。
    データの変換・加工ルールを定義し、保存・管理する。
    """
    save_rule_requested = Signal(str, dict)
    delete_rule_requested = Signal(str)

    def __init__(self, db_manager, parent=None):
        super().__init__(parent)
        print("EtlSettingView.__init__ start")
        self.db_manager = db_manager
        self.table_names = self.db_manager.get_table_names()
        print(f"EtlSettingView: table_names = {self.table_names}")
        self.column_checkboxes = []
        self._init_ui()
        print("EtlSettingView.__init__ end")

    def _init_ui(self):
        print("EtlSettingView: _init_ui start")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        title = TitleLabel("ETL設定", self)
        layout.addWidget(title)

        # 1. ルール選択カード
        rule_selection_card = CardWidget(self)
        selection_card_layout = QVBoxLayout(rule_selection_card)

        selection_card_title = StrongBodyLabel("📋 ルール選択", rule_selection_card)
        selection_card_layout.addWidget(selection_card_title)
        selection_card_layout.addSpacing(12)

        rule_selection_layout = QFormLayout()

        self.rule_combo = ComboBox(rule_selection_card)
        self.rule_combo.setPlaceholderText("既存のルールを選択...")
        self.rule_combo.addItem("＜新規作成＞")
        self.rule_combo.setFixedHeight(35)
        self.rule_combo.currentTextChanged.connect(self.on_rule_selected)
        rule_selection_layout.addRow(BodyLabel("ルール選択:"), self.rule_combo)

        from qfluentwidgets import PushButton
        delete_button = PushButton("このルールを削除", rule_selection_card)
        delete_button.setFixedHeight(35)
        delete_button.clicked.connect(self.on_delete_rule)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(delete_button)

        selection_card_layout.addLayout(rule_selection_layout)
        selection_card_layout.addLayout(button_layout)
        layout.addWidget(rule_selection_card)

        # 2. ルール定義カード
        self.rule_definition_card = CardWidget(self)
        definition_card_layout = QVBoxLayout(self.rule_definition_card)

        definition_card_title = StrongBodyLabel(
            "⚙️ ルール定義", self.rule_definition_card)
        definition_card_layout.addWidget(definition_card_title)
        definition_card_layout.addSpacing(12)

        rule_layout = QFormLayout()

        self.rule_name_input = LineEdit(self.rule_definition_card)
        self.rule_name_input.setPlaceholderText("新しいルール名を入力")
        self.rule_name_input.setFixedHeight(35)
        rule_layout.addRow(BodyLabel("ルール名:"), self.rule_name_input)

        self.target_table_combo = ComboBox(self.rule_definition_card)
        self.target_table_combo.addItems(self.table_names)
        self.target_table_combo.setFixedHeight(35)
        self.target_table_combo.currentTextChanged.connect(
            self.on_target_table_changed)
        rule_layout.addRow(BodyLabel("対象テーブル:"), self.target_table_combo)

        definition_card_layout.addLayout(rule_layout)

        # カラム除外設定
        columns_label = BodyLabel("除外するカラム:", self.rule_definition_card)
        definition_card_layout.addWidget(columns_label)

        # スクロールエリア本体
        self.columns_scroll = QScrollArea(self.rule_definition_card)
        self.columns_scroll.setWidgetResizable(True)
        self.columns_scroll.setFixedHeight(200)
        self.columns_scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                background-color: rgba(255, 255, 255, 0.05);
            }
        """)

        # スクロールエリア内の実コンテナ
        self.columns_container = QWidget()
        self.columns_layout = QVBoxLayout(self.columns_container)
        self.columns_container.setLayout(self.columns_layout)
        self.columns_scroll.setWidget(self.columns_container)
        definition_card_layout.addWidget(self.columns_scroll)

        layout.addWidget(self.rule_definition_card)
        layout.addStretch()

        # 3. アクションボタンエリア
        action_layout = QHBoxLayout()
        action_layout.addStretch(1)
        self.save_button = PrimaryPushButton(FIF.SAVE, "ルールを保存", self)
        self.save_button.setFixedHeight(40)
        self.save_button.clicked.connect(self.on_save_rule)
        action_layout.addWidget(self.save_button)
        layout.addLayout(action_layout)

        print("EtlSettingView: UI built, calling on_target_table_changed")
        # 初期状態
        self.on_target_table_changed(self.target_table_combo.currentText())
        print("EtlSettingView: _init_ui end")

    def on_rule_selected(self, rule_name: str):
        if rule_name == "＜新規作成＞" or not rule_name:
            self.rule_name_input.setText("")
            self.rule_name_input.setReadOnly(False)
            self.target_table_combo.setCurrentIndex(0)
            self.on_target_table_changed(self.target_table_combo.currentText())
        else:
            self.rule_name_input.setText(rule_name)
            self.rule_name_input.setReadOnly(True)
            # TODO: ルールデータを読み込んでUIに反映する処理

    def on_target_table_changed(self, table_name: str):
        print(f"EtlSettingView: on_target_table_changed({table_name}) start")
        # チェックボックスをクリア
        for checkbox in self.column_checkboxes:
            self.columns_layout.removeWidget(checkbox)
            checkbox.deleteLater()
        self.column_checkboxes.clear()

        if not table_name:
            return

        columns = self.db_manager.get_table_columns(table_name)
        for col_name in columns:
            checkbox = CheckBox(col_name)
            self.columns_layout.addWidget(checkbox)
            self.column_checkboxes.append(checkbox)
        print(
            f"EtlSettingView: on_target_table_changed({table_name}) done; {len(columns)} columns")

    def on_save_rule(self):
        rule_name = self.rule_name_input.text()
        if not rule_name:
            logging.warning("ルール名が入力されていません。")
            # TODO: Show MessageBox
            return

        ignored_columns = [cb.text()
                           for cb in self.column_checkboxes if cb.isChecked()]
        rule_data = {
            "target_table": self.target_table_combo.currentText(),
            "ignored_columns": ignored_columns,
        }
        self.save_rule_requested.emit(rule_name, rule_data)

    def on_delete_rule(self):
        selected_rule = self.rule_combo.currentText()
        if selected_rule != "＜新規作成＞" and selected_rule:
            self.delete_rule_requested.emit(selected_rule)

    def set_rules(self, rules: dict):
        current_selection = self.rule_combo.currentText()
        self.rule_combo.blockSignals(True)
        self.rule_combo.clear()
        self.rule_combo.addItem("＜新規作成＞")
        self.rule_combo.addItems(rules.keys())

        # Try to restore selection
        index = self.rule_combo.findText(current_selection)
        if index != -1:
            self.rule_combo.setCurrentIndex(index)
        self.rule_combo.blockSignals(False)

    def set_rule_data(self, rule_data: dict):
        """指定されたルールデータをUIに反映させる"""
        self.target_table_combo.setCurrentText(
            rule_data.get("target_table", ""))
        self.on_target_table_changed(rule_data.get("target_table", ""))

        ignored = rule_data.get("ignored_columns", [])
        for checkbox in self.column_checkboxes:
            if checkbox.text() in ignored:
                checkbox.setChecked(True)
            else:
                checkbox.setChecked(False)
