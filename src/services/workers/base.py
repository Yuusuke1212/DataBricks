"""
Base Worker Classes for JRA-Data Collector

並列データ処理パイプラインの基盤となるワーカークラス群を定義します。
Thread-Safeな設計とCooperative Cancellationをサポートします。
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, Optional, Callable, TYPE_CHECKING
import threading
import time
import logging
import queue
from dataclasses import dataclass

if TYPE_CHECKING:
    from queue import Queue


class WorkerState(Enum):
    """ワーカーの実行状態"""
    IDLE = "idle"                    # 待機中
    STARTING = "starting"            # 開始中
    RUNNING = "running"              # 実行中
    STOPPING = "stopping"           # 停止中
    STOPPED = "stopped"              # 停止済み
    ERROR = "error"                  # エラー状態
    COMPLETED = "completed"          # 完了


@dataclass
class ProgressInfo:
    """進捗情報"""
    worker_name: str
    current_item: int
    total_items: int
    message: str
    percentage: float = 0.0

    def __post_init__(self):
        if self.total_items > 0:
            self.percentage = min(
                100.0, (self.current_item / self.total_items) * 100.0)


class CancellationToken:
    """
    協調的キャンセレーション用トークン

    複数のワーカー間でキャンセル状態を共有し、
    安全な処理停止を実現します。
    """

    def __init__(self):
        self._is_cancelled = threading.Event()
        self._reason: Optional[str] = None
        self._lock = threading.Lock()

    def cancel(self, reason: str = "User requested cancellation") -> None:
        """キャンセルを要求"""
        with self._lock:
            self._reason = reason
            self._is_cancelled.set()
            logging.info(f"Cancellation requested: {reason}")

    @property
    def is_cancelled(self) -> bool:
        """キャンセルが要求されているかを確認"""
        return self._is_cancelled.is_set()

    @property
    def reason(self) -> Optional[str]:
        """キャンセル理由を取得"""
        with self._lock:
            return self._reason

    def throw_if_cancelled(self) -> None:
        """キャンセルされている場合は例外を発生"""
        if self.is_cancelled:
            raise CancellationRequestedException(
                self.reason or "Operation was cancelled")

    def wait_for_cancellation(self, timeout: Optional[float] = None) -> bool:
        """キャンセルが要求されるまで待機"""
        return self._is_cancelled.wait(timeout)


class CancellationRequestedException(Exception):
    """キャンセル要求例外"""
    pass


class BaseWorker(ABC, threading.Thread):
    """
    すべてのワーカーの基底クラス

    Thread-Safeな並列処理とCooperative Cancellationを提供します。
    各ワーカーは独立したスレッドで実行され、キューを通じてデータを交換します。
    """

    def __init__(self,
                 name: str,
                 cancellation_token: CancellationToken,
                 progress_callback: Optional[Callable[[
                     ProgressInfo], None]] = None,
                 error_callback: Optional[Callable[[str, Exception], None]] = None):
        super().__init__(name=name, daemon=True)

        self.worker_name = name
        self._state = WorkerState.IDLE
        self._state_lock = threading.Lock()

        # キャンセレーション
        self.cancellation_token = cancellation_token

        # コールバック
        self.progress_callback = progress_callback
        self.error_callback = error_callback

        # 統計情報
        self.items_processed = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None

        # ログ
        self.logger = logging.getLogger(f"Worker.{name}")

        # 内部状態
        self._exception: Optional[Exception] = None

    @property
    def state(self) -> WorkerState:
        """現在の状態を取得"""
        with self._state_lock:
            return self._state

    def _set_state(self, new_state: WorkerState) -> None:
        """状態を安全に更新"""
        with self._state_lock:
            if self._state != new_state:
                old_state = self._state
                self._state = new_state

                # ★修正★: 型安全なstate.valueアクセス
                try:
                    old_state_str = old_state.value if hasattr(old_state, 'value') else str(old_state)
                    new_state_str = new_state.value if hasattr(new_state, 'value') else str(new_state)
                except (AttributeError, TypeError):
                    old_state_str = str(old_state)
                    new_state_str = str(new_state)

                self.logger.info(f"State transition: {old_state_str} -> {new_state_str}")

    @property
    def is_running(self) -> bool:
        """ワーカーが実行中かどうかを確認"""
        return self.state in [WorkerState.STARTING, WorkerState.RUNNING]

    @property
    def processing_time(self) -> Optional[float]:
        """処理時間を取得（秒）"""
        if self.start_time is None:
            return None
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def throughput(self) -> Optional[float]:
        """スループットを取得（items/second）"""
        processing_time = self.processing_time
        if processing_time is None or processing_time <= 0:
            return None
        return self.items_processed / processing_time

    def run(self) -> None:
        """メインワーカー実行ループ"""
        try:
            self._set_state(WorkerState.STARTING)
            self.start_time = time.time()

            self.logger.info(f"Worker '{self.worker_name}' starting...")

            # 初期化処理
            self.on_start()

            # メイン処理ループ
            self._set_state(WorkerState.RUNNING)
            self.process_loop()

            # 正常完了
            self._set_state(WorkerState.COMPLETED)
            self.logger.info(
                f"Worker '{self.worker_name}' completed successfully")

        except CancellationRequestedException:
            self._set_state(WorkerState.STOPPED)
            self.logger.info(f"Worker '{self.worker_name}' was cancelled")

        except Exception as e:
            self._exception = e
            self._set_state(WorkerState.ERROR)
            self.logger.error(f"Worker '{self.worker_name}' failed: {e}")

            if self.error_callback:
                try:
                    self.error_callback(self.worker_name, e)
                except Exception as callback_error:
                    self.logger.error(
                        f"Error callback failed: {callback_error}")

        finally:
            self.end_time = time.time()
            try:
                self.on_cleanup()
            except Exception as cleanup_error:
                self.logger.error(f"Cleanup failed: {cleanup_error}")

    @abstractmethod
    def process_loop(self) -> None:
        """
        メイン処理ループ（サブクラスで実装）

        定期的にcancellation_token.throw_if_cancelled()を呼び出して
        キャンセル要求に応答してください。
        """
        pass

    def on_start(self) -> None:
        """ワーカー開始時の初期化処理（オーバーライド可能）"""
        pass

    def on_cleanup(self) -> None:
        """ワーカー終了時のクリーンアップ処理（オーバーライド可能）"""
        pass

    def stop(self, timeout: float = 5.0) -> bool:
        """
        ワーカーを停止

        Args:
            timeout: 停止待機時間（秒）

        Returns:
            bool: 正常に停止したかどうか
        """
        if not self.is_alive():
            return True

        self.logger.info(f"Stopping worker '{self.worker_name}'...")
        self._set_state(WorkerState.STOPPING)

        # キャンセル要求
        if not self.cancellation_token.is_cancelled:
            self.cancellation_token.cancel(
                f"Stop requested for worker {self.worker_name}")

        # 停止を待機
        self.join(timeout)

        if self.is_alive():
            self.logger.warning(
                f"Worker '{self.worker_name}' did not stop within {timeout} seconds")
            return False
        else:
            self.logger.info(
                f"Worker '{self.worker_name}' stopped successfully")
            return True

    def report_progress(self, current: int, total: int, message: str = "") -> None:
        """進捗を報告"""
        if self.progress_callback:
            progress = ProgressInfo(
                worker_name=self.worker_name,
                current_item=current,
                total_items=total,
                message=message
            )
            try:
                self.progress_callback(progress)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")

    def safe_sleep(self, duration: float, check_interval: float = 0.1) -> None:
        """
        キャンセル要求を監視しながら安全にスリープ

        Args:
            duration: スリープ時間（秒）
            check_interval: キャンセルチェック間隔（秒）
        """
        end_time = time.time() + duration
        while time.time() < end_time:
            self.cancellation_token.throw_if_cancelled()
            remaining = end_time - time.time()
            sleep_time = min(check_interval, remaining)
            if sleep_time > 0:
                time.sleep(sleep_time)

    def get_stats(self) -> Dict[str, Any]:
        """ワーカー統計情報を取得"""
        # ★修正★: 型安全なstate.valueアクセス
        try:
            state_str = self.state.value if hasattr(self.state, 'value') else str(self.state)
        except (AttributeError, TypeError):
            state_str = str(self.state)

        return {
            "name": self.worker_name,
            "state": state_str,
            "items_processed": self.items_processed,
            "processing_time": self.processing_time,
            "throughput": self.throughput,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_alive": self.is_alive(),
            "exception": str(self._exception) if self._exception else None
        }


class QueueWorker(BaseWorker):
    """
    キューベースワーカーの基底クラス

    入力キューからデータを取得し、処理後に出力キューに送信する
    Producer-Consumerパターンの実装基盤を提供します。
    """

    def __init__(self,
                 name: str,
                 input_queue: Optional[Queue] = None,
                 output_queue: Optional[Queue] = None,
                 cancellation_token: CancellationToken = None,
                 progress_callback: Optional[Callable[[
                     ProgressInfo], None]] = None,
                 error_callback: Optional[Callable[[
                     str, Exception], None]] = None,
                 queue_timeout: float = 1.0):

        super().__init__(name, cancellation_token, progress_callback, error_callback)

        self.input_queue = input_queue
        self.output_queue = output_queue
        self.queue_timeout = queue_timeout

    def process_loop(self) -> None:
        """キューベースの処理ループ"""
        while not self.cancellation_token.is_cancelled:
            try:
                # 入力キューからデータを取得
                if self.input_queue:
                    try:
                        item = self.input_queue.get(timeout=self.queue_timeout)
                        if item is None:  # 終了マーカー
                            break
                    except queue.Empty:
                        continue  # タイムアウト時は継続
                else:
                    # 入力キューがない場合（Producerワーカー）
                    item = self.produce_item()
                    if item is None:  # データ生成完了
                        break

                # データを処理
                processed_item = self.process_item(item)

                # 出力キューに送信（出力キューがある場合）
                if self.output_queue and processed_item is not None:
                    self.output_queue.put(processed_item)

                self.items_processed += 1

                # 定期的に進捗を報告
                if self.items_processed % 100 == 0:
                    self.report_progress(
                        self.items_processed, -1, f"Processed {self.items_processed} items")

            except CancellationRequestedException:
                raise  # キャンセル例外は再発生
            except Exception as e:
                self.logger.error(f"Error processing item: {e}")
                # 個別アイテムのエラーは継続（必要に応じてエラーカウンターを追加）

    @abstractmethod
    def process_item(self, item: Any) -> Any:
        """
        個別アイテムの処理（サブクラスで実装）

        Args:
            item: 処理するアイテム

        Returns:
            Any: 処理済みアイテム（Noneの場合は出力しない）
        """
        pass

    def produce_item(self) -> Optional[Any]:
        """
        アイテムの生成（Producerワーカーで実装）

        Returns:
            Optional[Any]: 生成されたアイテム（Noneで終了）
        """
        return None  # デフォルトはConsumerワーカー

    def finish_input(self) -> None:
        """入力完了をマークする（終了マーカーをキューに送信）"""
        if self.output_queue:
            self.output_queue.put(None)  # 終了マーカー
