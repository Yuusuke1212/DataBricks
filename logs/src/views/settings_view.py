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
from pathlib import Path


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
        self.save_button.setIcon(FIF.SAVE)
        self.save_button.clicked.connect(self._on_save)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)

    def _create_account_group(self, parent_layout):
        """アカウント情報設定グループ"""
        account_group = SettingCardGroup("🔐 アカウント情報", self)
        
        # サービスキー設定カード - ★修正★: アイコンなしで作成
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
        
        # データ保存フラグ - ★修正★: アイコンなしで作成
        self.save_data_switch = SwitchSettingCard(
            "ローカルデータ保存",
            "取得したデータをローカルファイルに保存する"
        )
        storage_group.addSettingCard(self.save_data_switch)
        
        # ★修正★: FolderListSettingCardを通常のSettingCardに変更
        self.save_path_card = SettingCard(
            "保存先フォルダ",
            "データファイルの保存先を設定してください"
        )
        
        # フォルダ選択機能を追加
        self.save_path_input = LineEdit()
        self.save_path_input.setPlaceholderText("フォルダパスを入力または参照ボタンをクリック...")
        self.save_path_input.setReadOnly(True)
        
        self.browse_button = PushButton("参照")
        self.browse_button.clicked.connect(self._browse_folder)
        
        # レイアウトに追加
        folder_layout = QHBoxLayout()
        folder_layout.addWidget(self.save_path_input)
        folder_layout.addWidget(self.browse_button)
        folder_layout.setContentsMargins(0, 0, 0, 0)
        
        self.save_path_card.hBoxLayout.addLayout(folder_layout)
        self.save_path_card.hBoxLayout.addSpacing(16)
        
        storage_group.addSettingCard(self.save_path_card)
        
        parent_layout.addWidget(storage_group)

    def _create_appearance_group(self, parent_layout):
        """表示設定グループ"""
        appearance_group = SettingCardGroup("🎨 表示設定", self)
        
        # テーマ設定 - Light/Darkモード切り替え - ★修正★: アイコンなしで作成
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
        
        # JRA-VAN公式サイト - ★修正★: アイコン引数を削除
        jra_van_link = HyperlinkCard(
            "https://jra-van.jp/",
            "JRA-VAN公式サイト",
            "サービス情報とユーザーサポート",
            "契約状況の確認やサポート情報を参照できます"
        )
        links_group.addSettingCard(jra_van_link)
        
        # JV-Link仕様書 - ★修正★: アイコン引数を削除
        spec_link = HyperlinkCard(
            "https://jra-van.jp/dlb/sdk/index.html",
            "JV-Link SDK仕様書",
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

    def _browse_folder(self):
        """フォルダ参照ダイアログを表示"""
        try:
            folder = QFileDialog.getExistingDirectory(
                self, 
                "データ保存先フォルダを選択",
                self.save_path_input.text() or str(Path.home())
            )
            if folder:
                self.save_path_input.setText(folder)
        except Exception as e:
            logging.error(f"フォルダ参照エラー: {e}")

    def update_settings_display(self, settings: dict):
        """設定値をUIに反映（修正版）"""
        try:
            if 'service_key' in settings:
                self.service_key_input.setText(settings['service_key'])
            if 'save_data' in settings:
                self.save_data_switch.setChecked(settings['save_data'])
            if 'save_path' in settings:
                # ★修正★: FolderListSettingCardからLineEditに変更
                self.save_path_input.setText(str(settings['save_path']))
            if 'theme' in settings:
                theme_value = settings['theme']
                # ★修正★: 型安全なAppTheme比較
                try:
                    if hasattr(AppTheme, 'DARK') and hasattr(AppTheme.DARK, 'value'):
                        is_dark = theme_value == AppTheme.DARK.value
                    else:
                        is_dark = str(theme_value).upper() == 'DARK'
                except (AttributeError, TypeError):
                    is_dark = False  # デフォルトはライトテーマ
                self.theme_switch.setChecked(is_dark)
        except Exception as e:
            logging.error(f"設定表示更新エラー: {e}")

    def _gather_settings(self) -> dict:
        """UIから設定値を収集（修正版）"""
        # ★修正★: テーマ値の型安全なアクセス
        try:
            current_theme = self.theme_manager.current_theme
            theme_value = current_theme.value if hasattr(current_theme, 'value') else str(current_theme)
        except (AttributeError, TypeError):
            theme_value = 'LIGHT'  # デフォルト値
        
        return {
            'service_key': self.service_key_input.text(),
            'save_data': self.save_data_switch.isChecked(),
            'save_path': self.save_path_input.text(),  # ★修正★: LineEditから取得
            'theme': theme_value,
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
