"""
State Machine Package for JRA-Data Collector

このパッケージはアプリケーションのライフサイクル管理のための
ステートマシンパターンを実装します。
"""

from .base import AppState
from .states import (
    IdleState,
    RequestingDataState,
    PollingDownloadState,
    ReadingDataState,
    CancellingState,
    FinalizingState,
    ErrorState
)

__all__ = [
    'AppState',
    'IdleState',
    'RequestingDataState',
    'PollingDownloadState',
    'ReadingDataState',
    'CancellingState',
    'FinalizingState',
    'ErrorState'
]
