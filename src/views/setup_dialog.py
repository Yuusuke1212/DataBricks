from PySide6.QtCore import QDate, Slot
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox,
    QScrollArea, QWidget, QCheckBox, QPushButton, QGroupBox, QGridLayout
)
from qfluentwidgets import CalendarPicker, BodyLabel, StrongBodyLabel


class SetupDialog(QDialog):
    """
    一括データ取得の開始日とデータ種別を設定するためのダイアログ。
    """

    # JV-Linkデータ種別一覧（日本語名とIDの対応表）
    DATA_TYPES = {
        "レース詳細": "RACE",
        "競走馬マスタ": "UM",
        "騎手マスタ": "KS",
        "調教師マスタ": "CH",
        "生産者マスタ": "BR",
        "馬主マスタ": "BN",
        "レース結果": "SE",
        "払戻": "HR",
        "オッズ": "O1",
        "確定オッズ": "O2",
        "3連単オッズ": "O3",
        "3連複オッズ": "O4",
        "ワイドオッズ": "O5",
        "単勝・複勝オッズ": "O6",
        "成績": "AV",
        "票数": "HY",
        "コース": "CS",
        "調教": "CZ",
        "厩舎コメント": "CC",
        "レーシングメモ": "RC",
        "競走成績": "SV",
        "障害レース結果": "JC",
        "地方競馬レース": "RA",
        "地方競馬結果": "JG",
        "海外レース": "WF",
        "海外レース結果": "WH",
        "重賞レース": "WE",
        "天候・馬場状態": "TK",
        "競馬場マスタ": "JO",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('一括データ取得設定')
        self.setMinimumSize(500, 600)
        self.resize(600, 700)

        # チェックボックスを格納する辞書
        self.data_type_checkboxes = {}

        # ウィジェットの作成
        self._init_ui()

    def _init_ui(self):
        """UIを初期化する"""
        layout = QVBoxLayout(self)

        # タイトル
        title_label = StrongBodyLabel('一括データ取得設定', self)
        layout.addWidget(title_label)

        # 開始日選択セクション
        date_group = QGroupBox("取得開始日", self)
        date_layout = QVBoxLayout(date_group)

        date_label = BodyLabel('取得を開始する日付を選択してください', self)
        self.calendarPicker = CalendarPicker(self)
        # デフォルト値を設定 (JRA-VANデータ提供開始時期)
        self.calendarPicker.setDate(QDate(1986, 1, 1))

        date_layout.addWidget(date_label)
        date_layout.addWidget(self.calendarPicker)
        layout.addWidget(date_group)

        # データ種別選択セクション
        data_type_group = QGroupBox("取得するデータ種別", self)
        data_type_layout = QVBoxLayout(data_type_group)

        # 全選択/全解除ボタン
        button_layout = QHBoxLayout()
        self.select_all_button = QPushButton("全て選択", self)
        self.deselect_all_button = QPushButton("全て解除", self)
        self.select_all_button.clicked.connect(self._select_all)
        self.deselect_all_button.clicked.connect(self._deselect_all)

        button_layout.addWidget(self.select_all_button)
        button_layout.addWidget(self.deselect_all_button)
        button_layout.addStretch()
        data_type_layout.addLayout(button_layout)

        # スクロールエリア
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(300)

        # チェックボックスコンテナ
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)

        # データ種別チェックボックスを動的に生成
        row = 0
        col = 0
        for japanese_name, data_id in self.DATA_TYPES.items():
            checkbox = QCheckBox(japanese_name, scroll_widget)
            checkbox.setChecked(True)  # デフォルトで全て選択
            self.data_type_checkboxes[data_id] = checkbox

            scroll_layout.addWidget(checkbox, row, col)
            col += 1
            if col >= 2:  # 2列で配置
                col = 0
                row += 1

        scroll_area.setWidget(scroll_widget)
        data_type_layout.addWidget(scroll_area)
        layout.addWidget(data_type_group)

        # ダイアログボタン
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        layout.addWidget(self.buttonBox)

        # シグナルとスロットの接続
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def _select_all(self):
        """全てのチェックボックスを選択する"""
        for checkbox in self.data_type_checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all(self):
        """全てのチェックボックスを解除する"""
        for checkbox in self.data_type_checkboxes.values():
            checkbox.setChecked(False)

    def get_selected_date(self) -> str:
        """
        選択された日付を 'YYYYMMDD' 形式の文字列で返す。
        """
        return self.calendarPicker.getDate().toString('yyyyMMdd')

    def get_selected_data_types(self) -> list:
        """
        選択されたデータ種別IDのリストを返す。
        """
        selected_types = []
        for data_id, checkbox in self.data_type_checkboxes.items():
            if checkbox.isChecked():
                selected_types.append(data_id)
        return selected_types

    @Slot()
    def accept(self):
        """OKボタンが押されたときの処理"""
        selected_types = self.get_selected_data_types()
        if not selected_types:
            # 何も選択されていない場合は警告
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "警告",
                "少なくとも1つのデータ種別を選択してください。"
            )
            return
        super().accept()
