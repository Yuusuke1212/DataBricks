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
        logging.debug(f"ログレベル: DEBUG")
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


def launch_gui():
    """GUI アプリケーションを起動"""
    import sys
    import traceback  # ★追加★: 詳細トレースバック用
    
    try:
        logging.info("launch_gui()関数を呼び出しました")
        logging.info("launch_gui()関数を開始します")
        logging.info("=" * 60)
        logging.info("JRA-Data Collector GUIアプリケーションを開始")
        logging.info(f"Python バージョン: {sys.version}")
        logging.info(f"作業ディレクトリ: {Path.cwd()}")
        logging.info(f"ファイルシステムエンコーディング: {sys.getfilesystemencoding()}")
        logging.info(f"引数: {sys.argv}")
        logging.info("=" * 60)

        # PySide6 のDPI設定
        logging.info("QApplicationの高DPI設定を構成します")
        os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

        # QApplication インスタンス作成
        logging.info("QApplicationインスタンスを作成します")
        app = QApplication(sys.argv)
        
        logging.info("QApplicationインスタンスの作成が完了しました")

        # モンキーパッチ適用
        try:
            patch_qfluentwidgets()
            logging.info("QFluent モンキーパッチ適用完了")
        except Exception as e:
            logging.warning(f"モンキーパッチ適用エラー: {e}")

        # ★追加★: 詳細デバッグ用の例外ハンドリング
        try:
            # メインウィンドウとコントローラー初期化
            logging.info("メインウィンドウの初期化を開始...")
            main_win = MainWindow()
            logging.info("メインウィンドウの初期化が完了しました")

            logging.info("AppControllerの初期化を開始...")
            controller = AppController(main_window=main_win)
            logging.info("AppControllerの初期化が完了しました")

            main_win.app_controller = controller

            logging.info("ビューの初期化を開始...")
            main_win.initialize_views()
            logging.info("ビューの初期化が完了しました")

            logging.info("アプリケーション初期化を開始...")
            controller.initialize_app()
            logging.info("アプリケーション初期化が完了しました")

            logging.info("メインウィンドウを表示...")
            main_win.show()

            # ★重要★: UI表示後に非同期初期化をトリガー（課題3: 起動速度改善）
            logging.info("バックグラウンド初期化を開始...")
            controller.post_ui_init()
            logging.info("バックグラウンド初期化が完了しました")

        except Exception as init_error:
            # ★追加★: 初期化エラーの詳細ログ出力
            error_traceback = traceback.format_exc()
            logging.error(f"アプリケーション初期化エラー: {init_error}")
            logging.error(f"詳細スタックトレース:\n{error_traceback}")
            
            # ★追加★: エラー箇所の特定情報
            frame = traceback.extract_tb(init_error.__traceback__)[-1]
            logging.error(f"エラー発生ファイル: {frame.filename}")
            logging.error(f"エラー発生行番号: {frame.lineno}")
            logging.error(f"エラー発生関数: {frame.name}")
            logging.error(f"エラー発生コード: {frame.line}")
            
            # ★追加★: エラーの種類別詳細解析
            if "'str' object has no attribute 'value'" in str(init_error):
                logging.error("★ 'str' object has no attribute 'value' エラーを検出!")
                logging.error("このエラーは文字列に対して.valueアクセスしようとした際に発生します")
                logging.error("Enumオブジェクトが期待されている箇所に文字列が渡されている可能性があります")
            
            # コンソールにもエラー出力
            print(f"CRITICAL ERROR: アプリケーション初期化に失敗しました")
            print(f"エラー内容: {init_error}")
            print(f"詳細は以下のログファイルを確認してください:")
            print(f"  {Path.cwd()}/logs/jra_data_collector_{datetime.now().strftime('%Y%m%d')}.log")
            
            # エラーでも一度実行ループを試行
            return sys.exit(app.exec())

        # イベントループ開始
        logging.info("Qtイベントループを開始します")
        sys.exit(app.exec())

    except Exception as e:
        # ★追加★: 最上位レベルの例外ハンドリング
        error_traceback = traceback.format_exc()
        logging.error(f"launch_gui() 全体でエラーが発生しました: {e}")
        logging.error(f"詳細スタックトレース:\n{error_traceback}")
        print(f"FATAL ERROR: {e}")
        print(f"詳細は以下のログファイルを確認してください:")
        print(f"  {Path.cwd()}/logs/jra_data_collector_{datetime.now().strftime('%Y%m%d')}.log")
        return 1  # エラー終了コード

    finally:
        logging.info("launch_gui()から戻りました。")
        
        # ★追加★: デバッグ情報の追加出力
        logging.info("=" * 60)
        logging.info("launch_gui() 実行完了")
        logging.info("=" * 60)


def main():
    """メインエントリーポイント"""
    import sys
    import traceback  # ★追加★: デバッグ用
    
    try:
        # ★追加★: デバッグ用の初期情報
        print(f"🚀 main() function called")
        print(f"Python version: {sys.version}")
        print(f"Working directory: {Path.cwd()}")
        print(f"__file__: {__file__}")
        
        # ログ設定
        print(f"📝 ログ設定を初期化...")
        log_file = setup_logging()
        if log_file:
            print(f"📝 ログファイル: {log_file}")
        
        # ★追加★: より詳細なデバッグ情報
        logging.debug("main() function 開始")
        logging.debug(f"sys.argv: {sys.argv}")
        logging.debug(f"os.getcwd(): {os.getcwd()}")
        logging.debug(f"__name__: {__name__}")
        
        # 管理者権限チェック
        try:
            logging.debug("管理者権限チェックを開始...")
            from .admin_helper import is_admin, run_as_admin
            
            if not is_admin():
                logging.info("🔒 非管理者権限で実行中。昇格を試みます")
                print("🔒 JV-Link COMコンポーネントの適切な動作のため、管理者権限が必要です。")
                print("   UACプロンプトが表示されますので、「はい」を選択してください。")
                
                logging.info("管理者権限昇格を実行します...")
                run_as_admin()
                
                # 通常ここには到達しない（新しいプロセスで再起動される）
                return 42  # UAC成功の場合の特別な終了コード
            
            logging.info("✅ 管理者権限で実行中")
            
        except ImportError as e:
            logging.warning(f"管理者権限ヘルパーのインポートに失敗: {e}")
            print("⚠️  管理者権限チェックをスキップします")
        except Exception as e:
            logging.error(f"管理者権限チェックでエラー: {e}")
            print(f"⚠️  管理者権限チェックエラー: {e}")

        # JV-Link レジストリ設定
        try:
            logging.debug("JV-Link レジストリ設定を開始...")
            from .registry_helper import ensure_com_surrogate_for_jvlink
            ensure_com_surrogate_for_jvlink()
            logging.info("✅ JV-Link DLL サロゲート設定を完了")
            
        except ImportError as e:
            logging.warning(f"レジストリヘルパーのインポートに失敗: {e}")
        except Exception as e:
            logging.error(f"レジストリ設定エラー: {e}")

        # ★追加★: GUI起動前の最終チェック
        logging.debug("GUI起動前の最終チェック...")
        logging.debug("launch_gui() を呼び出します...")
        
        # GUI アプリケーション起動
        return launch_gui()
        
    except KeyboardInterrupt:
        logging.info("⚠️ ユーザーによる中断")
        print("\n⚠️ ユーザーによる中断（Ctrl+C）")
        return 1
        
    except Exception as e:
        # ★追加★: main()でのエラーハンドリング
        error_traceback = traceback.format_exc()
        logging.error(f"main()でエラーが発生しました: {e}")
        logging.error(f"詳細スタックトレース:\n{error_traceback}")
        
        # ★追加★: エラー種別の詳細解析
        if "'str' object has no attribute 'value'" in str(e):
            logging.error("★ main()で 'str' object has no attribute 'value' エラーを検出!")
            logging.error("このエラーはEnumアクセスの型不整合が原因です")
            
            # スタックトレースからエラー箇所を特定
            if hasattr(e, '__traceback__') and e.__traceback__:
                frame = traceback.extract_tb(e.__traceback__)[-1]
                logging.error(f"エラー発生ファイル: {frame.filename}")
                logging.error(f"エラー発生行番号: {frame.lineno}")
                logging.error(f"エラー発生関数: {frame.name}")
                logging.error(f"エラー発生コード: {frame.line}")
        
        print(f"❌ CRITICAL ERROR in main(): {e}")
        print(f"詳細はログファイルを確認してください")
        return 1
        
    finally:
        logging.debug("main() function 完了")
        print("🏁 main() function completed")


if __name__ == "__main__":
    sys.exit(main())
