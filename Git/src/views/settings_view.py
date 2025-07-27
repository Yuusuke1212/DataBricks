import logging
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QFormLayout,
    QFileDialog,
    QMessageBox,
    QGroupBox,
)

# qfluentwidgets components
from qfluentwidgets import (
    TitleLabel,
    BodyLabel,
    SubtitleLabel,
    StrongBodyLabel,
    LineEdit,
    PasswordLineEdit,
    ComboBox,
    PushButton,
    PrimaryPushButton,
    CardWidget,
    InfoBar,
    InfoBarPosition,
)
from qfluentwidgets import FluentIcon as FIF


class SettingsView(QWidget):
    """
    アプリケーション設定画面のUI。
    データベース接続の設定とJV-Link公式ダイアログの呼び出しを行う。
    """
    settings_saved = Signal(dict)
    db_test_requested = Signal(dict)
    jvlink_dialog_requested = Signal()  # JV-Link設定ダイアログ要求シグナル

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsView")
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)

        title = TitleLabel("アプリケーション設定", self)
        layout.addWidget(title)

        tab_widget = QTabWidget(self)

        jv_link_tab = self._create_jv_link_tab()
        db_tab = self._create_db_tab()

        tab_widget.addTab(jv_link_tab, "JV-Link 設定")
        tab_widget.addTab(db_tab, "データベース設定")

        layout.addWidget(tab_widget)

        # 保存ボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        save_button = PrimaryPushButton("設定を保存")
        save_button.clicked.connect(self._on_save)
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)

    def _create_jv_link_tab(self):
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # JV-Link設定カード
        jvlink_card = CardWidget(widget)
        card_layout = QVBoxLayout(jvlink_card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)

        # タイトル
        card_title = StrongBodyLabel("🔐 JRA-VAN 設定", jvlink_card)
        card_layout.addWidget(card_title)

        # 説明文
        description = BodyLabel(
            "JV-Linkの公式設定ダイアログでサービスキーやデータ保存パスを設定してください。\n"
            "設定はWindowsレジストリに保存され、アプリケーション全体で共有されます。",
            jvlink_card
        )
        description.setWordWrap(True)
        card_layout.addWidget(description)

        # JV-Link設定ダイアログ開くボタン
        self.open_jvlink_dialog_button = PrimaryPushButton(
            "JV-Link 設定ダイアログを開く", jvlink_card)
        self.open_jvlink_dialog_button.setIcon(FIF.SETTING)
        self.open_jvlink_dialog_button.setFixedHeight(40)
        self.open_jvlink_dialog_button.clicked.connect(
            self._on_open_jvlink_dialog)
        card_layout.addWidget(self.open_jvlink_dialog_button)

        # 注意事項
        info_label = BodyLabel(
            "💡 ヒント: この設定はEveryDB2などの他のJRA-VAN対応ソフトウェアと共有されます。",
            jvlink_card
        )
        info_label.setStyleSheet("color: #666666; font-size: 12px;")
        info_label.setWordWrap(True)
        card_layout.addWidget(info_label)

        main_layout.addWidget(jvlink_card)
        main_layout.addStretch(1)

        return widget

    def _create_db_tab(self):
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # DB種類選択カード
        db_type_card = CardWidget(widget)
        type_card_layout = QVBoxLayout(db_type_card)

        type_card_title = StrongBodyLabel("🗃️ データベース種類", db_type_card)
        type_card_layout.addWidget(type_card_title)
        type_card_layout.addSpacing(12)

        db_type_layout = QFormLayout()
        self.db_type_combo = ComboBox(db_type_card)
        self.db_type_combo.addItems(["SQLite", "MySQL", "PostgreSQL"])
        self.db_type_combo.currentTextChanged.connect(self._on_db_type_changed)
        self.db_type_combo.setFixedHeight(35)
        db_type_layout.addRow(BodyLabel("データベースの種類:"), self.db_type_combo)

        type_card_layout.addLayout(db_type_layout)
        main_layout.addWidget(db_type_card)

        # 接続情報カード
        self.db_settings_card = CardWidget(widget)
        settings_card_layout = QVBoxLayout(self.db_settings_card)

        settings_card_title = StrongBodyLabel("⚙️ 接続情報", self.db_settings_card)
        settings_card_layout.addWidget(settings_card_title)
        settings_card_layout.addSpacing(12)

        self.db_settings_layout = QFormLayout()
        settings_card_layout.addLayout(self.db_settings_layout)
        main_layout.addWidget(self.db_settings_card)

        # 接続テストボタン
        test_button_layout = QHBoxLayout()
        test_button_layout.addStretch()
        test_button = PushButton("接続テスト", self.db_settings_card)
        test_button.setFixedHeight(35)
        test_button.clicked.connect(self._on_test_connection)
        test_button_layout.addWidget(test_button)
        settings_card_layout.addLayout(test_button_layout)

        # 各DB用の入力ウィジェット
        self._create_sqlite_inputs()
        self._create_mysql_pg_inputs()

        # 初期状態
        self._on_db_type_changed("SQLite")

        main_layout.addStretch(1)

        return widget

    def _create_sqlite_inputs(self):
        self.sqlite_path_layout = QHBoxLayout()
        self.sqlite_path_input = LineEdit(self)
        self.sqlite_path_input.setReadOnly(True)
        browse_button = PushButton("参照...")
        browse_button.clicked.connect(self._browse_sqlite_path)
        self.sqlite_path_layout.addWidget(self.sqlite_path_input)
        self.sqlite_path_layout.addWidget(browse_button)
        self.sqlite_path_row = QWidget()
        self.sqlite_path_row.setLayout(self.sqlite_path_layout)

    def _create_mysql_pg_inputs(self):
        self.host_input = LineEdit(self)
        self.host_input.setText("localhost")
        self.port_input = LineEdit(self)
        self.username_input = LineEdit(self)
        self.password_input = PasswordLineEdit(self)
        self.db_name_input = LineEdit(self)

    def _on_db_type_changed(self, db_type: str):
        # 全ての既存DB設定ウィジェットを非表示にする
        for i in range(self.db_settings_layout.count()):
            item = self.db_settings_layout.itemAt(i)
            if item:
                widget = item.widget()
                if widget:
                    widget.setVisible(False)

        # 既存のウィジェットをレイアウトから削除
        while self.db_settings_layout.count():
            item = self.db_settings_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.setParent(None)

        if db_type == "SQLite":
            # SQLite用ウィジェットを表示
            self.sqlite_path_row.setVisible(True)
            self.db_settings_layout.addRow("データベースファイル:", self.sqlite_path_row)

            # MySQL/PostgreSQL用ウィジェットを非表示
            self.host_input.setVisible(False)
            self.port_input.setVisible(False)
            self.username_input.setVisible(False)
            self.password_input.setVisible(False)
            self.db_name_input.setVisible(False)

        else:  # MySQL or PostgreSQL
            # MySQL/PostgreSQL用ウィジェットを表示
            self.host_input.setVisible(True)
            self.port_input.setVisible(True)
            self.username_input.setVisible(True)
            self.password_input.setVisible(True)
            self.db_name_input.setVisible(True)

            # SQLite用ウィジェットを非表示
            self.sqlite_path_row.setVisible(False)

            # デフォルト値の設定
            if db_type == "MySQL":
                if not self.port_input.text():
                    self.port_input.setText("3306")
            elif db_type == "PostgreSQL":
                if not self.port_input.text():
                    self.port_input.setText("5432")

            self.db_settings_layout.addRow("ホスト:", self.host_input)
            self.db_settings_layout.addRow("ポート:", self.port_input)
            self.db_settings_layout.addRow("ユーザー名:", self.username_input)
            self.db_settings_layout.addRow("パスワード:", self.password_input)
            self.db_settings_layout.addRow("データベース名:", self.db_name_input)

    def _browse_sqlite_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "データベースファイルを選択", "", "SQLite Database (*.db)")
        if path:
            self.sqlite_path_input.setText(path)

    def get_current_settings(self) -> dict:
        settings = {
            "database": {
                "type": self.db_type_combo.currentText()
            }
        }
        db_settings = settings["database"]
        if db_settings["type"] == "SQLite":
            try:
                if hasattr(self, 'sqlite_path_input') and self.sqlite_path_input:
                    db_settings["path"] = self.sqlite_path_input.text()
                else:
                    db_settings["path"] = "jra_data.db"
            except RuntimeError:
                db_settings["path"] = "jra_data.db"
        else:
            # 他のDB種別の場合、UIオブジェクトの安全なアクセス
            try:
                if hasattr(self, 'host_input') and self.host_input:
                    db_settings["host"] = self.host_input.text()
                else:
                    db_settings["host"] = "localhost"
            except RuntimeError:
                db_settings["host"] = "localhost"

            try:
                if hasattr(self, 'port_input') and self.port_input:
                    try:
                        db_settings["port"] = int(self.port_input.text()) if self.port_input.text(
                        ) else (5432 if db_settings["type"] == "PostgreSQL" else 3306)
                    except ValueError:
                        db_settings["port"] = 5432 if db_settings["type"] == "PostgreSQL" else 3306
                else:
                    db_settings["port"] = 5432 if db_settings["type"] == "PostgreSQL" else 3306
            except RuntimeError:
                db_settings["port"] = 5432 if db_settings["type"] == "PostgreSQL" else 3306

            try:
                if hasattr(self, 'username_input') and self.username_input:
                    db_settings["username"] = self.username_input.text()
                else:
                    db_settings["username"] = "postgres" if db_settings["type"] == "PostgreSQL" else "root"
            except RuntimeError:
                db_settings["username"] = "postgres" if db_settings["type"] == "PostgreSQL" else "root"

            try:
                if hasattr(self, 'password_input') and self.password_input:
                    db_settings["password"] = self.password_input.text()
                else:
                    db_settings["password"] = ""
            except RuntimeError:
                db_settings["password"] = ""

            try:
                if hasattr(self, 'db_name_input') and self.db_name_input:
                    db_settings["db_name"] = self.db_name_input.text()
                else:
                    db_settings["db_name"] = "jra_data"
            except RuntimeError:
                db_settings["db_name"] = "jra_data"
        return settings

    def set_current_settings(self, settings: dict):
        if not settings:
            return
        # Database
        db_settings = settings.get("database", {})
        db_type = db_settings.get("type", "SQLite")
        self.db_type_combo.setCurrentText(db_type)
        self._on_db_type_changed(db_type)  # フォームを切り替え

        if db_type == "SQLite":
            self.sqlite_path_input.setText(db_settings.get("path", ""))
        else:
            self.host_input.setText(db_settings.get("host", "localhost"))
            self.port_input.setText(str(db_settings.get("port", "")))
            self.username_input.setText(db_settings.get("username", ""))
            self.password_input.setText(db_settings.get("password", ""))
            self.db_name_input.setText(db_settings.get("db_name", ""))

    def _on_save(self):
        self.settings_saved.emit(self.get_current_settings())

    def _on_test_connection(self):
        self.db_test_requested.emit(
            self.get_current_settings().get('database', {}))

    def _on_open_jvlink_dialog(self):
        """JV-Link設定ダイアログを開く要求を発行"""
        self.jvlink_dialog_requested.emit()

    def show_test_result(self, success: bool, message: str):
        if success:
            QMessageBox.information(self, "成功", message)
        else:
            QMessageBox.warning(self, "失敗", message)

    def show_jvlink_dialog_result(self, success: bool, message: str):
        """JV-Link設定ダイアログの結果を表示"""
        if success:
            InfoBar.success(
                title="設定完了",
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        else:
            InfoBar.error(
                title="設定エラー",
                content=message,
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )
