"""
Worker Classes Package for JRA-Data Collector

このパッケージは並列データ処理のためのワーカークラス群を提供します。
Producer-Consumer パターンで高効率なデータパイプラインを実現します。

Phase 3 Update: 統一されたシグナルと構造化ログシステムを統合
"""

from .base import BaseWorker, WorkerState, CancellationToken
from .signals import WorkerSignals, LogRecord, ProgressInfo, TaskResult, LoggerMixin
from .jvlink_reader import JvLinkReaderWorker
from .etl_processor_worker import EtlProcessorWorker
from .database_writer import DatabaseWriterWorker
from .pipeline_coordinator import PipelineCoordinator

__all__ = [
    # ベースクラス
    'BaseWorker',
    'WorkerState',
    'CancellationToken',

    # 統一シグナルと構造化ログ
    'WorkerSignals',
    'LogRecord',
    'ProgressInfo',
    'TaskResult',
    'LoggerMixin',

    # ワーカーインプリメンテーション
    'JvLinkReaderWorker',
    'EtlProcessorWorker',
    'DatabaseWriterWorker',
    'PipelineCoordinator'
]
