#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
統一通知管理システム

アプリケーション全体で一貫した視覚的フィードバックを提供する
通知ルールの統一とユーザー体験の向上
"""

import logging
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime

from PySide6.QtCore import QObject, Signal, QTimer
from PySide6.QtWidgets import QMessageBox, QWidget

try:
    from qfluentwidgets import InfoBar, InfoBarPosition, FluentIcon as FIF
    QFLUENTWIDGETS_AVAILABLE = True
except ImportError:
    QFLUENTWIDGETS_AVAILABLE = False
    logging.warning("QFluentWidgets not available. Falling back to standard notifications.")


class NotificationType(Enum):
    """通知の種類"""
    SUCCESS = "success"    # 成功（緑色）
    WARNING = "warning"    # 警告（黄色）
    ERROR = "error"        # エラー（赤色）
    INFO = "info"          # 情報（青色）


class NotificationPriority(Enum):
    """通知の優先度"""
    LOW = 1      # InfoBarのみ
    MEDIUM = 2   # InfoBar + ステータスバー
    HIGH = 3     # InfoBar + ステータスバー + ログ
    CRITICAL = 4 # InfoBar + ステータスバー + ログ + ダイアログ


class NotificationManager(QObject):
    """
    統一通知管理システム

    アプリケーション全体で一貫した通知機能を提供し、
    通知の種類と優先度に応じて適切な表示方法を選択する
    """

    # シグナル定義
    notification_sent = Signal(str, str, str)  # type, message, details

    def __init__(self, main_window: Optional[QWidget] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)

        # 通知履歴
        self.notification_history = []
        self.max_history_size = 100

        # 自動クリアタイマー
        self.auto_clear_timers = {}

    def set_main_window(self, main_window: QWidget):
        """メインウィンドウを設定"""
        self.main_window = main_window

    def show_success(self, message: str, details: str = "", 
                    priority: NotificationPriority = NotificationPriority.MEDIUM,
                    timeout: int = 3000) -> None:
        """
        成功通知を表示

        Args:
            message: 主要メッセージ
            details: 詳細情報（オプション）
            priority: 通知優先度
            timeout: 表示時間（ミリ秒）
        """
        self._show_notification(
            NotificationType.SUCCESS, message, details, priority, timeout
        )

    def show_warning(self, message: str, details: str = "",
                    priority: NotificationPriority = NotificationPriority.MEDIUM,
                    timeout: int = 5000) -> None:
        """
        警告通知を表示

        Args:
            message: 主要メッセージ
            details: 詳細情報（オプション）
            priority: 通知優先度
            timeout: 表示時間（ミリ秒）
        """
        self._show_notification(
            NotificationType.WARNING, message, details, priority, timeout
        )

    def show_error(self, message: str, details: str = "",
                  priority: NotificationPriority = NotificationPriority.HIGH,
                  timeout: int = 8000) -> None:
        """
        エラー通知を表示

        Args:
            message: 主要メッセージ
            details: 詳細情報（オプション）
            priority: 通知優先度
            timeout: 表示時間（ミリ秒）
        """
        self._show_notification(
            NotificationType.ERROR, message, details, priority, timeout
        )

    def show_info(self, message: str, details: str = "",
                 priority: NotificationPriority = NotificationPriority.LOW,
                 timeout: int = 4000) -> None:
        """
        情報通知を表示

        Args:
            message: 主要メッセージ
            details: 詳細情報（オプション）
            priority: 通知優先度
            timeout: 表示時間（ミリ秒）
        """
        self._show_notification(
            NotificationType.INFO, message, details, priority, timeout
        )

    def show_critical_error(self, message: str, details: str = "",
                           show_dialog: bool = True) -> None:
        """
        クリティカルエラー通知を表示

        Args:
            message: 主要メッセージ
            details: 詳細情報
            show_dialog: エラーダイアログを表示するか
        """
        self._show_notification(
            NotificationType.ERROR, message, details, 
            NotificationPriority.CRITICAL, 0  # 0は手動クリアまで表示
        )

        if show_dialog:
            self._show_error_dialog(message, details)

    def _show_notification(self, notification_type: NotificationType, 
                          message: str, details: str,
                          priority: NotificationPriority, timeout: int) -> None:
        """
        通知を表示する内部メソッド

        Args:
            notification_type: 通知の種類
            message: 主要メッセージ
            details: 詳細情報
            priority: 通知優先度
            timeout: 表示時間（ミリ秒、0は手動クリアまで）
        """
        try:
            # 通知履歴に追加
            self._add_to_history(notification_type, message, details)

            # 優先度に応じた表示
            if priority.value >= NotificationPriority.LOW.value:
                self._show_info_bar(notification_type, message, timeout)

            if priority.value >= NotificationPriority.MEDIUM.value:
                self._update_status_bar(notification_type, message, timeout)

            if priority.value >= NotificationPriority.HIGH.value:
                self._log_notification(notification_type, message, details)

            if priority.value >= NotificationPriority.CRITICAL.value:
                # クリティカルレベルは別途ダイアログ表示を検討
                pass

            # シグナル発行
            self.notification_sent.emit(notification_type.value, message, details)

        except Exception as e:
            # 通知システム自体でエラーが発生した場合のフォールバック
            self.logger.error(f"通知表示エラー: {e}")
            self._fallback_notification(message, details)

    def _show_info_bar(self, notification_type: NotificationType, 
                      message: str, timeout: int) -> None:
        """InfoBarを表示"""
        if not QFLUENTWIDGETS_AVAILABLE or not self.main_window:
            return

        try:
            # 通知タイプに応じたアイコンと位置
            icon_map = {
                NotificationType.SUCCESS: FIF.ACCEPT,
                NotificationType.WARNING: FIF.IMPORTANT,
                NotificationType.ERROR: FIF.CANCEL,
                NotificationType.INFO: FIF.INFO
            }

            icon = icon_map.get(notification_type, FIF.INFO)

            # InfoBarを作成して表示
            info_bar = InfoBar.new(
                icon=icon,
                title="",
                content=message,
                orient=InfoBarPosition.TOP,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=timeout if timeout > 0 else -1,
                parent=self.main_window
            )

            # タイプに応じたスタイル適用
            if notification_type == NotificationType.SUCCESS:
                info_bar.setCustomBackgroundColor("#f0f9f0", "#d4edda")
            elif notification_type == NotificationType.WARNING:
                info_bar.setCustomBackgroundColor("#fff3cd", "#ffeaa7")
            elif notification_type == NotificationType.ERROR:
                info_bar.setCustomBackgroundColor("#f8d7da", "#fab1a0")

            info_bar.show()

        except Exception as e:
            self.logger.warning(f"InfoBar表示エラー: {e}")

    def _update_status_bar(self, notification_type: NotificationType,
                          message: str, timeout: int) -> None:
        """ステータスバーを更新"""
        if not self.main_window or not hasattr(self.main_window, 'statusBar'):
            return

        try:
            status_bar = self.main_window.statusBar()
            
            # メッセージプレフィックス
            prefix_map = {
                NotificationType.SUCCESS: "✅",
                NotificationType.WARNING: "⚠️",
                NotificationType.ERROR: "❌",
                NotificationType.INFO: "ℹ️"
            }

            prefix = prefix_map.get(notification_type, "")
            status_message = f"{prefix} {message}"

            # ステータスバーに表示
            if hasattr(status_bar, 'showMessage'):
                status_bar.showMessage(status_message, timeout)
            else:
                # カスタムステータスバーの場合
                if hasattr(status_bar, 'status_label'):
                    status_bar.status_label.setText(status_message)
                    
                    # 自動クリア
                    if timeout > 0:
                        timer_id = f"status_{datetime.now().timestamp()}"
                        timer = QTimer()
                        timer.timeout.connect(lambda: self._clear_status_bar(timer_id))
                        timer.setSingleShot(True)
                        timer.start(timeout)
                        self.auto_clear_timers[timer_id] = timer

        except Exception as e:
            self.logger.warning(f"ステータスバー更新エラー: {e}")

    def _clear_status_bar(self, timer_id: str) -> None:
        """ステータスバーをクリア"""
        try:
            if self.main_window and hasattr(self.main_window, 'statusBar'):
                status_bar = self.main_window.statusBar()
                if hasattr(status_bar, 'clearMessage'):
                    status_bar.clearMessage()
                elif hasattr(status_bar, 'status_label'):
                    status_bar.status_label.setText("Ready")

            # タイマーをクリーンアップ
            if timer_id in self.auto_clear_timers:
                self.auto_clear_timers[timer_id].deleteLater()
                del self.auto_clear_timers[timer_id]

        except Exception as e:
            self.logger.warning(f"ステータスバークリアエラー: {e}")

    def _log_notification(self, notification_type: NotificationType,
                         message: str, details: str) -> None:
        """ログに記録"""
        try:
            log_message = f"{message}"
            if details:
                log_message += f" - {details}"

            if notification_type == NotificationType.SUCCESS:
                self.logger.info(log_message)
            elif notification_type == NotificationType.WARNING:
                self.logger.warning(log_message)
            elif notification_type == NotificationType.ERROR:
                self.logger.error(log_message)
            else:  # INFO
                self.logger.info(log_message)

        except Exception as e:
            print(f"ログ記録エラー: {e}")

    def _show_error_dialog(self, message: str, details: str) -> None:
        """エラーダイアログを表示"""
        try:
            if not self.main_window:
                return

            msg_box = QMessageBox(self.main_window)
            msg_box.setWindowTitle("エラー")
            msg_box.setIcon(QMessageBox.Critical)
            msg_box.setText(message)
            
            if details:
                msg_box.setDetailedText(details)
                msg_box.setInformativeText("詳細情報を確認するには「詳細を表示」をクリックしてください。")

            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.exec()

        except Exception as e:
            self.logger.error(f"エラーダイアログ表示エラー: {e}")

    def _add_to_history(self, notification_type: NotificationType,
                       message: str, details: str) -> None:
        """通知履歴に追加"""
        try:
            notification_record = {
                'timestamp': datetime.now(),
                'type': notification_type.value,
                'message': message,
                'details': details
            }

            self.notification_history.append(notification_record)

            # 履歴サイズ制限
            if len(self.notification_history) > self.max_history_size:
                self.notification_history.pop(0)

        except Exception as e:
            self.logger.warning(f"通知履歴追加エラー: {e}")

    def _fallback_notification(self, message: str, details: str) -> None:
        """フォールバック通知（基本的なログ出力）"""
        try:
            print(f"通知: {message}")
            if details:
                print(f"詳細: {details}")
            self.logger.error(f"通知表示失敗 - {message}: {details}")
        except Exception:
            pass  # 最後の手段として無視

    def get_notification_history(self) -> list:
        """通知履歴を取得"""
        return self.notification_history.copy()

    def clear_notification_history(self) -> None:
        """通知履歴をクリア"""
        self.notification_history.clear()

    def cleanup(self) -> None:
        """リソースクリーンアップ"""
        try:
            # アクティブなタイマーを停止
            for timer in self.auto_clear_timers.values():
                timer.stop()
                timer.deleteLater()
            self.auto_clear_timers.clear()

        except Exception as e:
            self.logger.warning(f"クリーンアップエラー: {e}")


# グローバルインスタンス（シングルトンパターン）
_notification_manager_instance: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """NotificationManagerのシングルトンインスタンスを取得"""
    global _notification_manager_instance

    if _notification_manager_instance is None:
        _notification_manager_instance = NotificationManager()

    return _notification_manager_instance


def initialize_notification_manager(main_window: QWidget) -> NotificationManager:
    """NotificationManagerを初期化"""
    global _notification_manager_instance

    if _notification_manager_instance is None:
        _notification_manager_instance = NotificationManager(main_window)
    else:
        _notification_manager_instance.set_main_window(main_window)

    return _notification_manager_instance


# 便利な関数（グローバルアクセス用）
def show_success(message: str, details: str = "", timeout: int = 3000) -> None:
    """成功通知を表示（グローバル関数）"""
    get_notification_manager().show_success(message, details, timeout=timeout)


def show_warning(message: str, details: str = "", timeout: int = 5000) -> None:
    """警告通知を表示（グローバル関数）"""
    get_notification_manager().show_warning(message, details, timeout=timeout)


def show_error(message: str, details: str = "", timeout: int = 8000) -> None:
    """エラー通知を表示（グローバル関数）"""
    get_notification_manager().show_error(message, details, timeout=timeout)


def show_info(message: str, details: str = "", timeout: int = 4000) -> None:
    """情報通知を表示（グローバル関数）"""
    get_notification_manager().show_info(message, details, timeout=timeout)


def show_critical_error(message: str, details: str = "") -> None:
    """クリティカルエラー通知を表示（グローバル関数）"""
    get_notification_manager().show_critical_error(message, details) 