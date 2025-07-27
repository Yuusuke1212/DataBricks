import logging
import os
import pandas as pd
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal as Signal, QThreadPool, pyqtSlot as Slot

from .db_manager import DatabaseManager


class WorkerSignals(QObject):
    """
    データエクスポートワーカスレッドから発行されるシグナルを定義します。
    """
    progress = Signal(str)
    finished = Signal()
    error = Signal(str)


class ExportWorker(QRunnable):
    """
    データエクスポート処理をバックグラウンドで実行するワーカースレッド。
    """

    def __init__(self, db_manager, params: dict):
        super().__init__()
        self.db_manager = db_manager
        self.params = params
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        """
        エクスポート処理の本体。指定されたテーブルをファイルに書き出す。
        """
        try:
            tables = self.params['tables']
            file_format = self.params['format']
            output_path = self.params['path']
            sep = ',' if file_format == 'csv' else '\t'
            is_dir = os.path.isdir(output_path)

            for table_name in tables:
                self.signals.progress.emit(
                    f"テーブル '{table_name}' のデータを読み込み中...")
                df = pd.read_sql_table(table_name, self.db_manager.engine)

                self.signals.progress.emit(f"テーブル '{table_name}' をファイルに出力中...")

                file_path = os.path.join(
                    output_path, f"{table_name}.{file_format}") if is_dir else output_path

                df.to_csv(file_path, sep=sep, index=False,
                          encoding='utf-8-sig')

        except Exception as e:
            logging.error(f"エクスポート中にエラーが発生: {e}", exc_info=True)
            self.signals.error.emit(f"エクスポートエラー: {e}")
        else:
            self.signals.finished.emit()


class ExportManager(QObject):
    """
    データエクスポート処理を管理し、非同期で実行する。
    """
    export_progress = Signal(str)
    export_finished = Signal(str)
    export_error = Signal(str)

    def __init__(self, db_manager: DatabaseManager, parent=None):
        super().__init__(parent)
        self.db_manager = db_manager
        self.thread_pool = QThreadPool()
        logging.info(
            f"ExportManager initialized with {self.thread_pool.maxThreadCount()} threads.")

    @Slot(dict)
    def start_export(self, params: dict):
        """
        エクスポート処理をワーカースレッドで開始する。
        """
        logging.info(f"エクスポート処理を開始します: {params}")
        worker = ExportWorker(self.db_manager, params)

        worker.signals.progress.connect(self.export_progress)
        worker.signals.finished.connect(
            lambda: self.export_finished.emit("データエクスポートが正常に完了しました。"))
        worker.signals.error.connect(self.export_error)

        self.thread_pool.start(worker)
