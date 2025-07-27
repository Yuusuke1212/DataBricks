"""
JV-Link フィードバックシステム

レポート「セクション4.2: エラーハンドリングと通知」
Table 1「JV-Linkリターンコードとユーザーフィードバックのマッピング」に基づく
統一フィードバックシステムの実装
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, Callable
from PySide6.QtCore import QObject, Signal, Qt
from qfluentwidgets import InfoBar, InfoBarPosition, MessageBox
from qfluentwidgets import FluentIcon as FIF


class FeedbackType(Enum):
    """フィードバック種別"""
    SUCCESS = "success"
    INFO = "info" 
    WARNING = "warning"
    ERROR = "error"


@dataclass
class FeedbackAction:
    """フィードバックアクション定義"""
    text: str
    callback: Optional[Callable] = None
    icon: Optional[str] = None


@dataclass
class FeedbackMapping:
    """フィードバックマッピング定義"""
    type: FeedbackType
    title: str
    message: str
    action: Optional[FeedbackAction] = None
    duration: int = 3000


class JVLinkFeedbackSystem:
    """
    JV-Linkリターンコード用フィードバックシステム
    レポート Table 1 に基づく実装
    """
    
    # レポート Table 1: JV-Linkリターンコードとユーザーフィードバックのマッピング
    FEEDBACK_MAPPINGS: Dict[tuple, FeedbackMapping] = {
        # JVOpen リターンコード
        ("JVOpen", -1): FeedbackMapping(
            type=FeedbackType.INFO,
            title="データなし",
            message="指定された条件に合致する新しいデータはありません。",
            duration=2000
        ),
        
        ("JVOpen", -301): FeedbackMapping(
            type=FeedbackType.ERROR,
            title="認証失敗",
            message="認証に失敗しました。利用キーが正しいか確認してください。",
            action=FeedbackAction(
                text="設定画面を開く",
                icon="SETTING"
            ),
            duration=5000
        ),
        
        ("JVOpen", -302): FeedbackMapping(
            type=FeedbackType.ERROR,
            title="利用キー期限切れ",
            message="利用キーの有効期限が切れています。JRA-VANのサイトで契約状況を確認してください。",
            action=FeedbackAction(
                text="JRA-VANサイトを開く",
                icon="GLOBE"
            ),
            duration=0  # 手動で閉じるまで表示
        ),
        
        ("JVOpen", -303): FeedbackMapping(
            type=FeedbackType.WARNING,
            title="利用キー未設定",
            message="利用キーが設定されていません。データ取得の前に設定が必要です。",
            action=FeedbackAction(
                text="設定画面を開く",
                icon="SETTING"
            ),
            duration=0
        ),
        
        ("JVOpen", -504): FeedbackMapping(
            type=FeedbackType.WARNING,
            title="サーバーメンテナンス",
            message="サーバーは現在メンテナンス中です。しばらく時間をおいてから再度お試しください。",
            duration=3000
        ),
        
        # JVStatus リターンコード
        ("JVStatus", -502): FeedbackMapping(
            type=FeedbackType.ERROR,
            title="ダウンロード失敗",
            message="データのダウンロードに失敗しました。ネットワーク接続を確認してください。",
            action=FeedbackAction(
                text="再試行",
                icon="SYNC"
            ),
            duration=5000
        ),
        
        # JVRead リターンコード
        ("JVRead", -402): FeedbackMapping(
            type=FeedbackType.ERROR,
            title="ファイル破損",
            message="ダウンロードしたファイルが破損しています。キャッシュをクリアして再試行します。",
            duration=5000
        ),
        
        # JVClose リターンコード (成功)
        ("JVClose", 0): FeedbackMapping(
            type=FeedbackType.SUCCESS,
            title="データ取得完了",
            message="データ取得処理が正常に終了しました。",
            duration=2000
        ),
        
        # 汎用エラー
        ("Generic", -101): FeedbackMapping(
            type=FeedbackType.ERROR,
            title="初期化エラー",
            message="JV-Linkの初期化に失敗しました。アプリケーションを再起動してください。",
            action=FeedbackAction(
                text="アプリケーション再起動",
                icon="POWER_BUTTON"
            ),
            duration=0
        ),
    }

    def __init__(self, parent_widget):
        self.parent_widget = parent_widget
        self.action_callbacks = {}

    def register_action_callback(self, action_key: str, callback: Callable):
        """アクションコールバックを登録"""
        self.action_callbacks[action_key] = callback

    def show_feedback(self, api_method: str, return_code: int, context: Dict = None):
        """
        JV-Linkリターンコードに基づくフィードバック表示
        
        Args:
            api_method: JV-Link APIメソッド名 (例: "JVOpen", "JVStatus")
            return_code: リターンコード
            context: 追加のコンテキスト情報
        """
        # マッピングテーブルから対応するフィードバックを検索
        mapping_key = (api_method, return_code)
        feedback = self.FEEDBACK_MAPPINGS.get(mapping_key)
        
        if not feedback:
            # 未定義のリターンコードの場合は汎用エラー
            feedback = FeedbackMapping(
                type=FeedbackType.ERROR,
                title="予期しないエラー", 
                message=f"{api_method}でエラーが発生しました (コード: {return_code})",
                duration=5000
            )
        
        self._display_feedback(feedback, context)

    def _display_feedback(self, feedback: FeedbackMapping, context: Dict = None):
        """フィードバックを実際に表示"""
        # InfoBarの表示
        info_bar = self._create_info_bar(feedback)
        
        # 重大なエラーの場合は追加でモーダルダイアログを表示
        if feedback.type == FeedbackType.ERROR and feedback.duration == 0:
            self._show_error_dialog(feedback)

    def _create_info_bar(self, feedback: FeedbackMapping) -> InfoBar:
        """InfoBarを作成・表示"""
        # フィードバック種別に応じたInfoBar表示
        if feedback.type == FeedbackType.SUCCESS:
            info_bar = InfoBar.success(
                title=feedback.title,
                content=feedback.message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=feedback.duration,
                parent=self.parent_widget
            )
        elif feedback.type == FeedbackType.INFO:
            info_bar = InfoBar.info(
                title=feedback.title,
                content=feedback.message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=feedback.duration,
                parent=self.parent_widget
            )
        elif feedback.type == FeedbackType.WARNING:
            info_bar = InfoBar.warning(
                title=feedback.title,
                content=feedback.message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=feedback.duration,
                parent=self.parent_widget
            )
        else:  # ERROR
            info_bar = InfoBar.error(
                title=feedback.title,
                content=feedback.message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=feedback.duration,
                parent=self.parent_widget
            )
        
        # アクションボタンの追加
        if feedback.action:
            self._add_action_to_info_bar(info_bar, feedback.action)
        
        return info_bar

    def _add_action_to_info_bar(self, info_bar: InfoBar, action: FeedbackAction):
        """InfoBarにアクションボタンを追加"""
        # Note: qfluentwidgetsのInfoBarはアクションボタンの追加が制限されている場合があります
        # この場合は、アクションボタン付きの独自InfoBarやダイアログで代替
        action_callback = self._get_action_callback(action)
        if action_callback:
            # アクションボタンクリック時のコールバック設定
            # 実装詳細はqfluentwidgetsのバージョンに依存
            pass

    def _show_error_dialog(self, feedback: FeedbackMapping):
        """重大なエラー用のモーダルダイアログを表示"""
        dialog = MessageBox(
            title=feedback.title,
            content=feedback.message,
            parent=self.parent_widget
        )
        
        if feedback.action:
            # カスタムボタンの追加
            action_callback = self._get_action_callback(feedback.action)
            if action_callback:
                dialog.yesButton.setText(feedback.action.text)
                dialog.yesButton.clicked.connect(action_callback)
        
        dialog.exec()

    def _get_action_callback(self, action: FeedbackAction) -> Optional[Callable]:
        """アクションに対応するコールバックを取得"""
        # アクションテキストに基づいてコールバックを解決
        action_map = {
            "設定画面を開く": "open_settings",
            "JRA-VANサイトを開く": "open_jra_van_site",
            "再試行": "retry_operation",
            "アプリケーション再起動": "restart_application"
        }
        
        callback_key = action_map.get(action.text)
        if callback_key:
            return self.action_callbacks.get(callback_key)
        
        return None

    def register_standard_callbacks(self, main_window):
        """標準的なアクションコールバックを登録"""
        self.register_action_callback("open_settings", 
                                    lambda: main_window.switchTo(main_window.settings_view))
        
        self.register_action_callback("open_jra_van_site",
                                    lambda: self._open_external_url("https://jra-van.jp/"))
        
        self.register_action_callback("retry_operation",
                                    lambda: main_window.retry_last_operation())
        
        self.register_action_callback("restart_application",
                                    lambda: main_window.restart_application())

    def _open_external_url(self, url: str):
        """外部URLを開く"""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))


# グローバルフィードバックシステムインスタンス
_feedback_system: Optional[JVLinkFeedbackSystem] = None


def get_feedback_system() -> Optional[JVLinkFeedbackSystem]:
    """グローバルフィードバックシステムを取得"""
    return _feedback_system


def initialize_feedback_system(parent_widget) -> JVLinkFeedbackSystem:
    """フィードバックシステムを初期化"""
    global _feedback_system
    _feedback_system = JVLinkFeedbackSystem(parent_widget)
    return _feedback_system


def show_jvlink_feedback(api_method: str, return_code: int, context: Dict = None):
    """便利関数：JV-Linkフィードバックを表示"""
    if _feedback_system:
        _feedback_system.show_feedback(api_method, return_code, context) 