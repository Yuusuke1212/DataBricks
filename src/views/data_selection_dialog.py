#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
データ種別選択ダイアログ

セットアップデータ、差分更新、速報データの各種データ種別を
ユーザーが選択できる汎用的なダイアログを提供
"""

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QDialogButtonBox,
    QScrollArea, QWidget, QCheckBox, QPushButton, QGroupBox,
    QGridLayout, QTabWidget
)
from qfluentwidgets import CalendarPicker, BodyLabel, StrongBodyLabel
from typing import Dict, List


class DataSelectionDialog(QDialog):
    """
    データ種別選択ダイアログ
    
    様々なモード（セットアップ、差分更新、速報設定）に対応した
    データ種別選択機能を提供
    """

    # JV-Linkデータ種別の詳細定義
    DATA_CATEGORIES = {
        "基本データ": {
            "RACE": ("レース詳細", "race", True),
            "SE": ("レース結果", "result", True),
            "HR": ("払戻", "payout", True),
            "UM": ("競走馬マスタ", "horse", True),
            "KS": ("騎手マスタ", "jockey", True),
            "CH": ("調教師マスタ", "trainer", False),
            "BR": ("生産者マスタ", "breeder", False),
            "BN": ("馬主マスタ", "owner", False),
        },
        "オッズ系": {
            "O1": ("オッズ", "odds", False),
            "O2": ("確定オッズ", "final_odds", False),
            "O3": ("3連単オッズ", "trifecta_odds", False),
            "O4": ("3連複オッズ", "trio_odds", False),
            "O5": ("ワイドオッズ", "wide_odds", False),
            "O6": ("単勝・複勝オッズ", "win_place_odds", False),
        },
        "付加情報": {
            "AV": ("成績", "performance", False),
            "HY": ("票数", "votes", False),
            "CS": ("コース", "course", False),
            "CZ": ("調教", "training", False),
            "CC": ("厩舎コメント", "stable_comment", False),
            "RC": ("レーシングメモ", "racing_memo", False),
            "SV": ("競走成績", "race_performance", False),
        },
        "特殊レース": {
            "JC": ("障害レース結果", "steeplechase", False),
            "RA": ("地方競馬レース", "local_race", False),
            "JG": ("地方競馬結果", "local_result", False),
            "WF": ("海外レース", "foreign_race", False),
            "WH": ("海外レース結果", "foreign_result", False),
            "WE": ("重賞レース", "stakes_race", False),
        },
        "環境・その他": {
            "TK": ("天候・馬場状態", "weather_track", False),
            "JO": ("競馬場マスタ", "racetrack", False),
        }
    }

    # プリセット設定
    PRESETS = {
        "セットアップ推奨": ["RACE", "SE", "HR", "UM", "KS"],
        "差分更新推奨": ["RACE", "SE", "HR"],
        "最小構成": ["RACE", "SE"],
        "完全セット": list(sum([list(cat.keys()) for cat in DATA_CATEGORIES.values()], [])),
        "オッズ重視": ["RACE", "SE", "O1", "O2", "O6"],
        "マスタ重視": ["UM", "KS", "CH", "BR", "BN", "JO"],
    }

    # 速報イベント種別
    REALTIME_EVENTS = {
        "レース関連": {
            "race_start": ("レース開始", True),
            "race_result": ("レース結果確定", True),
            "payout": ("払戻発表", True),
            "scratched": ("取消・除外", True),
        },
        "オッズ関連": {
            "odds_update": ("オッズ更新", False),
            "vote_update": ("投票数更新", False),
            "final_odds": ("確定オッズ", False),
        },
        "競馬場情報": {
            "weather_change": ("天候変更", False),
            "track_condition": ("馬場状態変更", False),
            "course_change": ("コース変更", False),
        }
    }

    def __init__(self, mode: str = "setup", parent=None):
        """
        データ選択ダイアログの初期化
        
        Args:
            mode: 動作モード ("setup", "differential", "realtime")
            parent: 親ウィジェット
        """
        super().__init__(parent)

        self.mode = mode
        self.data_type_checkboxes = {}
        self.realtime_checkboxes = {}

        self._setup_dialog_properties()
        self._init_ui()

    def _setup_dialog_properties(self):
        """ダイアログのプロパティを設定"""
        mode_titles = {
            "setup": "セットアップデータ取得設定",
            "differential": "差分データ更新設定",
            "realtime": "速報受信設定"
        }

        self.setWindowTitle(mode_titles.get(self.mode, "データ選択"))
        self.setMinimumSize(600, 700)
        self.resize(700, 800)

    def _init_ui(self):
        """UIを初期化"""
        layout = QVBoxLayout(self)

        # タイトル
        title_text = {
            "setup": "🚀 セットアップデータ取得設定",
            "differential": "🔄 差分データ更新設定",
            "realtime": "📡 速報受信設定"
        }
        title_label = StrongBodyLabel(title_text.get(self.mode, "データ選択"), self)
        layout.addWidget(title_label)

        # タブウィジェット
        tab_widget = QTabWidget(self)

        if self.mode in ["setup", "differential"]:
            # 日付選択タブ（セットアップと差分更新用）
            if self.mode == "setup":
                date_tab = self._create_date_selection_tab()
                tab_widget.addTab(date_tab, "📅 取得開始日")

            # データ種別選択タブ
            data_tab = self._create_data_selection_tab()
            tab_widget.addTab(data_tab, "📊 データ種別")

        elif self.mode == "realtime":
            # 速報設定タブ
            realtime_tab = self._create_realtime_selection_tab()
            tab_widget.addTab(realtime_tab, "📡 速報設定")

        layout.addWidget(tab_widget)

        # ダイアログボタン
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self
        )
        layout.addWidget(self.buttonBox)

        # シグナル接続
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

    def _create_date_selection_tab(self) -> QWidget:
        """日付選択タブを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 説明
        description = BodyLabel(
            "取得を開始する日付を選択してください。\n"
            "※ 過去の日付を指定すると大量のデータをダウンロードする可能性があります。",
            widget
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        # カレンダー
        date_group = QGroupBox("取得開始日", widget)
        date_layout = QVBoxLayout(date_group)

        self.calendarPicker = CalendarPicker(widget)
        # デフォルト値を設定（JRA-VANデータ提供開始時期）
        self.calendarPicker.setDate(QDate(1986, 1, 1))

        date_layout.addWidget(self.calendarPicker)
        layout.addWidget(date_group)

        layout.addStretch()
        return widget

    def _create_data_selection_tab(self) -> QWidget:
        """データ種別選択タブを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # プリセット選択
        preset_group = QGroupBox("📋 プリセット選択", widget)
        preset_layout = QHBoxLayout(preset_group)

        for preset_name in self.PRESETS.keys():
            btn = QPushButton(preset_name, widget)
            btn.clicked.connect(lambda checked, name=preset_name: self._apply_preset(name))
            preset_layout.addWidget(btn)

        preset_layout.addStretch()
        layout.addWidget(preset_group)

        # 全選択/全解除ボタン
        button_layout = QHBoxLayout()
        self.select_all_button = QPushButton("✓ 全て選択", widget)
        self.deselect_all_button = QPushButton("✗ 全て解除", widget)
        self.select_all_button.clicked.connect(self._select_all_data)
        self.deselect_all_button.clicked.connect(self._deselect_all_data)

        button_layout.addWidget(self.select_all_button)
        button_layout.addWidget(self.deselect_all_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # スクロールエリア
        scroll_area = QScrollArea(widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(400)

        # カテゴリ別チェックボックス
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        for category_name, data_types in self.DATA_CATEGORIES.items():
            category_group = QGroupBox(f"📁 {category_name}", scroll_widget)
            category_layout = QGridLayout(category_group)

            row = 0
            col = 0
            for data_id, (japanese_name, _, default_checked) in data_types.items():
                checkbox = QCheckBox(f"{japanese_name} ({data_id})", category_group)

                # モードに応じたデフォルト選択
                if self.mode == "setup":
                    checkbox.setChecked(data_id in self.PRESETS["セットアップ推奨"])
                elif self.mode == "differential":
                    checkbox.setChecked(data_id in self.PRESETS["差分更新推奨"])
                else:
                    checkbox.setChecked(default_checked)

                self.data_type_checkboxes[data_id] = checkbox
                category_layout.addWidget(checkbox, row, col)

                col += 1
                if col >= 2:  # 2列配置
                    col = 0
                    row += 1

            scroll_layout.addWidget(category_group)

        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        return widget

    def _create_realtime_selection_tab(self) -> QWidget:
        """速報選択タブを作成"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # 説明
        description = BodyLabel(
            "受信したい速報イベントを選択してください。\n"
            "※ 多くのイベントを選択すると、システムリソースを多く消費します。",
            widget
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        # 全選択/全解除ボタン
        button_layout = QHBoxLayout()
        select_all_realtime_btn = QPushButton("✓ 全て選択", widget)
        deselect_all_realtime_btn = QPushButton("✗ 全て解除", widget)
        select_all_realtime_btn.clicked.connect(self._select_all_realtime)
        deselect_all_realtime_btn.clicked.connect(self._deselect_all_realtime)

        button_layout.addWidget(select_all_realtime_btn)
        button_layout.addWidget(deselect_all_realtime_btn)
        button_layout.addStretch()
        layout.addLayout(button_layout)

        # スクロールエリア
        scroll_area = QScrollArea(widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(300)

        # カテゴリ別速報イベントチェックボックス
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        for category_name, events in self.REALTIME_EVENTS.items():
            category_group = QGroupBox(f"📡 {category_name}", scroll_widget)
            category_layout = QGridLayout(category_group)

            row = 0
            col = 0
            for event_id, (event_name, default_checked) in events.items():
                checkbox = QCheckBox(f"{event_name} ({event_id})", category_group)
                checkbox.setChecked(default_checked)

                self.realtime_checkboxes[event_id] = checkbox
                category_layout.addWidget(checkbox, row, col)

                col += 1
                if col >= 2:  # 2列配置
                    col = 0
                    row += 1

            scroll_layout.addWidget(category_group)

        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)

        return widget

    def _apply_preset(self, preset_name: str):
        """プリセットを適用"""
        if preset_name not in self.PRESETS:
            return

        preset_data_types = self.PRESETS[preset_name]

        # 全てのチェックボックスを一度解除
        for checkbox in self.data_type_checkboxes.values():
            checkbox.setChecked(False)

        # プリセットに含まれるデータ種別をチェック
        for data_id in preset_data_types:
            if data_id in self.data_type_checkboxes:
                self.data_type_checkboxes[data_id].setChecked(True)

    def _select_all_data(self):
        """全てのデータ種別を選択"""
        for checkbox in self.data_type_checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all_data(self):
        """全てのデータ種別を解除"""
        for checkbox in self.data_type_checkboxes.values():
            checkbox.setChecked(False)

    def _select_all_realtime(self):
        """全ての速報イベントを選択"""
        for checkbox in self.realtime_checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all_realtime(self):
        """全ての速報イベントを解除"""
        for checkbox in self.realtime_checkboxes.values():
            checkbox.setChecked(False)

    # === 結果取得メソッド ===

    def get_selected_date(self) -> str:
        """
        選択された日付を 'YYYYMMDD' 形式で返す
        
        Returns:
            日付文字列（セットアップモード時のみ）
        """
        if hasattr(self, 'calendarPicker'):
            return self.calendarPicker.getDate().toString('yyyyMMdd')
        return ""

    def get_selected_data_types(self) -> List[str]:
        """
        選択されたデータ種別IDのリストを返す
        
        Returns:
            データ種別IDのリスト（例: ['RACE', 'SE', 'HR']）
        """
        selected = []
        for data_id, checkbox in self.data_type_checkboxes.items():
            if checkbox.isChecked():
                selected.append(data_id)
        return selected

    def get_selected_realtime_events(self) -> List[str]:
        """
        選択された速報イベントIDのリストを返す
        
        Returns:
            速報イベントIDのリスト
        """
        selected = []
        for event_id, checkbox in self.realtime_checkboxes.items():
            if checkbox.isChecked():
                selected.append(event_id)
        return selected

    def get_selection_summary(self) -> Dict:
        """
        選択内容の要約を取得
        
        Returns:
            選択内容の辞書
        """
        result = {
            "mode": self.mode,
            "data_types": self.get_selected_data_types(),
            "data_count": len(self.get_selected_data_types())
        }

        if self.mode == "setup":
            result["start_date"] = self.get_selected_date()

        if self.mode == "realtime":
            result["realtime_events"] = self.get_selected_realtime_events()
            result["event_count"] = len(self.get_selected_realtime_events())

        return result

    @classmethod
    def get_data_type_name(cls, data_id: str) -> str:
        """
        データ種別IDから日本語名を取得
        
        Args:
            data_id: データ種別ID（例: 'RACE'）
            
        Returns:
            日本語名（例: 'レース詳細'）
        """
        for category in cls.DATA_CATEGORIES.values():
            if data_id in category:
                return category[data_id][0]
        return data_id  # 見つからない場合はIDをそのまま返す
