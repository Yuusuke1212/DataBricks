"""
高度なガイダンスシステム

レポート「セクション4.3: オンボーディングとガイダンス」準拠
TeachingTipコンポーネントを活用したコンテキストヘルプシステム
"""

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional, Callable
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget
from qfluentwidgets import TeachingTip, InfoBarIcon, FluentIcon as FIF


class GuidanceType(Enum):
    """ガイダンス種別"""
    TOOLTIP = "tooltip"
    TEACHING_TIP = "teaching_tip"
    OVERLAY = "overlay"


@dataclass
class GuidanceContent:
    """ガイダンスコンテンツ定義"""
    title: str
    description: str
    guidance_type: GuidanceType = GuidanceType.TEACHING_TIP
    icon: str = "INFO"
    action_text: Optional[str] = None
    action_callback: Optional[Callable] = None


class ContextualGuidanceSystem:
    """
    コンテキスト依存ガイダンスシステム
    
    専門的な設定項目に対してTeachingTipを使用した
    詳細説明とガイダンスを提供
    """

    # レポート セクション4.3: 設定項目ガイダンス定義
    GUIDANCE_DEFINITIONS: Dict[str, GuidanceContent] = {
        # データ取得画面のガイダンス
        "data_retrieval_option_normal": GuidanceContent(
            title="差分データとは？",
            description="前回取得以降に更新されたデータのみを取得します。\n"
                       "通常の運用では最も効率的で、ネットワーク負荷も最小限に抑えられます。\n"
                       "初回取得時は「セットアップデータ」をお選びください。",
            icon="INFO"
        ),

        "data_retrieval_option_week": GuidanceContent(
            title="今週データとは？",
            description="今週開催分のレース情報を全て取得します。\n"
                       "週の途中から利用開始した場合や、\n"
                       "今週のデータを確実に最新状態にしたい場合に使用します。",
            icon="CALENDAR"
        ),

        "data_retrieval_option_setup": GuidanceContent(
            title="セットアップデータとは？",
            description="初期セットアップ用の全データを取得します。\n"
                       "⚠️ 注意: 大量のデータをダウンロードするため、\n"
                       "完了まで数時間かかる場合があります。\n"
                       "初回利用時のみ実行してください。",
            icon="DOWNLOAD"
        ),

        "data_retrieval_dataspec": GuidanceContent(
            title="データ種別の選択方法",
            description="JRA-VANでは様々な種類のデータが提供されています：\n\n"
                       "• レース情報: 出走表、結果、オッズなど\n"
                       "• 馬情報: 血統、調教、成績など\n"
                       "• 開催情報: スケジュール、天候など\n\n"
                       "必要なデータのみを選択することで、効率的に取得できます。",
            icon="DOCUMENT",
            action_text="詳細な仕様を確認",
        ),

        # 設定画面のガイダンス
        "settings_service_key": GuidanceContent(
            title="JRA-VANサービスキーについて",
            description="JRA-VANとの契約時に発行される認証キーです。\n"
                       "このキーがないとデータを取得できません。\n\n"
                       "サービスキーは以下から取得できます：\n"
                       "1. JRA-VANにログイン\n"
                       "2. マイページ > 利用設定\n"
                       "3. データラボ > サービスキー確認",
            icon="CONNECT",
            action_text="JRA-VAN公式サイトを開く"
        ),

        "settings_data_save": GuidanceContent(
            title="ローカルデータ保存について",
            description="取得したデータをローカルファイルとして保存するかを設定します。\n\n"
                       "【ON】の場合:\n"
                       "• データを再利用可能\n"
                       "• オフライン分析が可能\n"
                       "• ディスク容量が必要\n\n"
                       "【OFF】の場合:\n"
                       "• メモリ上でのみ処理\n"
                       "• ディスク容量を節約\n"
                       "• 再取得が必要",
            icon="SAVE"
        ),

        "settings_theme": GuidanceContent(
            title="テーマ設定について",
            description="アプリケーションの外観を変更できます。\n\n"
                       "【ライトモード】\n"
                       "• 明るい背景\n"
                       "• 昼間の作業に適している\n\n"
                       "【ダークモード】\n"
                       "• 暗い背景\n"
                       "• 長時間作業での眼精疲労軽減\n"
                       "• 夜間作業に適している",
            icon="PALETTE"
        ),

        # エクスポート画面のガイダンス
        "export_table_format": GuidanceContent(
            title="エクスポート形式の選択",
            description="データの用途に応じて適切な形式を選択してください：\n\n"
                       "【CSV形式】\n"
                       "• 汎用性が高い\n"
                       "• Excel、Googleスプレッドシートで開ける\n"
                       "• プログラミング言語での処理に適している\n\n"
                       "【Excel形式】\n"
                       "• 書式設定が保持される\n"
                       "• Excelでの分析に最適\n"
                       "• ファイルサイズが大きい",
            icon="DOCUMENT"
        ),
    }

    def __init__(self, parent_widget: QWidget):
        self.parent_widget = parent_widget
        self.active_tips = {}
        self.action_callbacks = {}

    def register_action_callback(self, guidance_key: str, callback: Callable):
        """アクションコールバックを登録"""
        self.action_callbacks[guidance_key] = callback

    def show_guidance(self, guidance_key: str, target_widget: QWidget, position: QPoint = None):
        """
        指定されたウィジェットに対してガイダンスを表示
        
        Args:
            guidance_key: ガイダンス定義のキー
            target_widget: ガイダンスを表示する対象ウィジェット
            position: 表示位置（省略時は自動計算）
        """
        guidance = self.GUIDANCE_DEFINITIONS.get(guidance_key)
        if not guidance:
            return

        # 既存のTeachingTipがあれば閉じる
        if guidance_key in self.active_tips:
            self.active_tips[guidance_key].close()

        # TeachingTipを作成
        tip = self._create_teaching_tip(guidance, target_widget, position)

        # アクションボタンがある場合はコールバックを設定
        if guidance.action_text and guidance.action_callback:
            # Note: TeachingTipのアクションボタン実装は
            # qfluentwidgetsのバージョンに依存
            pass

        self.active_tips[guidance_key] = tip
        tip.show()

    def _create_teaching_tip(self, guidance: GuidanceContent, target_widget: QWidget, position: QPoint = None) -> TeachingTip:
        """TeachingTipを作成"""
        # アイコンの取得
        icon = getattr(FIF, guidance.icon, FIF.INFO)

        # TeachingTipの作成
        tip = TeachingTip.create(
            target=target_widget,
            icon=InfoBarIcon(icon),
            title=guidance.title,
            content=guidance.description,
            isClosable=True,
            tailPosition=TeachingTip.Position.TOP,
            parent=self.parent_widget
        )

        return tip

    def hide_guidance(self, guidance_key: str):
        """指定されたガイダンスを非表示"""
        if guidance_key in self.active_tips:
            self.active_tips[guidance_key].close()
            del self.active_tips[guidance_key]

    def hide_all_guidance(self):
        """すべてのガイダンスを非表示"""
        for tip in self.active_tips.values():
            tip.close()
        self.active_tips.clear()

    def register_standard_callbacks(self, main_window):
        """標準的なアクションコールバックを登録"""
        self.register_action_callback(
            "data_retrieval_dataspec",
            lambda: self._open_external_url("https://jra-van.jp/dlb/sdk/index.html")
        )

        self.register_action_callback(
            "settings_service_key",
            lambda: self._open_external_url("https://jra-van.jp/")
        )

    def _open_external_url(self, url: str):
        """外部URLを開く"""
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))


class GuidanceHelperMixin:
    """
    ガイダンス機能をビューに追加するためのMixin
    """

    def setup_guidance_system(self, parent_widget: QWidget):
        """ガイダンスシステムをセットアップ"""
        self.guidance_system = ContextualGuidanceSystem(parent_widget)

    def add_guidance_to_widget(self, widget: QWidget, guidance_key: str, trigger_event: str = "hover"):
        """ウィジェットにガイダンスを追加"""
        if not hasattr(self, 'guidance_system'):
            return

        def show_guidance():
            self.guidance_system.show_guidance(guidance_key, widget)

        if trigger_event == "hover":
            widget.enterEvent = lambda event: show_guidance()
        elif trigger_event == "click":
            if hasattr(widget, 'clicked'):
                widget.clicked.connect(show_guidance)

    def create_help_button(self, guidance_key: str) -> 'QPushButton':
        """ヘルプボタンを作成"""
        from qfluentwidgets import TransparentToolButton

        help_button = TransparentToolButton(FIF.HELP)
        help_button.setFixedSize(20, 20)
        help_button.setToolTip("ヘルプを表示")

        def show_help():
            if hasattr(self, 'guidance_system'):
                self.guidance_system.show_guidance(guidance_key, help_button)

        help_button.clicked.connect(show_help)
        return help_button


# グローバルガイダンスシステムインスタンス
_guidance_system: Optional[ContextualGuidanceSystem] = None


def get_guidance_system() -> Optional[ContextualGuidanceSystem]:
    """グローバルガイダンスシステムを取得"""
    return _guidance_system


def initialize_guidance_system(parent_widget: QWidget) -> ContextualGuidanceSystem:
    """ガイダンスシステムを初期化"""
    global _guidance_system
    _guidance_system = ContextualGuidanceSystem(parent_widget)
    return _guidance_system


def show_contextual_guidance(guidance_key: str, target_widget: QWidget):
    """便利関数：コンテキストガイダンスを表示"""
    if _guidance_system:
        _guidance_system.show_guidance(guidance_key, target_widget)
