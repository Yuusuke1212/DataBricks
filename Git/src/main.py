#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JRA-Data Collector メインアプリケーション

日本語パス対応とUnicode例外処理を含む
"""

from .monkey_patch_qfluent import patch_qfluentwidgets
from .controllers.app_controller import AppController
from .views.main_window import MainWindow
from qfluentwidgets import FluentTranslator, FluentIcon
import qfluentwidgets
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QTranslator, QLocale
from PySide6.QtWidgets import QApplication, QMessageBox
import sys
import os
import logging
import types
from pathlib import Path

# PySide6/PyQt5 互換性シム (最優先で実行)


def setup_qt_compatibility():
    """PySide6とPyQt5の互換性を確保"""
    try:
        import PySide6.QtCore as _QtCore
        import PySide6.QtWidgets as _QtWidgets
        import PySide6.QtGui as _QtGui

        # PyQt5 スタイルのシグナル/スロット名を追加
        _QtCore.pyqtSignal = _QtCore.Signal
        _QtCore.pyqtSlot = _QtCore.Slot

        # PyQt5 モジュールのエイリアスを作成
        _pyqt5 = types.ModuleType("PyQt5")
        _pyqt5.QtCore = _QtCore
        _pyqt5.QtWidgets = _QtWidgets
        _pyqt5.QtGui = _QtGui

        # sys.modules に登録
        sys.modules.setdefault("PyQt5", _pyqt5)
        sys.modules.setdefault("PyQt5.QtCore", _QtCore)
        sys.modules.setdefault("PyQt5.QtWidgets", _QtWidgets)
        sys.modules.setdefault("PyQt5.QtGui", _QtGui)

        print("PyQt5/PySide6 互換性シム設定完了")

    except ImportError as e:
        print(f"Qt 互換性シム設定エラー: {e}")


# 最優先で互換性シムを設定
setup_qt_compatibility()

# Qt imports with unicode support
os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '1'

# 日本語パス対応: PySide6 import前の環境設定


def setup_qt_unicode_environment():
    """Qt アプリケーション用のUnicode環境設定"""
    try:
        # Qt関連の環境変数を設定
        os.environ['QT_SCALE_FACTOR'] = '1'
        os.environ['QT_ENABLE_HIGHDPI_SCALING'] = '1'

        # Windows Console UTF-8対応
        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.kernel32.SetConsoleOutputCP(65001)  # UTF-8
            except Exception:
                pass

    except Exception as e:
        print(f"Qt Unicode環境設定エラー: {e}")


# Unicode環境設定を事前実行
setup_qt_unicode_environment()


# アプリケーションが既にインポートされた後に実行


# ログ設定（Unicode対応）

def setup_unicode_logging():
    """Unicode対応のログ設定"""
    try:
        log_format = '%(asctime)s [%(levelname)s] %(message)s'

        # ログファイルのパスも安全に設定
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "jra_data_collector.log"

        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(str(log_file), encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

        print(f"ログファイル設定: {log_file}")

    except Exception as e:
        print(f"ログ設定エラー: {e}")
        # フォールバック: 基本的なログ設定
        logging.basicConfig(level=logging.INFO, format=log_format)


def handle_unicode_exception(exc_type, exc_value, exc_traceback):
    """
    Unicode関連例外の専用ハンドラー
    """
    import traceback

    error_msg = ''.join(traceback.format_exception(
        exc_type, exc_value, exc_traceback))

    if isinstance(exc_value, UnicodeDecodeError):
        print("=" * 60)
        print("Unicode デコードエラーが発生しました")
        print("原因: 日本語を含むパスまたはファイル名の処理に問題があります")
        print("対処法:")
        print("1. アプリケーションを英数字のみのパスに移動してください")
        print("2. または、以下の環境変数を設定してください:")
        print("   set PYTHONUTF8=1")
        print("   set PYTHONIOENCODING=utf-8")
        print("=" * 60)
        print(f"詳細なエラー情報:\n{error_msg}")

        # ログにも記録
        logging.error(f"Unicode decode error: {error_msg}")

    elif isinstance(exc_value, UnicodeEncodeError):
        print("=" * 60)
        print("Unicode エンコードエラーが発生しました")
        print("原因: 文字エンコーディングの変換に問題があります")
        print("=" * 60)
        print(f"詳細なエラー情報:\n{error_msg}")

        # ログにも記録
        logging.error(f"Unicode encode error: {error_msg}")

    else:
        # その他のエラーは標準のハンドラーに任せる
        sys.__excepthook__(exc_type, exc_value, exc_traceback)


def launch_gui():
    """
    GUIアプリケーションを起動する関数

    run.pyから呼び出されることを想定したGUI起動のエントリーポイント
    """
    try:
        logging.info("launch_gui()関数を開始します")
        
        # グローバル例外ハンドラーを設定
        sys.excepthook = handle_unicode_exception

        # Unicode対応ログ設定
        setup_unicode_logging()

        logging.info(
            "============================================================")
        logging.info("JRA-Data Collector GUIアプリケーションを開始")
        logging.info(f"Python バージョン: {sys.version}")
        logging.info(f"作業ディレクトリ: {Path.cwd()}")
        logging.info(f"ファイルシステムエンコーディング: {sys.getfilesystemencoding()}")
        logging.info(f"引数: {sys.argv}")
        logging.info(
            "============================================================")

        # アプリケーション設定
        logging.info("QApplicationの高DPI設定を構成します")
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

        logging.info("QApplicationインスタンスを作成します")
        app = QApplication(sys.argv)
        logging.info("QApplicationインスタンスの作成が完了しました")

        # Unicode対応フォント設定
        try:
            font = QFont("Yu Gothic UI", 9)  # 日本語対応フォント
            if not font.exactMatch():
                font = QFont("Meiryo UI", 9)  # フォールバック
            if not font.exactMatch():
                font = QFont("MS UI Gothic", 9)  # さらなるフォールバック
            app.setFont(font)
        except Exception as e:
            logging.warning(f"フォント設定エラー: {e}")

        # 翻訳設定
        try:
            translator = FluentTranslator(QLocale.Japanese)
            app.installTranslator(translator)
        except Exception as e:
            logging.warning(f"翻訳設定エラー: {e}")

        # モンキーパッチ適用
        try:
            patch_qfluentwidgets()
            logging.info("QFluent モンキーパッチ適用完了")
        except Exception as e:
            logging.warning(f"モンキーパッチ適用エラー: {e}")

        # メインウィンドウとコントローラー初期化
        main_win = MainWindow()

        try:
            controller = AppController(main_window=main_win)

            # 循環依存を解決するための2段階初期化
            main_win.app_controller = controller
            main_win.initialize_views()
            controller.initialize_app()

            logging.info("アプリケーション初期化完了")

            # メインウィンドウを表示
            logging.info("メインウィンドウを表示します")
            main_win.show()

            # アプリケーション実行（メインイベントループ開始）
            logging.info("🎯 QtアプリケーションのメインループCapp.exec())を開始します")
            exit_code = app.exec()
            logging.info(f"Qtアプリケーションが終了しました。終了コード: {exit_code}")
            
            return exit_code

        except UnicodeDecodeError as e:
            error_msg = f"アプリケーション初期化時のUnicodeエラー: {e}"
            logging.error(error_msg)

            # ユーザーにわかりやすいエラーメッセージを表示
            QMessageBox.critical(
                None,
                "Unicode エラー",
                f"日本語を含むパスでUnicodeエラーが発生しました。\n\n"
                f"対処法:\n"
                f"1. アプリケーションを英数字のみのパスに移動\n"
                f"2. または環境変数 PYTHONUTF8=1 を設定\n\n"
                f"詳細: {e}"
            )
            return 1

        except Exception as e:
            logging.error(f"アプリケーション初期化エラー: {e}")

            QMessageBox.critical(
                None,
                "初期化エラー",
                f"アプリケーションの初期化に失敗しました。\n\n詳細: {e}"
            )
            return 1

    except Exception as e:
        error_msg = f"GUIアプリケーション起動時の致命的エラー: {e}"
        logging.exception(error_msg)  # スタックトレースも含めてログに記録
        print(f"❌ {error_msg}")
        
        # 可能であればエラーダイアログも表示
        try:
            # QApplicationは既にインポート済みなので、ローカルインポートは不要
            if not QApplication.instance():
                _ = QApplication(sys.argv)
            QMessageBox.critical(None, "アプリケーション起動エラー", 
                               f"GUIアプリケーションの起動に失敗しました:\n{e}")
        except ImportError:
            print("GUI環境でないため、エラーダイアログを表示できません")
        except Exception as dialog_error:
            logging.warning(f"エラーダイアログの表示に失敗: {dialog_error}")
        
        return 1


def main():
    """
    メインアプリケーション関数（Unicode対応強化）

    従来の互換性を保つためのラッパー関数
    """
    return launch_gui()


if __name__ == "__main__":
    sys.exit(main())
