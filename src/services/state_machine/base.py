"""
State Machine Base Classes for JRA-Data Collector

ステートマシンパターンの基盤となる抽象基底クラスを定義します。
Phase 3: Worker Pipeline統合対応
"""

from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING, Any, Dict, Optional
import logging

if TYPE_CHECKING:
    from ...controllers.app_controller import AppController
    from ..workers.pipeline_coordinator import PipelineCoordinator
    from ..workers.base import ProgressInfo


class AppState(ABC):
    """
    アプリケーション状態の抽象基底クラス

    すべての具象状態クラスはこのクラスを継承し、
    適切な状態遷移と動作を実装する必要があります。

    Phase 3では Worker Pipeline との統合サポートを追加。
    """

    def __init__(self, name: str = None):
        self._context: Optional[AppController] = None
        self._name = name or self.__class__.__name__
        self._logger = logging.getLogger(f"Statemachine.{self._name}")

    @property
    def context(self) -> AppController:
        """コンテキスト（AppController）への参照を取得"""
        if self._context is None:
            raise RuntimeError(f"State {self._name} has no context set")
        return self._context

    @context.setter
    def context(self, context: AppController) -> None:
        """コンテキスト（AppController）を設定"""
        self._context = context

    @property
    def name(self) -> str:
        """状態名を取得"""
        return self._name

    @property
    def pipeline_coordinator(self) -> Optional[PipelineCoordinator]:
        """PipelineCoordinatorへの参照を取得"""
        try:
            if hasattr(self.context, 'pipeline_coordinator'):
                return self.context.pipeline_coordinator
        except Exception as e:
            self._logger.debug(f"PipelineCoordinator not available: {e}")
        return None

    def on_enter(self) -> None:
        """
        状態に入る際に実行される処理

        この状態にトランジションした時に自動的に呼び出されます。
        UIの更新、リソースの初期化などを行います。
        """
        self._logger.info(f"Entering state: {self._name}")
        try:
            self._update_ui_status()
        except Exception as e:
            self._logger.warning(f"Failed to update UI status: {e}")

    def on_exit(self) -> None:
        """
        状態から出る際に実行される処理

        他の状態にトランジションする前に自動的に呼び出されます。
        リソースのクリーンアップ、状態保存などを行います。
        """
        self._logger.info(f"Exiting state: {self._name}")

    def _update_ui_status(self) -> None:
        """
        UI状態更新のデフォルト実装

        各状態クラスで必要に応じてオーバーライドしてください。
        """
        try:
            if hasattr(self.context, 'main_window') and hasattr(self.context.main_window, 'update_status'):
                status_message = self._get_status_message()
                self.context.main_window.update_status(status_message)
            else:
                self._logger.debug(
                    f"UI status update not available for state: {self._name}")
        except Exception as e:
            self._logger.warning(f"UI status update failed: {e}")

    def start_processing(self, params: Dict[str, Any] = None) -> None:
        """
        処理開始要求を処理

        ユーザーからの処理開始要求やUI操作に応答します。

        Args:
            params: 処理パラメータの辞書

        Raises:
            StateTransitionError: 現在の状態で処理開始が許可されていない場合
        """
        if not self._can_start_processing():
            raise StateTransitionError(
                f"Cannot start processing in state: {self._name}"
            )

        self._logger.info(f"Processing start requested in state: {self._name}")

    def cancel_processing(self) -> None:
        """
        処理キャンセル要求を処理

        ユーザーからのキャンセル要求やエラー発生時の緊急停止に応答します。

        Raises:
            StateTransitionError: 現在の状態でキャンセルが許可されていない場合
        """
        if not self._can_cancel_processing():
            raise StateTransitionError(
                f"Cannot cancel processing in state: {self._name}"
            )

        self._logger.info(
            f"Processing cancellation requested in state: {self._name}")

    def handle_progress_update(self, progress: ProgressInfo) -> None:
        """
        Worker Pipeline からの進捗更新を処理

        Args:
            progress: Worker からの進捗情報
        """
        self._logger.debug(
            f"Progress update: {progress.worker_name} - {progress.percentage:.1f}%")

        try:
            # UIへの進捗反映
            self._update_progress_ui(progress)
        except Exception as e:
            self._logger.warning(f"Failed to update progress UI: {e}")

    def handle_pipeline_error(self, worker_name: str, error: Exception) -> None:
        """
        Worker Pipeline からのエラーを処理

        Args:
            worker_name: エラーが発生したワーカー名
            error: 発生したエラー
        """
        self._logger.error(f"Pipeline error from {worker_name}: {error}")

        # 重大なエラーの場合は自動的にエラー状態に遷移
        if self._is_critical_pipeline_error(error):
            self.handle_error(
                error, {"worker": worker_name, "context": "pipeline"})

    def handle_pipeline_completion(self) -> None:
        """
        Worker Pipeline 完了を処理

        パイプライン全体が正常完了した際に呼び出されます。
        デフォルトでは次の状態への遷移ロジックを実行します。
        """
        self._logger.info(f"Pipeline completed in state: {self._name}")

        # サブクラスでオーバーライドして適切な次状態への遷移を実装
        self._on_pipeline_completion()

    def start_pipeline(self, data_params: Dict[str, Any], etl_rules: Dict[str, Any]) -> bool:
        """
        Worker Pipeline を開始

        Args:
            data_params: データ取得パラメータ
            etl_rules: ETL処理ルール

        Returns:
            bool: 開始に成功した場合 True
        """
        coordinator = self.pipeline_coordinator
        if not coordinator:
            self._logger.error("PipelineCoordinator not available")
            return False

        try:
            return coordinator.start_pipeline(data_params, etl_rules)
        except Exception as e:
            self._logger.error(f"Failed to start pipeline: {e}")
            self.handle_error(e, {"operation": "start_pipeline"})
            return False

    def stop_pipeline(self, timeout: float = 30.0) -> bool:
        """
        Worker Pipeline を停止

        Args:
            timeout: 停止待機時間（秒）

        Returns:
            bool: 正常に停止した場合 True
        """
        coordinator = self.pipeline_coordinator
        if not coordinator:
            self._logger.warning("PipelineCoordinator not available for stop")
            return True  # 既に停止済みとみなす

        try:
            return coordinator.stop_pipeline(timeout)
        except Exception as e:
            self._logger.error(f"Failed to stop pipeline: {e}")
            return False

    def get_pipeline_stats(self) -> Optional[Dict[str, Any]]:
        """
        Worker Pipeline の統計情報を取得

        Returns:
            Optional[Dict]: パイプライン統計情報
        """
        coordinator = self.pipeline_coordinator
        if not coordinator:
            return None

        try:
            return coordinator.get_pipeline_stats()
        except Exception as e:
            self._logger.error(f"Failed to get pipeline stats: {e}")
            return None

    def handle_error(self, error: Exception, context_info: Dict[str, Any] = None) -> None:
        """
        エラーハンドリング - 即座にパイプラインを停止しエラー状態に遷移

        Args:
            error: 発生したエラー
            context_info: エラーコンテキスト情報
        """
        self._logger.error(f"Critical error in state {self._name}: {error}")
        if context_info:
            self._logger.error(f"Error context: {context_info}")

        # パイプラインを即座に停止
        try:
            if hasattr(self, 'context') and hasattr(self.context, 'jvlink_manager'):
                jvlink_manager = self.context.jvlink_manager

                # 進行中の操作をキャンセル
                if hasattr(jvlink_manager, 'cancel_current_operation'):
                    jvlink_manager.cancel_current_operation()

                # リアルタイム監視を停止
                if hasattr(jvlink_manager, 'stop_watching_events'):
                    jvlink_manager.stop_watching_events()

            # Worker Pipelineを停止
            self.stop_pipeline(timeout=5.0)

        except Exception as pipeline_error:
            self._logger.critical(
                f"Failed to stop pipeline during error handling: {pipeline_error}")

        # エラー状態に遷移（他の状態への自動遷移を防止）
        try:
            from .error_state import ErrorState
            error_state = ErrorState(
                error_title="システムエラー",
                error_message=str(error),
                exception=error,
                error_context=context_info
            )

            if hasattr(self, 'context'):
                self.context.transition_to(error_state)
            else:
                self._logger.critical(
                    "No context available for error state transition")

        except Exception as transition_error:
            self._logger.critical(
                f"Failed to transition to error state: {transition_error}")
            # 最後の手段: アプリケーションを安全停止状態にする
            self._emergency_shutdown()

    def _emergency_shutdown(self):
        """
        緊急停止処理 - 致命的エラー時の最後の手段
        """
        try:
            self._logger.critical("Emergency shutdown initiated")

            # 全てのワーカーを強制停止
            if hasattr(self, 'context'):
                context = self.context

                # JV-Linkリソースを強制解放
                if hasattr(context, 'jvlink_manager'):
                    try:
                        context.jvlink_manager.close()
                    except:
                        pass

                # データベース接続を閉じる
                if hasattr(context, 'db_manager'):
                    try:
                        context.db_manager.close()
                    except:
                        pass

                # UIに緊急停止を通知
                if hasattr(context, 'main_window'):
                    try:
                        import logging
                        logging.critical("システムエラーが発生しました。アプリケーションを再起動してください。")
                        if hasattr(context.main_window, 'statusBar'):
                            context.main_window.statusBar().showMessage(
                                "致命的エラー: アプリケーションを再起動してください。", 0
                            )
                    except:
                        pass

        except Exception as shutdown_error:
            # 最終的なログ記録
            import logging
            logging.critical(f"Emergency shutdown failed: {shutdown_error}")

    def _update_ui_state(self) -> None:
        """
        現在の状態に基づいてUIを更新する

        各状態で適切なUIの有効/無効状態を設定します。
        """
        try:
            if hasattr(self.context, 'main_window') and self.context.main_window:
                self._update_dashboard_buttons()
                self._update_status_message()
        except Exception as e:
            self._logger.warning(f"Failed to update UI state: {e}")

    def _update_dashboard_buttons(self) -> None:
        """ダッシュボードボタンの状態を更新"""
        dashboard = getattr(self.context.main_window, 'dashboard_view', None)
        if not dashboard:
            return

        # デフォルト状態（各状態でオーバーライド）
        can_start = self._can_start_processing()
        can_cancel = self._can_cancel_processing()

        if hasattr(dashboard, 'diff_button'):
            dashboard.diff_button.setEnabled(can_start)
        if hasattr(dashboard, 'full_button'):
            dashboard.full_button.setEnabled(can_start)
        if hasattr(dashboard, 'stop_button'):
            dashboard.stop_button.setEnabled(can_cancel)

    def _update_status_message(self) -> None:
        """ステータスメッセージを更新"""
        if hasattr(self.context.main_window, 'statusBar'):
            status_bar = self.context.main_window.statusBar()
            message = self._get_status_message()
            status_bar.showMessage(message)

    def _can_start_processing(self) -> bool:
        """処理開始が可能かどうかを判定（各状態でオーバーライド）"""
        return False

    def _can_cancel_processing(self) -> bool:
        """処理キャンセルが可能かどうかを判定（各状態でオーバーライド）"""
        return False

    def _get_status_message(self) -> str:
        """
        状態に応じたステータスメッセージを取得

        各状態クラスでオーバーライドして適切なメッセージを返してください。
        """
        return f"状態: {self._name}"

    def _raise_invalid_transition(self, operation: str) -> None:
        """
        無効な状態遷移の警告を出力

        Args:
            operation: 実行しようとした操作名
        """
        message = f"Invalid operation '{operation}' in state '{self._name}'"
        self._logger.warning(message)

        # UIに警告メッセージを表示
        try:
            from PyQt5.QtWidgets import QMessageBox
            if hasattr(self.context, 'main_window') and self.context.main_window:
                QMessageBox.warning(
                    self.context.main_window,
                    "操作エラー",
                    f"現在の状態（{self._name}）では'{operation}'操作は実行できません。"
                )
        except Exception as e:
            self._logger.error(f"Failed to show warning dialog: {e}")


class StateTransitionError(Exception):
    """状態遷移エラー"""

    def __init__(self, from_state: str, to_state: str, reason: str = None):
        self.from_state = from_state
        self.to_state = to_state
        self.reason = reason

        message = f"Invalid transition from {from_state} to {to_state}"
        if reason:
            message += f": {reason}"

        super().__init__(message)

    def _is_critical_pipeline_error(self, error: Exception) -> bool:
        """
        パイプラインエラーが重大かどうかを判定

        Args:
            error: 発生したエラー

        Returns:
            bool: 重大なエラーの場合 True
        """
        critical_error_types = [
            "ConnectionError",
            "AuthenticationError",
            "DatabaseError",
            "PermissionError",
            "OutOfMemoryError"
        ]

        return type(error).__name__ in critical_error_types

    def _on_pipeline_completion(self) -> None:
        """
        パイプライン完了時の処理（サブクラスでオーバーライド）

        デフォルト実装では何もしません。
        具象状態クラスで適切な次状態への遷移を実装してください。
        """
        pass

    def _update_progress_ui(self, progress: ProgressInfo) -> None:
        """
        UIに進捗情報を反映

        Args:
            progress: 進捗情報
        """
        try:
            if hasattr(self.context, 'main_window') and self.context.main_window:
                main_window = self.context.main_window

                # Dashboard View の進捗更新
                if hasattr(main_window, 'dashboard_view'):
                    dashboard = main_window.dashboard_view
                    if hasattr(dashboard, 'update_progress'):
                        dashboard.update_progress(
                            progress.percentage, progress.message)

                # ステータスバーの更新
                if hasattr(main_window, 'update_status'):
                    main_window.update_status(
                        f"{progress.worker_name}: {progress.message}")

        except Exception as e:
            self._logger.debug(f"UI update failed: {e}")

    def _update_ui_status(self) -> None:
        """
        状態変更時にUIのステータスを更新

        デフォルト実装では基本的なステータス更新を行います。
        具象クラスでオーバーライドして、状態固有のUI更新を実装できます。
        """
        try:
            status_message = self._get_status_message()

            if hasattr(self.context, 'main_window') and self.context.main_window:
                main_window = self.context.main_window

                # ステータスバーの更新
                if hasattr(main_window, 'statusBar'):
                    status_bar = main_window.statusBar()
                    if status_bar:
                        status_bar.showMessage(
                            f"{self._name}: {status_message}")

                # Dashboard View の状態更新
                if hasattr(main_window, 'dashboard_view'):
                    dashboard = main_window.dashboard_view
                    if hasattr(dashboard, 'update_status'):
                        dashboard.update_status(self._name, status_message)

        except Exception as e:
            self._logger.debug(f"UI status update failed: {e}")

    def _get_status_message(self) -> str:
        """
        現在の状態に応じたステータスメッセージを取得

        Returns:
            str: 状態メッセージ（サブクラスでオーバーライド推奨）
        """
        return f"{self._name}状態"
