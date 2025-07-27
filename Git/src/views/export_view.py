import logging
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStackedWidget,
    QCheckBox,
    QGroupBox,
    QRadioButton,
    QFileDialog,
    QLineEdit,
    QLabel,
    QFormLayout,
    QScrollArea,
    QPushButton,
)

# QFluentWidgets
from qfluentwidgets import (
    TitleLabel,
    SubtitleLabel,
    PrimaryPushButton,
    InfoBar,
    InfoBarPosition,
    CardWidget,
    StrongBodyLabel,
    BodyLabel,
)
from qfluentwidgets import FluentIcon as FIF


class ExportView(QWidget):
    """
    データエクスポート画面のUI。
    ウィザード形式でエクスポート設定を行う。
    """
    export_requested = Signal(dict)

    def __init__(self, table_names: list[str], parent=None):
        super().__init__(parent)
        self.table_names = table_names
        self.setObjectName("ExportView")
        self._init_ui()

    def _init_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        # Title
        title = TitleLabel("データエクスポート", self)
        layout.addWidget(title)

        # Steps indicator (alternative implementation)
        steps_card = CardWidget(self)
        steps_card.setFixedHeight(60)
        steps_layout = QHBoxLayout(steps_card)
        steps_layout.setContentsMargins(20, 10, 20, 10)

        self.step_labels = []
        step_names = ["1️⃣ テーブル選択", "2️⃣ 形式・保存先", "3️⃣ 確認"]

        for i, step_name in enumerate(step_names):
            step_label = BodyLabel(step_name, steps_card)
            step_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.step_labels.append(step_label)
            steps_layout.addWidget(step_label)

            if i < len(step_names) - 1:
                arrow_label = BodyLabel("→", steps_card)
                arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                steps_layout.addWidget(arrow_label)

        layout.addWidget(steps_card)

        # Stacked pages
        self.stacked_widget = QStackedWidget(self)
        self.step1_widget = self._create_step1_widget()
        self.step2_widget = self._create_step2_widget()
        self.step3_widget = self._create_step3_widget()

        self.stacked_widget.addWidget(self.step1_widget)
        self.stacked_widget.addWidget(self.step2_widget)
        self.stacked_widget.addWidget(self.step3_widget)

        layout.addWidget(self.stacked_widget)

        # Navigation buttons
        nav_layout = QHBoxLayout()
        nav_layout.addStretch(1)
        self.back_button = PrimaryPushButton("戻る")
        self.next_button = PrimaryPushButton("次へ")
        self.export_button = PrimaryPushButton("エクスポート開始")

        nav_layout.addWidget(self.back_button)
        nav_layout.addWidget(self.next_button)
        nav_layout.addWidget(self.export_button)

        layout.addLayout(nav_layout)

        # シグナル接続
        self.back_button.clicked.connect(self._go_back)
        self.next_button.clicked.connect(self._go_next)
        self.export_button.clicked.connect(self._emit_export_request)

        self._update_nav_buttons()

    def _create_step1_widget(self) -> QWidget:
        """ステップ1: データ選択UIを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        subtitle = SubtitleLabel("1. エクスポートするテーブルを選択してください", self)
        layout.addWidget(subtitle)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_content = QWidget()
        self.checkbox_layout = QVBoxLayout(scroll_content)
        self.checkbox_layout.setSpacing(8)

        self.table_checkboxes = []
        for table_name in self.table_names:
            checkbox = QCheckBox(table_name)
            self.checkbox_layout.addWidget(checkbox)
            self.table_checkboxes.append(checkbox)

        scroll_area.setWidget(scroll_content)
        layout.addWidget(scroll_area)
        return widget

    def _create_step2_widget(self) -> QWidget:
        """ステップ2: 形式と出力先選択UIを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(10)
        subtitle = SubtitleLabel("2. 出力形式と保存先を選択してください", self)
        layout.addWidget(subtitle)

        form_layout = QFormLayout()
        form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        format_group = QGroupBox("出力形式")
        format_layout = QHBoxLayout()
        self.csv_radio = QRadioButton("CSV (カンマ区切り)")
        self.csv_radio.setChecked(True)
        self.tsv_radio = QRadioButton("TSV (タブ区切り)")
        format_layout.addWidget(self.csv_radio)
        format_layout.addWidget(self.tsv_radio)
        format_group.setLayout(format_layout)
        form_layout.addRow(format_group)

        dest_layout = QHBoxLayout()
        self.path_line_edit = QLineEdit()
        self.path_line_edit.setReadOnly(True)
        browse_button = QPushButton("参照...")
        browse_button.clicked.connect(self._browse_path)
        dest_layout.addWidget(self.path_line_edit)
        dest_layout.addWidget(browse_button)
        form_layout.addRow("保存先:", dest_layout)

        layout.addLayout(form_layout)
        layout.addStretch()
        return widget

    def _create_step3_widget(self) -> QWidget:
        """ステップ3: 実行確認UIを作成（Resultコンポーネント風に改善）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)

        subtitle = SubtitleLabel("✅ 3. 設定を確認してエクスポートを開始", self)
        layout.addWidget(subtitle)

        # 確認用カード
        confirmation_card = CardWidget(self)
        card_layout = QVBoxLayout(confirmation_card)

        card_title = StrongBodyLabel("📋 エクスポート設定の確認", confirmation_card)
        card_layout.addWidget(card_title)
        card_layout.addSpacing(12)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("""
            QLabel {
                background-color: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                border-radius: 8px;
                padding: 16px;
                font-size: 14px;
                line-height: 1.5;
            }
        """)
        card_layout.addWidget(self.summary_label)

        layout.addWidget(confirmation_card)
        layout.addStretch(1)

        return widget

    def _go_next(self):
        """「次へ」ボタンの処理"""
        current_index = self.stacked_widget.currentIndex()
        if current_index < self.stacked_widget.count() - 1:
            if current_index == 0 and not any(cb.isChecked() for cb in self.table_checkboxes):
                logging.warning("エクスポートするテーブルが選択されていません。")
                # TODO: Show MessageBox
                return
            self.stacked_widget.setCurrentIndex(current_index + 1)
        self._update_nav_buttons()
        if self.stacked_widget.currentIndex() == 2:
            self._update_summary()

    def _go_back(self):
        """「戻る」ボタンの処理"""
        current_index = self.stacked_widget.currentIndex()
        if current_index > 0:
            self.stacked_widget.setCurrentIndex(current_index - 1)
        self._update_nav_buttons()

    def _update_nav_buttons(self):
        """ナビゲーションボタンの状態を更新"""
        current_index = self.stacked_widget.currentIndex()
        self.back_button.setEnabled(current_index > 0)
        self.next_button.setEnabled(
            current_index < self.stacked_widget.count() - 1)

        is_last = current_index == self.stacked_widget.count() - 1
        self.export_button.setEnabled(is_last)
        self.export_button.setVisible(True)

        # Update steps visual indicator
        for i, label in enumerate(self.step_labels):
            if i == current_index:
                label.setStyleSheet("color: #0078D4; font-weight: bold;")
            else:
                label.setStyleSheet("color: #888; font-weight: normal;")

    def _browse_path(self):
        """保存先を選択するダイアログを開く"""
        selected_tables = [cb.text()
                           for cb in self.table_checkboxes if cb.isChecked()]
        file_format = "csv" if self.csv_radio.isChecked() else "tsv"

        if len(selected_tables) == 1:
            default_name = f"{selected_tables[0]}.{file_format}"
            path, _ = QFileDialog.getSaveFileName(
                self, "保存先を選択", default_name, f"{file_format.upper()} files (*.{file_format});;All files (*)")
        else:
            path = QFileDialog.getExistingDirectory(self, "保存先のフォルダを選択")

        if path:
            self.path_line_edit.setText(path)

    def _update_summary(self):
        """ステップ3のサマリーを更新"""
        selected_tables = [cb.text()
                           for cb in self.table_checkboxes if cb.isChecked()]
        file_format = "CSV" if self.csv_radio.isChecked() else "TSV"
        path = self.path_line_edit.text()

        summary_text = f"""
        <b>エクスポート対象:</b><br> {', '.join(selected_tables)}<br><br>
        <b>出力形式:</b><br> {file_format}<br><br>
        <b>保存先:</b><br> {path}
        """
        self.summary_label.setText(summary_text)

    def _emit_export_request(self):
        """エクスポート開始シグナルを発行"""
        params = {
            "tables": [cb.text() for cb in self.table_checkboxes if cb.isChecked()],
            "format": "csv" if self.csv_radio.isChecked() else "tsv",
            "path": self.path_line_edit.text(),
        }
        if not params["tables"] or not params["path"]:
            logging.error("エクスポートパラメータが不正です")
            # TODO: MessageBox
            return

        logging.info(f"エクスポートリクエストを発行します: {params}")
        self.export_requested.emit(params)
