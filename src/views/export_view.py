"""
データ表示・出力画面 - レポート セクション3.3準拠

JVReadで取得した生データを、構造化されたインタラクティブな表形式で表示し、
分析しやすい形でエクスポートする機能を提供
"""

from datetime import datetime
from typing import Dict, List
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel, QAbstractTableModel, QModelIndex, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableView, QHeaderView,
    QFileDialog, QFrame
)

from qfluentwidgets import (
    TitleLabel, StrongBodyLabel, BodyLabel, CaptionLabel, LineEdit, ComboBox,
    PrimaryPushButton, PushButton, InfoBar, InfoBarPosition, CardWidget,
    FluentIcon as FIF, ScrollArea
)


class DataTableModel(QAbstractTableModel):
    """データテーブル用のモデル"""

    def __init__(self, data: List[Dict] = None, headers: List[str] = None, parent=None):
        super().__init__(parent)
        self._data = data or []
        self._headers = headers or []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._data)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._headers)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self._data)):
            return None

        row_data = self._data[index.row()]
        column_key = self._headers[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            return str(row_data.get(column_key, ""))

        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._headers[section] if section < len(self._headers) else ""
            else:
                return str(section + 1)
        return None

    def update_data(self, data: List[Dict], headers: List[str]):
        """データを更新"""
        self.beginResetModel()
        self._data = data
        self._headers = headers
        self.endResetModel()


class DataExportView(QWidget):
    """
    データ表示・出力画面 - UI/UX改善指示書準拠
    コンポーネントの役割を明確化し、視覚的な一貫性を向上。
    """
    data_load_requested = Signal(str)
    export_requested = Signal(dict)

    def __init__(self, table_names: List[str], parent=None):
        super().__init__(parent)
        self.setObjectName("DataExportView")

        self._init_ui()
        self._setup_table()
        self.update_available_tables(table_names)

    def _init_ui(self):
        """UIの初期化 - 8pxスペーシングシステムとコントラスト改善を適用"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_container = QWidget()
        title_layout = QHBoxLayout(title_container)
        title_layout.setContentsMargins(36, 20, 36, 12)
        title_label = TitleLabel("データ表示と出力", title_container)
        title_layout.addWidget(title_label)
        layout.addWidget(title_container)

        scroll_area = ScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        layout.addWidget(scroll_area)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(36, 8, 36, 24)
        scroll_layout.setSpacing(16)
        scroll_widget.setObjectName("ExportScrollWidget")
        scroll_area.setWidget(scroll_widget)

        self._create_data_selection_card(scroll_layout)
        self._create_data_table_card(scroll_layout)
        self._create_export_actions_card(scroll_layout)

    def _create_data_selection_card(self, parent_layout):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("📊 データソース選択"))

        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)

        self.data_type_combo = ComboBox()
        self.data_type_combo.setPlaceholderText("テーブルを選択...")
        self.data_type_combo.setMinimumHeight(32)

        self.load_data_btn = PrimaryPushButton("データを読み込み")
        self.load_data_btn.setMinimumHeight(32)
        self.load_data_btn.setIcon(FIF.SYNC)
        self.load_data_btn.clicked.connect(self._load_data)

        controls_layout.addWidget(BodyLabel("表示するテーブル:"))
        controls_layout.addWidget(self.data_type_combo, 1)
        controls_layout.addWidget(self.load_data_btn)
        layout.addLayout(controls_layout)

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(8)
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("テーブル内を検索...")
        self.search_input.setMinimumHeight(32)
        self.search_input.textChanged.connect(self._apply_filters)

        filter_layout.addWidget(BodyLabel("絞り込み検索:"))
        filter_layout.addWidget(self.search_input, 1)
        layout.addLayout(filter_layout)

        parent_layout.addWidget(card)

    def _create_data_table_card(self, parent_layout):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_layout.addWidget(StrongBodyLabel("📋 データプレビュー"))
        header_layout.addStretch()
        self.data_count_label = CaptionLabel("0件")
        header_layout.addWidget(self.data_count_label)
        layout.addLayout(header_layout)

        self.data_table = QTableView()
        self.data_table.setMinimumHeight(400)
        self.data_table.setPlaceholderText("「データを読み込み」ボタンを押して、表示するデータをロードしてください。")
        layout.addWidget(self.data_table)
        parent_layout.addWidget(card)

    def _create_export_actions_card(self, parent_layout):
        card = CardWidget()
        layout = QVBoxLayout(card)
        layout.setSpacing(12)

        layout.addWidget(StrongBodyLabel("📤 データのエクスポート"))
        layout.addWidget(BodyLabel("現在プレビューに表示されているデータをファイルに出力します。"))

        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        self.export_csv_btn = PushButton("CSV形式でエクスポート")
        self.export_csv_btn.setMinimumHeight(32)
        self.export_csv_btn.setIcon(FIF.SAVE)
        self.export_csv_btn.clicked.connect(lambda: self._export_data("csv"))
        buttons_layout.addWidget(self.export_csv_btn)
        layout.addLayout(buttons_layout)

        parent_layout.addWidget(card)

    def update_available_tables(self, table_names: List[str]):
        """利用可能なテーブルリストを更新"""
        self.data_type_combo.clear()
        self.data_type_combo.addItems(table_names)

    def _setup_table(self):
        """テーブルの設定"""
        # データモデルの設定
        self.table_model = DataTableModel()

        # ソート・フィルタープロキシモデル
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.table_model)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)

        # テーブルにモデルを設定
        self.data_table.setModel(self.proxy_model)

        # ヘッダー設定（ソート機能を有効化）
        header = self.data_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setSortIndicatorShown(True)

        # テーブルクリックでソート
        self.data_table.setSortingEnabled(True)

    @Slot(str)
    def _on_data_type_changed(self, data_type: str):
        """データ種別変更時の処理"""
        # このメソッドは現在使用されていませんが、将来の拡張のために残します
        pass

    @Slot()
    def _load_data(self):
        """データ読み込み"""
        selected_type = self.data_type_combo.currentText()
        if not selected_type or selected_type == "テーブルを選択...":
            InfoBar.warning(
                title="選択エラー",
                content="表示するテーブルを選択してください。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        # データ読み込み要求を発行
        self.data_load_requested.emit(selected_type)

    def load_sample_data(self):
        """サンプルデータの読み込み（開発用）"""
        # JV-Data仕様書に基づくサンプルデータ
        sample_headers = ["開催日", "レース名", "馬名", "騎手", "着順", "タイム"]
        sample_data = [
            {
                "開催日": "2024-01-27", "レース名": "東京1R", "馬名": "サンプル馬1",
                "騎手": "佐藤騎手", "着順": "1", "タイム": "1:23.4"
            },
            {
                "開催日": "2024-01-27", "レース名": "東京1R", "馬名": "サンプル馬2",
                "騎手": "田中騎手", "着順": "2", "タイム": "1:23.8"
            },
            {
                "開催日": "2024-01-27", "レース名": "東京2R", "馬名": "サンプル馬3",
                "騎手": "鈴木騎手", "着順": "1", "タイム": "1:35.2"
            },
        ]

        self.update_data_display(sample_data, sample_headers)

    def update_data_display(self, data: List[Dict], headers: List[str]):
        """データ表示を更新"""
        self.current_data = data
        self.current_headers = headers

        # テーブルモデルを更新
        self.table_model.update_data(data, headers)

        # データ件数表示を更新
        self._update_data_count()

        if data:
            InfoBar.success(
                title="データ読み込み完了",
                content=f"{len(data)}件のデータを読み込みました。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=2000,
                parent=self
            )

    @Slot()
    def _apply_filters(self):
        """フィルタリングを適用"""
        search_text = self.search_input.text()
        self.proxy_model.setFilterWildcard(f"*{search_text}*")
        self.proxy_model.setFilterKeyColumn(-1)
        self._update_data_count()

    def _update_data_count(self):
        """データ件数表示を更新"""
        filtered_count = self.proxy_model.rowCount()
        self.data_count_label.setText(f"{filtered_count}件")

    @Slot(str)
    def _export_data(self, format_type: str):
        """データエクスポート"""
        if not hasattr(self, 'current_data') or not self.current_data:
            InfoBar.warning(
                title="エクスポートエラー",
                content="エクスポートするデータがありません。",
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"{format_type.upper()}形式でエクスポート",
            f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}",
            f"{format_type.upper()} Files (*.{format_type})"
        )

        if file_path:
            export_settings = {
                'file_path': file_path,
                'format': format_type,
                'data': self._get_filtered_data(),
                'headers': self.current_headers
            }
            self.export_requested.emit(export_settings)

    def _get_filtered_data(self) -> List[Dict]:
        """フィルタリング後のデータを取得"""
        filtered_data = []
        for row in range(self.proxy_model.rowCount()):
            source_row = self.proxy_model.mapToSource(self.proxy_model.index(row, 0)).row()
            if hasattr(self, 'current_data') and source_row < len(self.current_data):
                filtered_data.append(self.current_data[source_row])
        return filtered_data

    def on_export_completed(self, success: bool, message: str):
        """エクスポート完了通知"""
        if success:
            InfoBar.success(
                "エクスポート完了", message, orient=Qt.Orientation.Horizontal,
                isClosable=True, position=InfoBarPosition.TOP, duration=3000, parent=self
            )
        else:
            InfoBar.error(
                "エクスポートエラー", message, orient=Qt.Orientation.Horizontal,
                isClosable=True, position=InfoBarPosition.TOP, duration=5000, parent=self
            )


# 後方互換性のためのエイリアス
ExportView = DataExportView
