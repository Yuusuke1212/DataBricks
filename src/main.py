#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JRA-Data Collector メインアプリケーション

日本語パス対応とUnicode例外処理を含む
"""

from .controllers.app_controller import AppController
from .views.main_window import MainWindow
from PySide6.QtWidgets import QApplication
import sys
import os
import logging
import types
from pathlib import Path
import traceback
from datetime import datetime
import platform

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

def setup_logging():
    """ログ設定"""
    try:
        # ログディレクトリの作成
        log_dir = Path(__file__).parent.parent / "logs"
        log_dir.mkdir(exist_ok=True)

        # ログファイル名（日付付き）
        today = datetime.now().strftime('%Y%m%d')
        log_file = log_dir / f"jra_data_collector_{today}.log"

        # ★修正★: デバッグモードでログレベルをDEBUGに設定
        logging.basicConfig(
            level=logging.DEBUG,  # INFOからDEBUGに変更
            format='%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s',  # 行番号も追加
            handlers=[
                logging.FileHandler(str(log_file), encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True
        )

        # ★追加★: デバッグ用の追加情報
        logging.debug("=" * 80)
        logging.debug("DEBUG MODE ENABLED - 詳細デバッグ情報を出力します")
        logging.debug("=" * 80)
        logging.debug(f"ログファイル: {log_file}")
        logging.debug("ログレベル: DEBUG")
        logging.debug(f"Python実行可能ファイル: {sys.executable}")
        logging.debug(f"Pythonパス: {sys.path}")
        logging.debug(f"環境変数 PYTHONPATH: {os.environ.get('PYTHONPATH', 'Not set')}")
        logging.debug(f"プラットフォーム: {sys.platform}")
        logging.debug(f"アーキテクチャ: {platform.architecture()}")
        logging.debug("=" * 80)

        return log_file

    except Exception as e:
        # ログ設定に失敗した場合の基本設定
        print(f"ログ設定エラー: {e}")
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s'
        )
        return None


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


def launch_gui(is_admin):
    """GUIアプリケーションを起動する"""
    try:
        logging.info("GUIの起動を開始します...")
        if not is_admin:
            logging.warning("非管理者権限です。一部機能が制限される可能性があります。")

        logging.info("QApplicationインスタンスを作成します")
        app = QApplication(sys.argv)
        logging.info("QApplicationインスタンスの作成が完了しました")

        main_win = None
        controller = None

        try:
            logging.info("メインウィンドウの初期化を開始...")
            main_win = MainWindow()
            logging.info("メインウィンドウの初期化が完了しました")

            logging.info("AppControllerの初期化を開始...")
            controller = AppController(main_win)
            logging.info("AppControllerの初期化が完了しました")

            logging.info("メインウィンドウを表示します...")
            main_win.show()
            logging.info("メインウィンドウの表示が完了しました")

            logging.info("アプリケーションのイベントループを開始します...")
            exit_code = app.exec()
            logging.info(f"アプリケーションのイベントループが終了しました。終了コード: {exit_code}")
            return exit_code

        except Exception as init_error:
            logging.critical("アプリケーションの初期化中に致命的なエラーが発生しました", exc_info=True)
            error_traceback = traceback.format_exc()
            logging.error(f"初期化エラー: {init_error}")
            logging.error(f"詳細スタックトレース:\n{error_traceback}")

            # エラー箇所の特定情報
            frame = traceback.extract_tb(init_error.__traceback__)[-1]
            logging.error(f"エラー発生ファイル: {frame.filename}")
            logging.error(f"エラー発生行: {frame.lineno}")
            logging.error(f"エラー発生関数: {frame.name}")
            logging.error(f"エラー発生コード: {frame.line}")

            # コンソールにもエラー出力
            print("CRITICAL ERROR: アプリケーション初期化に失敗しました")
            print(f"エラー: {init_error}")
            log_file_path = Path.cwd() / "logs" / f"jra_data_collector_{datetime.now().strftime('%Y%m%d')}.log"
            print("詳細は以下のログファイルを確認してください:")
            print(f"  {log_file_path}")

            # エラーが発生しても、appインスタンスがあればイベントループを実行
            if 'app' in locals() and isinstance(app, QApplication):
                return sys.exit(app.exec())
            return 1

    except Exception as e:
        # 最上位レベルの例外ハンドリング
        error_traceback = traceback.format_exc()
        logging.error(f"launch_gui() 全体で予期せぬエラーが発生しました: {e}")
        logging.error(f"詳細スタックトレース:\n{error_traceback}")
        print(f"FATAL ERROR: {e}")
        return 1  # エラー終了コード

    finally:
        logging.info("launch_gui()から戻りました。")
        # デバッグ情報の追加出力
        if 'controller' in locals() and controller:
            logging.debug(f"コントローラーの状態: {controller.jvlink_manager.current_state}")
        if 'main_win' in locals() and main_win:
            logging.debug(f"メインウィンドウは表示されていましたか？ {'はい' if main_win.isVisible() else 'いいえ'}")
        logging.debug("アプリケーションを完全に終了します。")


def main():
    """アプリケーションのエントリポイント"""
    log_file = None
    try:
        # ログ設定を初期化
        # この時点でデバッグモードが有効かどうかが決まる
        log_file = setup_logging()

        # 管理者権限チェック
        is_admin = check_admin_privileges()

        if not is_admin:
            # 管理者権限で再起動を試みる
            if relaunch_as_admin():
                # 再起動が開始されたので、現在のプロセスは終了
                return 0
            else:
                # ユーザーがUACをキャンセルした場合など
                logging.warning("管理者権限での再起動ができませんでした。")
                # GUIは起動せず終了
                return 1

        # is_adminがTrueの場合のみGUIを起動
        # GUI アプリケーション起動
        return launch_gui(is_admin=True)

    except KeyboardInterrupt:
        logging.info("CTRL+C が検出されました。アプリケーションを終了します。")
        print("\nアプリケーションを終了します。")
        return 0
    except Exception as e:
        # main関数レベルでの最終的な例外キャッチ
        logging.critical("main() で予期せぬクリティカルエラーが発生しました。", exc_info=True)
        print(f"FATAL ERROR in main(): {e}")
        if log_file:
            print(f"詳細はログファイルを参照してください: {log_file}")
        return 1
    finally:
        logging.info("🏁 main() function completed")
        print("🏁 main() function completed")


if __name__ == "__main__":
    sys.exit(main())
