#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初回起動時ウェルカム/セットアップウィザード

ユーザーが初めてアプリケーションを起動した際に、
基本的な設定手順を案内するセットアップウィザード
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QWizard, QWizardPage
)

from qfluentwidgets import (
    TitleLabel, BodyLabel, CaptionLabel,
    PrimaryPushButton, PushButton, CardWidget,
    StrongBodyLabel
)


class WelcomePage(QWizardPage):
    """ウェルカムページ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("JRA-Data Collector へようこそ")
        self.setSubTitle("競馬データの効率的な管理を始めましょう")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        # ウェルカムメッセージ
        welcome_card = CardWidget()
        welcome_layout = QVBoxLayout(welcome_card)
        welcome_layout.setSpacing(15)
        welcome_layout.setContentsMargins(30, 25, 30, 25)

        welcome_title = TitleLabel("🏇 JRA-Data Collector")
        welcome_title.setAlignment(Qt.AlignCenter)
        welcome_layout.addWidget(welcome_title)

        welcome_desc = BodyLabel(
            "このアプリケーションは、JRA-VAN Data Labのデータを効率的に取得・管理し、\n"
            "データベースへの保存とエクスポート機能を提供します。\n\n"
            "初回セットアップでは、以下の設定を行います："
        )
        welcome_desc.setAlignment(Qt.AlignCenter)
        welcome_desc.setWordWrap(True)
        welcome_layout.addWidget(welcome_desc)

        # セットアップ項目リスト
        setup_list_layout = QVBoxLayout()
        setup_list_layout.setSpacing(8)

        setup_items = [
            ("🔗", "JV-Link", "JRA-VAN Data Labとの接続設定"),
            ("🗄️", "データベース", "データ保存先の設定"),
            ("✅", "完了", "設定確認とアプリケーション開始")
        ]

        for icon, title, description in setup_items:
            item_layout = QHBoxLayout()
            item_layout.setSpacing(15)

            icon_label = BodyLabel(icon)
            icon_label.setFixedWidth(30)
            item_layout.addWidget(icon_label)

            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)

            title_label = StrongBodyLabel(title)
            desc_label = CaptionLabel(description)
            desc_label.setStyleSheet("color: #666666;")

            text_layout.addWidget(title_label)
            text_layout.addWidget(desc_label)

            item_layout.addLayout(text_layout)
            item_layout.addStretch()

            setup_list_layout.addLayout(item_layout)

        welcome_layout.addLayout(setup_list_layout)
        welcome_layout.addStretch()

        layout.addWidget(welcome_card)
        layout.addStretch()

        # 説明テキスト
        note_label = CaptionLabel(
            "※ このウィザードはいつでも設定画面から再実行できます。"
        )
        note_label.setStyleSheet("color: #888888;")
        note_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(note_label)


class JVLinkSetupPage(QWizardPage):
    """JV-Link設定ページ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("JV-Link 設定")
        self.setSubTitle("JRA-VAN Data Labとの接続を設定します")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        # 説明カード
        info_card = CardWidget()
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(15)
        info_layout.setContentsMargins(25, 20, 25, 20)

        info_title = StrongBodyLabel("JV-Link 設定について")
        info_layout.addWidget(info_title)

        info_text = BodyLabel(
            "JV-Linkは、JRA-VAN Data Labからデータを取得するために必要なコンポーネントです。\n\n"
            "設定には以下の情報が必要です：\n"
            "• サービスキー（JRA-VANから提供）\n"
            "• ユーザーID（JRA-VANアカウント）\n"
            "• パスワード（JRA-VANアカウント）\n\n"
            "これらの設定は、JV-Link公式設定ダイアログで行います。"
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        layout.addWidget(info_card)

        # セットアップボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # ★修正★: PrimaryPushButtonからFluentIconを削除
        self.setup_button = PrimaryPushButton("JV-Link設定を開く")
        self.setup_button.setFixedSize(200, 40)
        self.setup_button.clicked.connect(self.open_jvlink_settings)
        button_layout.addWidget(self.setup_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # ステータス表示
        self.status_layout = QVBoxLayout()
        layout.addLayout(self.status_layout)

        layout.addStretch()

        # 内部状態
        self.setup_completed = False

    def open_jvlink_settings(self):
        """JV-Link設定ダイアログを開く"""
        try:
            # 親ウィザードのapp_controllerを取得
            wizard = self.wizard()
            if hasattr(wizard, 'app_controller'):
                wizard.app_controller.open_jvlink_settings_dialog()
                self.setup_completed = True
                self.show_setup_complete()
            else:
                self.show_setup_error("アプリケーションコントローラーが見つかりません")

        except Exception as e:
            self.show_setup_error(f"JV-Link設定でエラーが発生しました: {e}")

    def show_setup_complete(self):
        """設定完了メッセージを表示"""
        self.clear_status()

        success_card = CardWidget()
        success_layout = QVBoxLayout(success_card)
        success_layout.setContentsMargins(20, 15, 20, 15)

        success_label = BodyLabel("✅ JV-Link設定が完了しました")
        success_label.setStyleSheet("color: #107c10; font-weight: bold;")
        success_layout.addWidget(success_label)

        self.status_layout.addWidget(success_card)

        # 次のページに進むボタンを有効化
        self.completeChanged.emit()

    def show_setup_error(self, error_message: str):
        """設定エラーメッセージを表示"""
        self.clear_status()

        error_card = CardWidget()
        error_layout = QVBoxLayout(error_card)
        error_layout.setContentsMargins(20, 15, 20, 15)

        error_label = BodyLabel(f"❌ エラー: {error_message}")
        error_label.setStyleSheet("color: #d13438; font-weight: bold;")
        error_label.setWordWrap(True)
        error_layout.addWidget(error_label)

        retry_label = CaptionLabel("再度「JV-Link設定を開く」ボタンをクリックしてください。")
        retry_label.setStyleSheet("color: #666666;")
        error_layout.addWidget(retry_label)

        self.status_layout.addWidget(error_card)

    def clear_status(self):
        """ステータス表示をクリア"""
        while self.status_layout.count():
            child = self.status_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def isComplete(self):
        """ページが完了しているかどうかを判定"""
        return self.setup_completed


class DatabaseSetupPage(QWizardPage):
    """データベース設定ページ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("データベース設定")
        self.setSubTitle("データの保存先を設定します")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        # 説明カード
        info_card = CardWidget()
        info_layout = QVBoxLayout(info_card)
        info_layout.setSpacing(15)
        info_layout.setContentsMargins(25, 20, 25, 20)

        info_title = StrongBodyLabel("データベース設定について")
        info_layout.addWidget(info_title)

        info_text = BodyLabel(
            "取得したJRAデータの保存先を設定します。\n\n"
            "推奨設定：\n"
            "• 初心者：SQLite（設定が簡単、ファイルベース）\n"
            "• 高度な用途：PostgreSQL、MySQL（サーバーベース、高性能）\n\n"
            "デフォルトではSQLiteが設定されているため、\n"
            "特別な要件がなければそのまま進んでください。"
        )
        info_text.setWordWrap(True)
        info_layout.addWidget(info_text)

        layout.addWidget(info_card)

        # データベース設定ボタン
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # ★修正★: PushButtonからFluentIconを削除
        self.setup_button = PushButton("データベース設定を開く")
        self.setup_button.setFixedSize(200, 40)
        self.setup_button.clicked.connect(self.open_database_settings)
        button_layout.addWidget(self.setup_button)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # ステータス表示
        self.status_layout = QVBoxLayout()
        layout.addLayout(self.status_layout)

        # デフォルト設定の表示
        self.show_current_settings()

        layout.addStretch()

    def open_database_settings(self):
        """データベース設定画面を開く"""
        try:
            # 親ウィザードから設定画面を開く
            wizard = self.wizard()
            if hasattr(wizard, 'app_controller') and hasattr(wizard.app_controller, 'main_window'):
                main_window = wizard.app_controller.main_window
                if hasattr(main_window, 'navigationInterface'):
                    # 設定画面に切り替え
                    main_window.navigationInterface.setCurrentItem("Settings")
                    wizard.accept()  # ウィザードを閉じる

        except Exception as e:
            self.show_setup_error(f"設定画面を開けませんでした: {e}")

    def show_current_settings(self):
        """現在のデータベース設定を表示"""
        self.clear_status()

        settings_card = CardWidget()
        settings_layout = QVBoxLayout(settings_card)
        settings_layout.setContentsMargins(20, 15, 20, 15)

        try:
            wizard = self.wizard()
            if hasattr(wizard, 'app_controller'):
                db_info = wizard.app_controller.get_current_database_info()
                config = db_info.get('config', {})

                title_label = StrongBodyLabel("現在の設定:")
                settings_layout.addWidget(title_label)

                type_label = BodyLabel(f"タイプ: {config.get('type', 'SQLite')}")
                settings_layout.addWidget(type_label)

                if config.get('type') == 'SQLite':
                    path_label = BodyLabel(f"ファイル: {config.get('db_name', 'jra_data.db')}")
                    settings_layout.addWidget(path_label)
                else:
                    host_label = BodyLabel(f"ホスト: {config.get('host', 'localhost')}")
                    db_label = BodyLabel(f"データベース: {config.get('db_name', '')}")
                    settings_layout.addWidget(host_label)
                    settings_layout.addWidget(db_label)

                status_label = BodyLabel("✅ この設定で続行できます")
                status_label.setStyleSheet("color: #107c10; font-weight: bold;")
                settings_layout.addWidget(status_label)

            else:
                error_label = BodyLabel("設定情報を取得できませんでした")
                error_label.setStyleSheet("color: #d13438;")
                settings_layout.addWidget(error_label)

        except Exception as e:
            error_label = BodyLabel(f"設定表示エラー: {e}")
            error_label.setStyleSheet("color: #d13438;")
            settings_layout.addWidget(error_label)

        self.status_layout.addWidget(settings_card)

    def show_setup_error(self, error_message: str):
        """設定エラーメッセージを表示"""
        self.clear_status()

        error_card = CardWidget()
        error_layout = QVBoxLayout(error_card)
        error_layout.setContentsMargins(20, 15, 20, 15)

        error_label = BodyLabel(f"❌ エラー: {error_message}")
        error_label.setStyleSheet("color: #d13438; font-weight: bold;")
        error_label.setWordWrap(True)
        error_layout.addWidget(error_label)

        self.status_layout.addWidget(error_card)

    def clear_status(self):
        """ステータス表示をクリア"""
        while self.status_layout.count():
            child = self.status_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def isComplete(self):
        """ページは常に完了とみなす（デフォルト設定があるため）"""
        return True


class CompletionPage(QWizardPage):
    """完了ページ"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTitle("セットアップ完了")
        self.setSubTitle("JRA-Data Collector の準備が整いました")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)

        # 完了メッセージ
        completion_card = CardWidget()
        completion_layout = QVBoxLayout(completion_card)
        completion_layout.setSpacing(15)
        completion_layout.setContentsMargins(30, 25, 30, 25)

        completion_title = TitleLabel("🎉 セットアップ完了！")
        completion_title.setAlignment(Qt.AlignCenter)
        completion_layout.addWidget(completion_title)

        completion_desc = BodyLabel(
            "JRA-Data Collector の基本設定が完了しました。\n\n"
            "これで以下の機能をご利用いただけます：\n"
            "• JRA-VAN Data Labからのデータ取得\n"
            "• データベースへの自動保存\n"
            "• 取得データのエクスポート\n"
            "• リアルタイム速報の受信\n\n"
            "「完了」をクリックして、アプリケーションを開始してください。"
        )
        completion_desc.setAlignment(Qt.AlignCenter)
        completion_desc.setWordWrap(True)
        completion_layout.addWidget(completion_desc)

        completion_layout.addStretch()
        layout.addWidget(completion_card)

        # 次のステップガイド
        guide_card = CardWidget()
        guide_layout = QVBoxLayout(guide_card)
        guide_layout.setContentsMargins(25, 20, 25, 20)

        guide_title = StrongBodyLabel("💡 次にすること")
        guide_layout.addWidget(guide_title)

        guide_text = BodyLabel(
            "1. ダッシュボードで「一括データを取得」を実行\n"
            "2. 必要なデータ種別と取得開始日を選択\n"
            "3. データ取得の完了を待つ\n"
            "4. 「差分データを取得」で最新データを保持"
        )
        guide_layout.addWidget(guide_text)

        layout.addWidget(guide_card)
        layout.addStretch()


class WelcomeWizard(QWizard):
    """ウェルカム/セットアップウィザード"""

    # ウィザード完了シグナル
    setup_completed = Signal()

    def __init__(self, app_controller=None, parent=None):
        super().__init__(parent)
        self.app_controller = app_controller

        self.setWindowTitle("JRA-Data Collector セットアップ")
        self.setFixedSize(700, 500)
        self.setWizardStyle(QWizard.ModernStyle)

        # ページを追加
        self.welcome_page = WelcomePage()
        self.jvlink_page = JVLinkSetupPage()
        self.database_page = DatabaseSetupPage()
        self.completion_page = CompletionPage()

        self.addPage(self.welcome_page)
        self.addPage(self.jvlink_page)
        self.addPage(self.database_page)
        self.addPage(self.completion_page)

        # ボタンテキストをカスタマイズ
        self.setButtonText(QWizard.NextButton, "次へ ➤")
        self.setButtonText(QWizard.BackButton, "◀ 戻る")
        self.setButtonText(QWizard.FinishButton, "完了")
        self.setButtonText(QWizard.CancelButton, "キャンセル")

        # スタイル設定
        self.setStyleSheet("""
            QWizard {
                background-color: #f8f9fa;
            }
            QWizard QWidget {
                font-family: "Segoe UI", "Yu Gothic UI", sans-serif;
            }
            QWizard .QLabel {
                color: #2d3748;
            }
        """)

    def accept(self):
        """ウィザード完了時の処理"""
        super().accept()
        self.setup_completed.emit()

    @staticmethod
    def should_show_wizard(settings_manager) -> bool:
        """
        ウィザードを表示すべきかどうかを判定

        Args:
            settings_manager: 設定マネージャー

        Returns:
            ウィザードを表示すべき場合True
        """
        try:
            # 設定ファイルが存在しない場合は表示
            if not settings_manager.config_path.exists():
                return True

            # 初回セットアップ完了フラグを確認
            if settings_manager.config.has_section('Application'):
                setup_completed = settings_manager.config.getboolean(
                    'Application', 'initial_setup_completed', fallback=False)
                return not setup_completed
            else:
                return True

        except Exception:
            # エラーの場合は安全のため表示
            return True

    @staticmethod
    def mark_setup_completed(settings_manager):
        """
        初回セットアップ完了をマーク

        Args:
            settings_manager: 設定マネージャー
        """
        try:
            if not settings_manager.config.has_section('Application'):
                settings_manager.config.add_section('Application')

            settings_manager.config.set('Application', 'initial_setup_completed', 'true')
            settings_manager.save()

        except Exception as e:
            import logging
            logging.error(f"セットアップ完了マーク失敗: {e}")
