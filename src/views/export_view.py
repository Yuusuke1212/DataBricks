"""
データ表示・出力画面 - レポート セクション3.3準拠

JVReadで取得した生データを、構造化されたインタラクティブな表形式で表示し、
分析しやすい形でエクスポートする機能を提供
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel, QAbstractTableModel, QModelIndex, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTableView,
    QHeaderView,
    QFileDialog,
    QMessageBox,
    QAbstractItemView,
)

# QFluentWidgets components - レポート セクション3.3準拠
from qfluentwidgets import (
    TitleLabel,
    SubtitleLabel,
    PrimaryPushButton,
    PushButton,
    InfoBar,
    InfoBarPosition,
    CardWidget,
    StrongBodyLabel,
    BodyLabel,
    CaptionLabel,
    LineEdit,
    ComboBox,
    ScrollArea,
)
from qfluentwidgets import FluentIcon as FIF

from ..utils.theme_manager import get_theme_manager


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
    データ表示・出力画面 - レポート セクション3.3準拠
    
    JVReadで取得した生データを構造化されたインタラクティブな表形式で表示し、
    フィルタリング・ソート・エクスポート機能を提供
    """
    
    # シグナル定義
    data_load_requested = Signal(str)  # データ種別指定でのデータ読み込み要求
    export_requested = Signal(dict)    # エクスポート要求
    
    def __init__(self, table_names: List[str], parent=None):
        super().__init__(parent)
        self.table_names = table_names
        self.setObjectName("DataExportView")
        self.theme_manager = get_theme_manager()
        
        # データ管理
        self.current_data = []
        self.filtered_data = []
        self.current_headers = []
        
        self._init_ui()
        self._setup_table()

    def _init_ui(self):
        """レポート セクション3.3: データ表示画面レイアウトの実装"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(20)

        # タイトル
        title = TitleLabel("データ出力", self)
        layout.addWidget(title)

        # データ選択・フィルタリングカード
        self._create_data_selection_card(layout)
        
        # データ表示テーブル（メインコンポーネント）
        self._create_data_table_card(layout)
        
        # エクスポートアクションカード
        self._create_export_actions_card(layout)

    def _create_data_selection_card(self, parent_layout):
        """データ選択・フィルタリングカード"""
        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # カードタイトル
        title = StrongBodyLabel("📊 データ選択・フィルタリング")
        card_layout.addWidget(title)
        
        # データ選択・フィルタリングコントロール
        controls_layout = QHBoxLayout()
        
        # データ種別選択
        self.data_type_combo = ComboBox()
        self.data_type_combo.setPlaceholderText("データ種別を選択...")
        self.data_type_combo.addItems([
            "レース詳細",
            "オッズ情報", 
            "払戻情報",
            "馬基本情報",
            "血統情報",
            "調教情報"
        ])
        self.data_type_combo.currentTextChanged.connect(self._on_data_type_changed)
        controls_layout.addWidget(BodyLabel("データ種別:"))
        controls_layout.addWidget(self.data_type_combo)
        
        # データ読み込みボタン
        self.load_data_btn = PrimaryPushButton("データを読み込む")
        self.load_data_btn.setIcon(FIF.UPDATE.icon())  # .icon()メソッドを使用
        self.load_data_btn.clicked.connect(self._load_data)
        controls_layout.addWidget(self.load_data_btn)
        
        # データ件数表示
        self.data_count_label = BodyLabel("データ件数: 0")
        controls_layout.addWidget(self.data_count_label)
        
        controls_layout.addStretch()
        card_layout.addLayout(controls_layout)
        
        # フィルタリングコントロール
        filter_layout = QHBoxLayout()
        
        # 検索フィールド
        self.search_input = LineEdit()
        self.search_input.setPlaceholderText("データを検索...")
        self.search_input.textChanged.connect(self._apply_filters)
        filter_layout.addWidget(BodyLabel("検索:"))
        filter_layout.addWidget(self.search_input)
        
        # 列フィルター
        self.column_filter_combo = ComboBox()
        self.column_filter_combo.setPlaceholderText("すべての列")
        self.column_filter_combo.currentTextChanged.connect(self._apply_filters)
        filter_layout.addWidget(BodyLabel("列:"))
        filter_layout.addWidget(self.column_filter_combo)
        
        filter_layout.addStretch()
        card_layout.addLayout(filter_layout)
        
        parent_layout.addWidget(card)

    def _create_data_table_card(self, parent_layout):
        """データ表示テーブルカード"""
        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # カードタイトル
        header_layout = QHBoxLayout()
        title = StrongBodyLabel("📋 データテーブル")
        self.data_count_label = CaptionLabel("データ件数: 0件")
        
        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.data_count_label)
        
        card_layout.addLayout(header_layout)
        
        # TableView（メインコンポーネント）
        self.data_table = QTableView()
        self.data_table.setMinimumHeight(400)
        self.data_table.setAlternatingRowColors(True)
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.data_table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        
        card_layout.addWidget(self.data_table)
        parent_layout.addWidget(card)

    def _create_export_actions_card(self, parent_layout):
        """エクスポートアクションカード"""
        card = CardWidget()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(16)
        
        # カードタイトル
        title = StrongBodyLabel("📤 エクスポート")
        card_layout.addWidget(title)
        
        description = CaptionLabel("表示・フィルタリングされているデータを各種形式でエクスポートできます。")
        card_layout.addWidget(description)
        
        # エクスポートボタン群
        buttons_layout = QHBoxLayout()
        
        # CSV エクスポートボタン
        self.export_csv_btn = PrimaryPushButton("CSV形式でエクスポート")
        self.export_csv_btn.setIcon(FIF.DOCUMENT.icon())  # .icon()メソッドを使用
        self.export_csv_btn.clicked.connect(lambda: self._export_data("csv"))
        buttons_layout.addWidget(self.export_csv_btn)
        
        # Excel エクスポートボタン
        self.export_excel_btn = PushButton("Excel形式でエクスポート")
        self.export_excel_btn.setIcon(FIF.DOCUMENT.icon())  # .icon()メソッドを使用
        self.export_excel_btn.clicked.connect(lambda: self._export_data("excel"))
        buttons_layout.addWidget(self.export_excel_btn)
        
        buttons_layout.addStretch()
        card_layout.addLayout(buttons_layout)
        
        parent_layout.addWidget(card)

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
        # 列フィルターコンボボックスをリセット
        self.column_filter_combo.clear()
        self.column_filter_combo.addItem("すべての列")

    @Slot()
    def _load_data(self):
        """データ読み込み"""
        selected_type = self.data_type_combo.currentText()
        if not selected_type:
            InfoBar.warning(
                title="選択エラー",
                content="データ種別を選択してください。",
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
            {"開催日": "2024-01-27", "レース名": "東京1R", "馬名": "サンプル馬1", "騎手": "佐藤騎手", "着順": "1", "タイム": "1:23.4"},
            {"開催日": "2024-01-27", "レース名": "東京1R", "馬名": "サンプル馬2", "騎手": "田中騎手", "着順": "2", "タイム": "1:23.8"},
            {"開催日": "2024-01-27", "レース名": "東京2R", "馬名": "サンプル馬3", "騎手": "鈴木騎手", "着順": "1", "タイム": "1:35.2"},
        ]
        
        self.update_data_display(sample_data, sample_headers)

    def update_data_display(self, data: List[Dict], headers: List[str]):
        """データ表示を更新"""
        self.current_data = data
        self.current_headers = headers
        self.filtered_data = data.copy()
        
        # テーブルモデルを更新
        self.table_model.update_data(data, headers)
        
        # 列フィルターコンボボックスを更新
        self.column_filter_combo.clear()
        self.column_filter_combo.addItem("すべての列")
        self.column_filter_combo.addItems(headers)
        
        # データ件数表示を更新
        self._update_data_count()
        
        # 成功通知
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
        selected_column = self.column_filter_combo.currentText()
        
        # プロキシモデルにフィルタを設定
        if search_text:
            self.proxy_model.setFilterWildcard(f"*{search_text}*")
        else:
            self.proxy_model.setFilterWildcard("")
            
        # 列フィルター（実装詳細は省略）
        if selected_column and selected_column != "すべての列":
            # 特定の列のみをフィルタリング
            column_index = self.current_headers.index(selected_column) if selected_column in self.current_headers else -1
            if column_index >= 0:
                self.proxy_model.setFilterKeyColumn(column_index)
        else:
            self.proxy_model.setFilterKeyColumn(-1)  # 全列を対象
        
        self._update_data_count()

    def _update_data_count(self):
        """データ件数表示を更新"""
        total_count = len(self.current_data)
        filtered_count = self.proxy_model.rowCount()
        
        if total_count == filtered_count:
            self.data_count_label.setText(f"データ件数: {total_count}件")
        else:
            self.data_count_label.setText(f"データ件数: {filtered_count}件 (全{total_count}件中)")

    @Slot(str)
    def _export_data(self, format_type: str):
        """データエクスポート"""
        if not self.current_data:
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
        
        # ファイル選択ダイアログ
        file_filters = {
            "csv": "CSV Files (*.csv)",
            "excel": "Excel Files (*.xlsx)"
        }
        
        filter_string = file_filters.get(format_type, "All Files (*.*)")
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"{format_type.upper()}形式でエクスポート",
            f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}",
            filter_string
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
            if source_row < len(self.current_data):
                filtered_data.append(self.current_data[source_row])
        
        return filtered_data

    def on_export_completed(self, success: bool, message: str):
        """エクスポート完了通知"""
        if success:
            InfoBar.success(
                title="エクスポート完了",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=3000,
                parent=self
            )
        else:
            InfoBar.error(
                title="エクスポートエラー",
                content=message,
                orient=Qt.Orientation.Horizontal,
                isClosable=True,
                position=InfoBarPosition.TOP,
                duration=5000,
                parent=self
            )


# 後方互換性のためのエイリアス
ExportView = DataExportView
