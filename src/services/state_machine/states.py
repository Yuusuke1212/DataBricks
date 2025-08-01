"""
Concrete State Classes for JRA-Data Collector

アプリケーションの各ライフサイクル状態を実装する具象クラス群
"""

from typing import Any, Dict
from .base import AppState


class IdleState(AppState):
    """
    待機状態

    アプリケーション起動時の初期状態。
    ユーザーからの処理開始要求を待機している状態。
    """

    def __init__(self):
        super().__init__("Idle")

    def start_processing(self, params: Dict[str, Any] = None) -> None:
        """データ処理開始要求を処理"""
        self._logger.info("Starting data processing...")

        # データベース設定チェック
        if not self._check_database_config():
            self.context.emit_log("WARNING", "データベースが正しく設定されていないため、データ取得を開始できません。")
            self.context.show_error_message_box(
                "データベース未接続",
                "データベースが正しく設定されていません。アプリ設定から接続をテストし、設定を保存してください。"
            )
            return

        # リクエスト状態に遷移
        self.context.transition_to(RequestingDataState(params))

    def _can_start_processing(self) -> bool:
        return True

    def _can_cancel_processing(self) -> bool:
        return False

    def _get_status_message(self) -> str:
        return "準備完了 - 処理を開始できます"

    def _check_database_config(self) -> bool:
        """データベース設定の妥当性をチェック"""
        try:
            # AppControllerの既存チェック機能を使用
            if hasattr(self.context, '_check_database_config'):
                return self.context._check_database_config()
            else:
                self._logger.warning("Database config check method not found")
                return True
        except Exception as e:
            self._logger.error(f"Database config check failed: {e}")
            return False


class RequestingDataState(AppState):
    """
    データリクエスト状態

    JV-Linkサーバーにデータ取得要求を送信している状態。
    JVOpenの呼び出しとその応答待ちを行う。
    """

    def __init__(self, params: Dict[str, Any] = None):
        super().__init__("RequestingData")
        self.params = params or {}

    def on_enter(self) -> None:
        super().on_enter()
        self._start_data_request()

    def cancel_processing(self) -> None:
        """処理のキャンセル要求を処理"""
        self._logger.info("Cancelling data request...")
        self.context.transition_to(CancellingState())

    def _start_data_request(self) -> None:
        """データ取得要求を開始"""
        try:
            # AppControllerの既存機能を使用してデータ取得を開始
            if hasattr(self.context, 'jvlink_manager'):
                # データ取得パラメータの準備
                data_spec_list = self.params.get('data_spec_list', ['RACE'])
                from_date = self.params.get('from_date', '')
                option = self.params.get('option', 1)  # デフォルトは差分取得

                # JvLinkManagerに処理を委譲
                self.context.jvlink_manager.get_data_async(
                    option=option,
                    from_date=from_date,
                    data_spec_list=data_spec_list
                )

                # ポーリング状態に遷移
                self.context.transition_to(PollingDownloadState())

            else:
                raise RuntimeError("JvLinkManager not available")

        except Exception as e:
            self.handle_error(
                e, {"operation": "data_request", "params": self.params})

    def _can_start_processing(self) -> bool:
        return False

    def _can_cancel_processing(self) -> bool:
        return True

    def _get_status_message(self) -> str:
        return "データ取得要求を送信中..."


class PollingDownloadState(AppState):
    """
    ダウンロードポーリング状態

    JV-Linkからのデータ取得が進行中の状態。
    進捗監視とデータ受信を行う。
    """

    def __init__(self):
        super().__init__("PollingDownload")

    def on_enter(self) -> None:
        super().on_enter()
        self._setup_progress_monitoring()

    def cancel_processing(self) -> None:
        """処理のキャンセル要求を処理"""
        self._logger.info("Cancelling download...")
        self.context.transition_to(CancellingState())

    def handle_progress_update(self, progress: Dict[str, Any]) -> None:
        """進捗更新を処理"""
        progress_percent = progress.get('percent', 0)
        message = progress.get('message', 'ダウンロード中...')

        # UIに進捗を反映
        try:
            if hasattr(self.context.main_window, 'dashboard_view'):
                dashboard = self.context.main_window.dashboard_view
                if hasattr(dashboard, 'update_progress'):
                    dashboard.update_progress(progress_percent, message)
        except Exception as e:
            self._logger.warning(f"Failed to update progress UI: {e}")

    def _setup_progress_monitoring(self) -> None:
        """進捗監視を設定"""
        try:
            # 既存のJvLinkManagerのシグナルに接続
            if hasattr(self.context, 'jvlink_manager'):
                manager = self.context.jvlink_manager

                # シグナル接続（重複接続は自動的に防がれる）
                if hasattr(manager, 'data_received'):
                    manager.data_received.connect(self._on_data_received)

                if hasattr(manager, 'operation_finished'):
                    manager.operation_finished.connect(
                        self._on_operation_finished)

        except Exception as e:
            self._logger.error(f"Failed to setup progress monitoring: {e}")

    def _on_data_received(self, data) -> None:
        """データ受信時の処理"""
        self._logger.info("Data received, transitioning to reading state...")
        self.context.transition_to(ReadingDataState(data))

    def _on_operation_finished(self, message: str) -> None:
        """操作完了時の処理"""
        self._logger.info(f"Operation finished: {message}")
        self.context.transition_to(FinalizingState(message))

    def _can_start_processing(self) -> bool:
        return False

    def _can_cancel_processing(self) -> bool:
        return True

    def _get_status_message(self) -> str:
        return "データをダウンロード中..."


class ReadingDataState(AppState):
    """
    データ読み込み状態

    受信したデータのETL処理とDB格納を行っている状態。
    """

    def __init__(self, received_data: Any = None):
        super().__init__("ReadingData")
        self.received_data = received_data

    def on_enter(self) -> None:
        super().on_enter()
        self._start_data_processing()

    def cancel_processing(self) -> None:
        """処理のキャンセル要求を処理"""
        self._logger.info("Cancelling data processing...")
        self.context.transition_to(CancellingState())

    def _start_data_processing(self) -> None:
        """データ処理を開始"""
        try:
            # AppControllerの既存ETLパイプラインを使用
            if hasattr(self.context, 'on_data_received'):
                self.context.on_data_received(self.received_data)

                # パイプライン完了待ち
                self._setup_pipeline_monitoring()

            else:
                raise RuntimeError("Data processing pipeline not available")

        except Exception as e:
            self.handle_error(e, {"operation": "data_processing", "data_size": len(
                self.received_data) if self.received_data else 0})

    def _setup_pipeline_monitoring(self) -> None:
        """ETLパイプライン監視を設定"""
        try:
            if hasattr(self.context, 'etl_pipeline'):
                pipeline = self.context.etl_pipeline

                # パイプライン完了シグナルに接続
                if hasattr(pipeline, 'pipeline_finished'):
                    pipeline.pipeline_finished.connect(
                        self._on_pipeline_finished)

                # パイプラインエラーシグナルに接続
                if hasattr(pipeline, 'pipeline_error'):
                    pipeline.pipeline_error.connect(self._on_pipeline_error)

        except Exception as e:
            self._logger.error(f"Failed to setup pipeline monitoring: {e}")

    def _on_pipeline_finished(self) -> None:
        """パイプライン完了時の処理"""
        self._logger.info(
            "ETL pipeline finished, transitioning to finalizing state...")
        self.context.transition_to(FinalizingState("ETL処理完了"))

    def _on_pipeline_error(self, error_message: str) -> None:
        """パイプラインエラー時の処理"""
        error = RuntimeError(f"ETL Pipeline Error: {error_message}")
        self.handle_error(error, {"operation": "etl_pipeline"})

    def _can_start_processing(self) -> bool:
        return False

    def _can_cancel_processing(self) -> bool:
        return True

    def _get_status_message(self) -> str:
        return "データを処理中..."


class CancellingState(AppState):
    """
    キャンセル処理状態

    ユーザーからのキャンセル要求を処理し、
    実行中の処理を安全に停止している状態。
    """

    def __init__(self):
        super().__init__("Cancelling")

    def on_enter(self) -> None:
        super().on_enter()
        self._start_cancellation()

    def _start_cancellation(self) -> None:
        """キャンセル処理を開始"""
        try:
            # AppControllerの既存キャンセル機能を使用
            if hasattr(self.context, 'cancel_current_operation'):
                self.context.cancel_current_operation()

            # JvLinkManagerのキャンセル
            if hasattr(self.context, 'jvlink_manager'):
                manager = self.context.jvlink_manager
                if hasattr(manager, 'cancel_current_operation'):
                    manager.cancel_current_operation()

            # ETLパイプラインのキャンセル
            if hasattr(self.context, 'etl_pipeline'):
                pipeline = self.context.etl_pipeline
                if hasattr(pipeline, 'cancel_pipeline'):
                    pipeline.cancel_pipeline()

            self._logger.info(
                "Cancellation completed, returning to idle state...")
            self.context.transition_to(IdleState())

        except Exception as e:
            self._logger.error(f"Cancellation failed: {e}")
            # キャンセル失敗の場合はエラー状態に遷移
            self.handle_error(e, {"operation": "cancellation"})

    def _can_start_processing(self) -> bool:
        return False

    def _can_cancel_processing(self) -> bool:
        return False

    def _get_status_message(self) -> str:
        return "処理をキャンセル中..."


class FinalizingState(AppState):
    """
    処理完了状態

    データ処理が正常に完了し、
    最終的なクリーンアップ処理を行っている状態。
    """

    def __init__(self, completion_message: str = "処理完了"):
        super().__init__("Finalizing")
        self.completion_message = completion_message

    def on_enter(self) -> None:
        super().on_enter()
        self._finalize_processing()

    def _finalize_processing(self) -> None:
        """処理の最終化"""
        try:
            # 最終同期日時の更新
            if hasattr(self.context, 'current_data_specs') and self.context.current_data_specs:
                if hasattr(self.context, 'settings_manager'):
                    # 仮実装：最初のデータ種別の同期時刻を更新
                    data_spec = self.context.current_data_specs[0]
                    self.context.settings_manager.save_last_timestamp(
                        data_spec, self.completion_message)

            # データサマリーの更新
            if hasattr(self.context.main_window, 'dashboard_view'):
                dashboard = self.context.main_window.dashboard_view
                if hasattr(self.context, 'db_manager'):
                    summary = self.context.db_manager.get_data_summary()
                    dashboard.update_dashboard_summary(summary)

            # 完了メッセージを表示
            if hasattr(self.context.main_window, 'statusBar'):
                status_bar = self.context.main_window.statusBar()
                status_bar.showMessage(f"完了: {self.completion_message}", 5000)

            self._logger.info(
                f"Processing finalized: {self.completion_message}")

            # アイドル状態に戻る
            self.context.transition_to(IdleState())

        except Exception as e:
            self._logger.error(f"Finalization failed: {e}")
            self.handle_error(
                e, {"operation": "finalization", "message": self.completion_message})

    def _can_start_processing(self) -> bool:
        return False

    def _can_cancel_processing(self) -> bool:
        return False

    def _get_status_message(self) -> str:
        return f"処理を完了中... ({self.completion_message})"


class ErrorState(AppState):
    """
    エラー状態

    処理中にエラーが発生した場合の状態。
    エラー情報の表示とユーザーへの通知を行う。
    """

    def __init__(self, error: Exception = None, context_info: Dict[str, Any] = None):
        super().__init__("Error")
        self.error = error
        self.context_info = context_info or {}

    def on_enter(self) -> None:
        super().on_enter()
        self._handle_error_state()

    def start_processing(self, params: Dict[str, Any] = None) -> None:
        """エラー状態からの処理開始（エラー回復）"""
        self._logger.info("Attempting to recover from error state...")
        self.context.transition_to(IdleState())

    def _handle_error_state(self) -> None:
        """エラー状態の処理"""
        try:
            # エラーメッセージの構築
            error_message = str(self.error) if self.error else "不明なエラーが発生しました"

            # UIにエラーダイアログを表示
            self._show_error_dialog(error_message)

            # ステータスバーにエラーメッセージを表示
            if hasattr(self.context.main_window, 'statusBar'):
                status_bar = self.context.main_window.statusBar()
                status_bar.showMessage(f"エラー: {error_message}", 10000)

            # 進捗表示をリセット
            if hasattr(self.context.main_window, 'dashboard_view'):
                dashboard = self.context.main_window.dashboard_view
                if hasattr(dashboard, 'update_progress'):
                    dashboard.update_progress(0, "エラー発生")

            self._logger.error(f"Error state entered: {error_message}")
            if self.context_info:
                self._logger.error(f"Context: {self.context_info}")

        except Exception as e:
            self._logger.critical(f"Failed to handle error state: {e}")

    def _show_error_dialog(self, error_message: str) -> None:
        """エラーダイアログを表示"""
        try:
            from PyQt5.QtWidgets import QMessageBox

            if hasattr(self.context, 'main_window') and self.context.main_window:
                # コンテキスト情報がある場合は詳細を表示
                detailed_message = error_message
                if self.context_info:
                    details = "\n".join(
                        [f"{k}: {v}" for k, v in self.context_info.items()])
                    detailed_message += f"\n\n詳細:\n{details}"

                QMessageBox.critical(
                    self.context.main_window,
                    "エラーが発生しました",
                    detailed_message
                )
        except Exception as e:
            self._logger.error(f"Failed to show error dialog: {e}")

    def _can_start_processing(self) -> bool:
        return True  # エラー状態からの回復を許可

    def _can_cancel_processing(self) -> bool:
        return False

    def _get_status_message(self) -> str:
        error_msg = str(self.error) if self.error else "不明なエラー"
        return f"エラー: {error_msg}"
