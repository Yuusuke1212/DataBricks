import logging
from PySide6.QtCore import Signal, Qt, Slot
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QScrollArea

from qfluentwidgets import (
    TitleLabel, SettingCardGroup, SettingCard, SwitchSettingCard,
    FolderListSettingCard, HyperlinkCard, PrimaryPushButton,
    PasswordLineEdit, InfoBar, InfoBarPosition, FluentIcon as FIF
)

from ..utils.theme_manager import AppTheme, get_theme_manager


class SettingsView(QWidget):
    """
    モダンな設定画面 - UI/UX改善指示書準拠
    Fluent Designの原則に基づき、qfluentwidgetsの標準コンポーネントで再構築。
    """
    settings_saved = Signal(dict)
    theme_changed = Signal(str)
    jvlink_dialog_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsView")
        self.theme_manager = get_theme_manager()
        self._init_ui()
        self._load_current_settings()

    def _init_ui(self):
        """UIの初期化 - 8pxスペーシングシステムとコントラスト改善を適用"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- タイトル ---
        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(36, 20, 36, 12)
        title_label = TitleLabel("設定", title_container)
        title_layout.addWidget(title_label)
        layout.addWidget(title_container)

        # --- スクロールエリア ---
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(36, 8, 36, 24)
        scroll_layout.setSpacing(16)
        scroll_widget.setObjectName("SettingsScrollWidget")
        scroll_area.setWidget(scroll_widget)

        # --- 設定グループ ---
        self._create_account_group(scroll_layout)
        self._create_data_storage_group(scroll_layout)
        self._create_appearance_group(scroll_layout)
        self._create_help_group(scroll_layout)

        # --- 保存ボタン ---
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setContentsMargins(36, 12, 36, 12)
        button_layout.addStretch()
        self.save_button = PrimaryPushButton("設定を保存")
        self.save_button.setIcon(FIF.SAVE)
        self.save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_button)
        layout.addWidget(button_container)

    def _create_account_group(self, parent_layout):
        account_group = SettingCardGroup("🔐 アカウント情報", self)

        self.service_key_card = SettingCard(
            FIF.KEY, "JRA-VAN サービスキー", "データ取得に必要な認証キー"
        )
        self.service_key_input = PasswordLineEdit(self.service_key_card)
        self.service_key_input.setPlaceholderText("サービスキーを入力してください")
        self.service_key_card.hBoxLayout.addWidget(self.service_key_input)
        account_group.addSettingCard(self.service_key_card)

        parent_layout.addWidget(account_group)

    def _create_data_storage_group(self, parent_layout):
        storage_group = SettingCardGroup("💾 データ保存と連携", self)

        self.save_data_switch = SwitchSettingCard(
            FIF.SAVE, "ローカルデータ保存", "取得したデータをローカルファイルに保存する"
        )
        storage_group.addSettingCard(self.save_data_switch)

        self.save_path_card = FolderListSettingCard(
            [], "データファイルの保存先", "データファイルを保存するフォルダを選択してください"
        )
        storage_group.addSettingCard(self.save_path_card)

        self.jvlink_card = SettingCard(
            FIF.CONNECT, "JV-Link 設定", "公式のJV-Link設定ダイアログを開きます"
        )
        self.jvlink_card.clicked.connect(self.jvlink_dialog_requested)
        storage_group.addSettingCard(self.jvlink_card)

        parent_layout.addWidget(storage_group)

    def _create_appearance_group(self, parent_layout):
        appearance_group = SettingCardGroup("🎨 外観", self)
        self.theme_switch = SwitchSettingCard(
            FIF.BRUSH, "ダークモード", "アプリケーションの外観を暗いテーマに切り替える"
        )
        self.theme_switch.checkedChanged.connect(self._on_theme_switch_changed)
        appearance_group.addSettingCard(self.theme_switch)
        parent_layout.addWidget(appearance_group)

    def _create_help_group(self, parent_layout):
        help_group = SettingCardGroup("🔗 ヘルプとサポート", self)

        jra_van_link = HyperlinkCard(
            "jra-van-link", "JRA-VAN 公式サイト", "サービス情報とユーザーサポート",
            "https://jra-van.jp/", FIF.HELP
        )
        help_group.addSettingCard(jra_van_link)

        spec_link = HyperlinkCard(
            "spec-link", "JV-Link SDK 仕様書", "開発者向けの詳細な技術文書",
            "https://jra-van.jp/dlb/sdk/index.html", FIF.DOCUMENT
        )
        help_group.addSettingCard(spec_link)

        parent_layout.addWidget(help_group)

    def _load_current_settings(self):
        # このメソッドはAppControllerから呼ばれることを想定
        pass

    @Slot(bool)
    def _on_theme_switch_changed(self, checked: bool):
        theme = AppTheme.DARK if checked else AppTheme.LIGHT
        self.theme_manager.set_theme(theme)

    def on_theme_changed(self, theme: AppTheme):
        self.theme_switch.setChecked(theme == AppTheme.DARK)

    def _on_save(self):
        if self._validate_settings():
            settings = self._gather_settings()
            logging.info("設定が検証されました。保存シグナルを発行します。")
            self.settings_saved.emit(settings)
            InfoBar.success(
                "保存完了", "設定が正常に保存されました。", parent=self,
                isClosable=True, position=InfoBarPosition.TOP, duration=2000
            )
        else:
            logging.warning("設定の検証に失敗しました。")
            # ここでユーザーにエラーを通知することもできます
            # 例: self.show_error_dialog("入力内容を確認してください。")
            pass

    def update_settings_display(self, settings: dict):
        try:
            if 'service_key' in settings:
                self.service_key_input.setText(settings['service_key'])
            if 'save_data' in settings:
                self.save_data_switch.setChecked(settings['save_data'])
            if 'save_path' in settings:
                self.save_path_card.setFolders([settings['save_path']])
            if 'theme' in settings:
                is_dark = str(settings['theme']).upper() == 'DARK'
                self.theme_switch.setChecked(is_dark)
        except Exception as e:
            logging.error(f"設定表示の更新エラー: {e}")

    def _gather_settings(self) -> dict:
        theme_value = AppTheme.DARK.value if self.theme_switch.isChecked() else AppTheme.LIGHT.value
        save_paths = self.save_path_card.getFolders()

        return {
            'service_key': self.service_key_input.text(),
            'save_data': self.save_data_switch.isChecked(),
            'save_path': save_paths[0] if save_paths else "",
            'theme': theme_value,
        }

    def _validate_settings(self) -> bool:
        # 他のカードのバリデーションもここに追加できます
        if not self.service_key_input.text().strip():
            InfoBar.warning(
                "入力エラー", "サービスキーは必須項目です。", parent=self,
                isClosable=True, position=InfoBarPosition.TOP, duration=3000
            )
            return False
        return True
