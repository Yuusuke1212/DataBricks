"""
高度なログビューアウィジェット

マルチカラム表示、フィルタリング、検索、エクスポート機能を備えた
包括的なログ管理インターフェース
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLineEdit, QComboBox, QPushButton, QSplitter, QTextEdit, QTextBrowser, QLabel,
    QGroupBox, QCheckBox, QSpinBox, QDateTimeEdit, QFileDialog, QMessageBox,
    QHeaderView, QAbstractItemView
)
from PySide6.QtGui import QFont, QColor, QPalette

from qfluentwidgets import (
    CardWidget, StrongBodyLabel, BodyLabel, CaptionLabel,
    PushButton, LineEdit, ComboBox, CheckBox, SpinBox,
    PrimaryPushButton, TransparentPushButton
)
from qfluentwidgets import FluentIcon as FIF

from ..services.workers.signals import LogRecord


class LogLevelColors:
    """ログレベル別の色定義"""
    DEBUG = "#808080"      # グレー
    INFO = "#333333"       # 通常の黒
    WARNING = "#ff8c00"    # オレンジ
    ERROR = "#dc143c"      # 赤
    CRITICAL = "#8b0000"   # 濃い赤


class LogViewerWidget(CardWidget):
    """
    高度なログビューアウィジェット

    構造化ログの表示、フィルタリング、検索、エクスポート機能を提供
    """

    # シグナル
    log_exported = Signal(str)  # ログエクスポート完了

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LogViewerWidget")

        # ログレコードのマスターリスト
        self.log_records: List[LogRecord] = []
        self.filtered_records: List[LogRecord] = []

        # フィルタリング状態
        self.current_task_filter = "すべて表示"
        self.current_worker_filter = "すべて表示"
        self.current_level_filter = "すべて表示"
        self.current_search_text = ""
        self.show_timestamp = True
        self.auto_scroll = True

        self._init_ui()
        self._setup_connections()

    def _init_ui(self):
        """UIの初期化"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ヘッダー
        header_layout = QHBoxLayout()

        title = StrongBodyLabel("📊 リアルタイム構造化ログ")
        header_layout.addWidget(title)

        header_layout.addStretch()

        # ヘッダーのコントロール
        self.clear_button = PushButton(FIF.DELETE, "クリア")
        self.clear_button.setFixedWidth(80)

        self.export_button = PushButton(FIF.SAVE, "エクスポート")
        self.export_button.setFixedWidth(100)

        header_layout.addWidget(self.clear_button)
        header_layout.addWidget(self.export_button)

        layout.addLayout(header_layout)

        # フィルタリングコントロール
        filter_group = QGroupBox("フィルタリング・検索")
        filter_layout = QVBoxLayout(filter_group)

        # 第1行: タスク、ワーカー、レベルフィルタ
        filter_row1 = QHBoxLayout()

        filter_row1.addWidget(BodyLabel("タスク:"))
        self.task_filter_combo = ComboBox()
        self.task_filter_combo.addItem("すべて表示")
        self.task_filter_combo.setFixedWidth(150)
        filter_row1.addWidget(self.task_filter_combo)

        filter_row1.addSpacing(20)

        filter_row1.addWidget(BodyLabel("ワーカー:"))
        self.worker_filter_combo = ComboBox()
        self.worker_filter_combo.addItem("すべて表示")
        self.worker_filter_combo.setFixedWidth(120)
        filter_row1.addWidget(self.worker_filter_combo)

        filter_row1.addSpacing(20)

        filter_row1.addWidget(BodyLabel("レベル:"))
        self.level_filter_combo = ComboBox()
        level_items = ["すべて表示", "DEBUG", "INFO",
                       "WARNING", "ERROR", "CRITICAL"]
        self.level_filter_combo.addItems(level_items)
        self.level_filter_combo.setFixedWidth(100)
        filter_row1.addWidget(self.level_filter_combo)

        filter_row1.addStretch()

        filter_layout.addLayout(filter_row1)

        # 第2行: 検索とオプション
        filter_row2 = QHBoxLayout()

        filter_row2.addWidget(BodyLabel("検索:"))
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("メッセージ内容で検索...")
        self.search_input.setFixedWidth(300)
        filter_row2.addWidget(self.search_input)

        filter_row2.addSpacing(20)

        self.timestamp_checkbox = CheckBox("タイムスタンプ表示")
        self.timestamp_checkbox.setChecked(True)
        filter_row2.addWidget(self.timestamp_checkbox)

        filter_row2.addSpacing(10)

        self.autoscroll_checkbox = CheckBox("自動スクロール")
        self.autoscroll_checkbox.setChecked(True)
        filter_row2.addWidget(self.autoscroll_checkbox)

        filter_row2.addStretch()

        filter_layout.addLayout(filter_row2)

        layout.addWidget(filter_group)

        # ログ表示エリア
        self.log_text_browser = QTextBrowser()
        self.log_text_browser.setFont(QFont("Consolas", 9))
        self.log_text_browser.setStyleSheet("""
            QTextBrowser {
                border: 1px solid #cccccc;
                border-radius: 4px;
                background-color: #ffffff;
                padding: 8px;
            }
        """)

        layout.addWidget(self.log_text_browser, stretch=1)

        # ステータスバー
        status_layout = QHBoxLayout()

        self.record_count_label = CaptionLabel("0 件のログエントリ")
        self.record_count_label.setStyleSheet("color: #666666;")
        status_layout.addWidget(self.record_count_label)

        status_layout.addStretch()

        self.filter_status_label = CaptionLabel("")
        self.filter_status_label.setStyleSheet("color: #666666;")
        status_layout.addWidget(self.filter_status_label)

        layout.addLayout(status_layout)

    def _setup_connections(self):
        """シグナル・スロット接続の設定"""
        self.task_filter_combo.currentTextChanged.connect(
            self._on_task_filter_changed)
        self.worker_filter_combo.currentTextChanged.connect(
            self._on_worker_filter_changed)
        self.level_filter_combo.currentTextChanged.connect(
            self._on_level_filter_changed)
        self.search_input.textChanged.connect(self._on_search_text_changed)
        self.timestamp_checkbox.toggled.connect(
            self._on_timestamp_option_changed)
        self.autoscroll_checkbox.toggled.connect(
            self._on_autoscroll_option_changed)
        self.clear_button.clicked.connect(self.clear_logs)
        self.export_button.clicked.connect(self._export_logs)

    def add_log_record(self, log_record: LogRecord):
        """新しいログレコードを追加"""
        self.log_records.append(log_record)

        # フィルタオプションを更新
        self._update_filter_options(log_record)

        # 表示を更新
        self._update_log_display()

    def add_log_records(self, log_records: List[LogRecord]):
        """複数のログレコードを一括追加"""
        self.log_records.extend(log_records)

        # フィルタオプションを更新
        for record in log_records:
            self._update_filter_options(record)

        # 表示を更新
        self._update_log_display()

    def clear_logs(self):
        """すべてのログをクリア"""
        self.log_records.clear()
        self.filtered_records.clear()

        # フィルタオプションをリセット
        self._reset_filter_options()

        # 表示をクリア
        self.log_text_browser.clear()
        self._update_status_labels()

    def _update_filter_options(self, log_record: LogRecord):
        """フィルタオプションを更新"""
        # タスクフィルタ
        if log_record.task_name not in [self.task_filter_combo.itemText(i)
                                        for i in range(self.task_filter_combo.count())]:
            self.task_filter_combo.addItem(log_record.task_name)

        # ワーカーフィルタ
        if log_record.worker_name not in [self.worker_filter_combo.itemText(i)
                                          for i in range(self.worker_filter_combo.count())]:
            self.worker_filter_combo.addItem(log_record.worker_name)

    def _reset_filter_options(self):
        """フィルタオプションをリセット"""
        # タスクフィルタをリセット
        self.task_filter_combo.clear()
        self.task_filter_combo.addItem("すべて表示")

        # ワーカーフィルタをリセット
        self.worker_filter_combo.clear()
        self.worker_filter_combo.addItem("すべて表示")

        # レベルフィルタを初期状態に戻す
        self.level_filter_combo.setCurrentText("すべて表示")

    def _update_log_display(self):
        """ログ表示を更新"""
        # フィルタを適用
        self._apply_filters()

        # HTML文字列を生成
        html_content = self._generate_html_content()

        # 表示を更新
        old_scroll_value = self.log_text_browser.verticalScrollBar().value()
        self.log_text_browser.setHtml(html_content)

        # 自動スクロール
        if self.auto_scroll:
            self.log_text_browser.verticalScrollBar().setValue(
                self.log_text_browser.verticalScrollBar().maximum()
            )
        else:
            self.log_text_browser.verticalScrollBar().setValue(old_scroll_value)

        # ステータスラベルを更新
        self._update_status_labels()

    def _apply_filters(self):
        """フィルタを適用してfiltered_recordsを更新"""
        self.filtered_records = []

        for record in self.log_records:
            # タスクフィルタ
            if (self.current_task_filter != "すべて表示" and
                    record.task_name != self.current_task_filter):
                continue

            # ワーカーフィルタ
            if (self.current_worker_filter != "すべて表示" and
                    record.worker_name != self.current_worker_filter):
                continue

            # レベルフィルタ
            if (self.current_level_filter != "すべて表示" and
                    record.level != self.current_level_filter):
                continue

            # 検索フィルタ
            if (self.current_search_text and
                    self.current_search_text.lower() not in record.message.lower()):
                continue

            self.filtered_records.append(record)

    def _generate_html_content(self) -> str:
        """フィルタされたログレコードからHTML文字列を生成"""
        html_lines = []
        html_lines.append(
            '<html><body style="font-family: Consolas, monospace; font-size: 9pt;">')

        for record in self.filtered_records:
            color = getattr(LogLevelColors, record.level, LogLevelColors.INFO)

            # タイムスタンプ
            timestamp_str = ""
            if self.show_timestamp:
                timestamp_str = f'<span style="color: #666666;">[{record.timestamp.strftime("%H:%M:%S.%f")[:-3]}]</span> '

            # レベル
            level_str = f'<span style="color: {color}; font-weight: bold;">[{record.level}]</span> '

            # タスクとワーカー
            task_worker_str = f'<span style="color: #0066cc;">[{record.task_name}|{record.worker_name}]</span> '

            # メッセージ
            message_str = f'<span style="color: {color};">{self._escape_html(record.message)}</span>'

            # 検索ハイライト
            if self.current_search_text:
                message_str = message_str.replace(
                    self.current_search_text,
                    f'<span style="background-color: #ffff00;">{self.current_search_text}</span>'
                )

            line = f"{timestamp_str}{level_str}{task_worker_str}{message_str}<br>"
            html_lines.append(line)

        html_lines.append('</body></html>')
        return ''.join(html_lines)

    def _escape_html(self, text: str) -> str:
        """HTMLエスケープ"""
        return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#x27;'))

    def _update_status_labels(self):
        """ステータスラベルを更新"""
        total_count = len(self.log_records)
        filtered_count = len(self.filtered_records)

        self.record_count_label.setText(
            f"{filtered_count} / {total_count} 件のログエントリ")

        if total_count != filtered_count:
            self.filter_status_label.setText("フィルタ適用中")
        else:
            self.filter_status_label.setText("")

    # フィルタイベントハンドラ
    def _on_task_filter_changed(self, text: str):
        self.current_task_filter = text
        self._update_log_display()

    def _on_worker_filter_changed(self, text: str):
        self.current_worker_filter = text
        self._update_log_display()

    def _on_level_filter_changed(self, text: str):
        self.current_level_filter = text
        self._update_log_display()

    def _on_search_text_changed(self, text: str):
        self.current_search_text = text
        self._update_log_display()

    def _on_timestamp_option_changed(self, checked: bool):
        self.show_timestamp = checked
        self._update_log_display()

    def _on_autoscroll_option_changed(self, checked: bool):
        self.auto_scroll = checked

    def _export_logs(self):
        """ログをファイルにエクスポート"""
        from PySide6.QtWidgets import QFileDialog

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "ログエクスポート",
            f"jra_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;All Files (*)"
        )

        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    for record in self.filtered_records:
                        timestamp_str = record.timestamp.strftime(
                            "%Y-%m-%d %H:%M:%S.%f")[:-3]
                        line = f"[{timestamp_str}] [{record.level}] [{record.task_name}|{record.worker_name}] {record.message}\n"
                        f.write(line)

                self.log_exported.emit(f"ログを {filename} にエクスポートしました。")
            except Exception as e:
                self.log_exported.emit(f"エクスポートエラー: {str(e)}")
