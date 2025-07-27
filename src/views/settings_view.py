import logging
from datetime import datetime
from PySide6.QtCore import Signal, Qt, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFileDialog,
    QMessageBox,
    QScrollArea,
)

# qfluentwidgets components - レポート セクション3.4準拠のコンポーネント
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
    SettingCardGroup,
    SettingCard,
    SwitchSettingCard,
    FolderListSettingCard,
    HyperlinkCard,
    ScrollArea,
)
from qfluentwidgets import FluentIcon as FIF

from ..utils.theme_manager import AppTheme, get_theme_manager


class SettingsView(QWidget):
    """
    モダンな設定画面 - レポート セクション3.4準拠
    
    JVSetUIProperties APIの外部ダイアログを廃止し、
    アプリケーション内に完全に統合された設定ビューを提供
    """
    settings_saved = Signal(dict)
    db_test_requested = Signal(dict)
    theme_changed = Signal(str)  # テーマ変更シグナル

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsView")
        self.theme_manager = get_theme_manager()
        self._init_ui()
        self._load_current_settings()

    def _init_ui(self):
        """レポート セクション3.4: 設定画面レイアウトの実装"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)

        # タイトル
        title = TitleLabel("設定", self)
        layout.addWidget(title)

        # スクロール可能エリア（将来的な設定項目追加に対応）
        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)  # ExpandLayoutをQVBoxLayoutに変更
        scroll_layout.setSpacing(20)
        
        # 1. アカウント情報グループ
        self._create_account_group(scroll_layout)
        
        # 2. データ保存設定グループ
        self._create_data_storage_group(scroll_layout)
        
        # 3. 表示設定グループ
        self._create_appearance_group(scroll_layout)
        
        # 4. 外部リンクグループ
        self._create_external_links_group(scroll_layout)
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        # 保存ボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.save_button = PrimaryPushButton("設定を保存")
        self.save_button.setIcon(FIF.SAVE.icon())  # .icon()メソッドを使用
        self.save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)

    def _create_account_group(self, parent_layout):
        """アカウント情報設定グループ"""
        account_group = SettingCardGroup("🔐 アカウント情報", self)
        
        # サービスキー設定カード（アイコンなし）
        self.service_key_card = SettingCard(
            "JRA-VANサービスキー",
            "データ取得に必要な認証キーを入力してください"
        )
        
        # PasswordLineEditをカードに組み込み
        self.service_key_input = PasswordLineEdit()
        self.service_key_input.setPlaceholderText("サービスキーを入力...")
        self.service_key_card.hBoxLayout.addWidget(self.service_key_input)
        self.service_key_card.hBoxLayout.addSpacing(16)
        
        account_group.addSettingCard(self.service_key_card)
        parent_layout.addWidget(account_group)

    def _create_data_storage_group(self, parent_layout):
        """データ保存設定グループ"""
        storage_group = SettingCardGroup("💾 データ保存", self)
        
        # データ保存フラグ（アイコンなし）
        self.save_data_switch = SwitchSettingCard(
            "ローカルデータ保存",
            "取得したデータをローカルファイルに保存する"
        )
        storage_group.addSettingCard(self.save_data_switch)
        
        # データ保存パス（引数順序変更）
        self.save_path_card = FolderListSettingCard(
            "保存先フォルダ",
            "データファイルの保存先",
            "データが保存されるフォルダを選択してください"
        )
        storage_group.addSettingCard(self.save_path_card)
        
        parent_layout.addWidget(storage_group)

    def _create_appearance_group(self, parent_layout):
        """表示設定グループ"""
        appearance_group = SettingCardGroup("🎨 表示設定", self)
        
        # テーマ設定 - Light/Darkモード切り替え（アイコンなし）
        self.theme_switch = SwitchSettingCard(
            "ダークモード",
            "アプリケーションの外観を暗いテーマに切り替える"
        )
        self.theme_switch.checkedChanged.connect(self._on_theme_switch_changed)
        appearance_group.addSettingCard(self.theme_switch)
        
        parent_layout.addWidget(appearance_group)

    def _create_external_links_group(self, parent_layout):
        """外部リンクグループ"""
        links_group = SettingCardGroup("🔗 ヘルプとサポート", self)
        
        # JRA-VAN公式サイト
        jra_van_link = HyperlinkCard(
            "https://jra-van.jp/",
            "JRA-VAN公式サイト",
            FIF.GLOBE.icon(),  # .icon()メソッドを使用
            "サービス情報とユーザーサポート",
            "契約状況の確認やサポート情報を参照できます"
        )
        links_group.addSettingCard(jra_van_link)
        
        # JV-Link仕様書
        spec_link = HyperlinkCard(
            "https://jra-van.jp/dlb/sdk/index.html",
            "JV-Link SDK仕様書",
            FIF.DOCUMENT.icon(),  # .icon()メソッドを使用
            "技術仕様とAPI リファレンス",
            "開発者向けの詳細な技術文書を参照できます"
        )
        links_group.addSettingCard(spec_link)
        
        parent_layout.addWidget(links_group)

    def _load_current_settings(self):
        """現在の設定値をUIに反映"""
        # TODO: SettingsManagerから現在の設定を読み込む
        # 現在はダミーデータ
        pass

    @Slot(bool)
    def _on_theme_switch_changed(self, checked: bool):
        """テーマスイッチ変更時の処理"""
        theme = AppTheme.DARK if checked else AppTheme.LIGHT
        self.theme_manager.set_theme(theme)
        
        # メインウィンドウに通知
        if hasattr(self.parent(), 'switch_theme'):
            self.parent().switch_theme(theme)

    def on_theme_changed(self, theme: AppTheme):
        """外部からのテーマ変更通知を受信"""
        # スイッチの状態を同期
        self.theme_switch.setChecked(theme == AppTheme.DARK)

    def _on_save(self):
        """設定保存処理"""
        settings = self._gather_settings()
        
        # 設定の妥当性チェック
        if not self._validate_settings(settings):
            return
            
        # 保存実行
        self.settings_saved.emit(settings)
        
        # 成功通知
        InfoBar.success(
            title="設定保存完了",
            content="設定が正常に保存されました。",
            orient=Qt.Orientation.Horizontal,
            isClosable=True,
            position=InfoBarPosition.TOP,
            duration=2000,
            parent=self
        )

    def _gather_settings(self) -> dict:
        """UIから設定値を収集"""
        return {
            'service_key': self.service_key_input.text(),
            'save_data': self.save_data_switch.isChecked(),
            'save_path': self.save_path_card.folder,
            'theme': self.theme_manager.current_theme.value,
        }

    def _validate_settings(self, settings: dict) -> bool:
        """設定値の妥当性をチェック"""
        # サービスキーの必須チェック
        if not settings.get('service_key', '').strip():
            InfoBar.warning(
                title="入力エラー",
                content="サービスキーは必須項目です。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return False
            
        return True

    def update_settings_display(self, settings: dict):
        """外部から設定値を受信してUI表示を更新"""
        if 'service_key' in settings:
            self.service_key_input.setText(settings['service_key'])
        if 'save_data' in settings:
            self.save_data_switch.setChecked(settings['save_data'])
        if 'save_path' in settings:
            self.save_path_card.folder = settings['save_path']
        if 'theme' in settings:
            theme_value = settings['theme']
            is_dark = theme_value == AppTheme.DARK.value
            self.theme_switch.setChecked(is_dark)
