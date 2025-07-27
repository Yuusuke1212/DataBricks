"""Utility to disable QFluentWidgets の Tips ウィンドウ

外部ライブラリの __init__ が Tips 用 FluentWindow を生成してしまうと
PySide6 6.6 系では `QWidget: Must construct a QApplication before a QWidget`
を誘発する。本関数を **UI ライブラリを import する前** に呼び出すことで、
環境変数を設定して Tips 生成を完全に抑止する。
"""
from __future__ import annotations

import os

__all__ = ["patch_qfluentwidgets"]


def patch_qfluentwidgets() -> None:
    """Set env vars so qfluentwidgets skips its promotional window."""
    os.environ["QFLUENT_DISABLE_TIPS"] = "1"
    os.environ["QFLUENTWIDGET_DISABLE_TIPS"] = "1"  # フォールバック名
    os.environ["QFLUENTWIDGET_DISABLE_MESSAGE"] = "1"
    os.environ.setdefault("QT_API", "pyqt5")  # qtpy に PyQt5 を強制
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")  # Windows 固有だが冗長指定
