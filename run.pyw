#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JRA-Data Collector Application Entry Point

64bit Python環境で32bit JV-Link COMコンポーネントを使用するための
管理者権限チェックとDLLサロゲート設定を含む日本語パス対応エントリーポイント
"""

import sys
import os
import locale
import logging
from pathlib import Path
from datetime import datetime

# === STEP 1: 最優先でのロギング初期化 ===
def setup_early_logging():
    """
    アプリケーション起動時の最初期段階でのロギング設定
    管理者権限チェックやUAC表示の段階からログが記録される
    """
    try:
        # ログディレクトリの作成
        log_dir = Path.cwd() / "logs"
        log_dir.mkdir(exist_ok=True)
        
        # ログファイル名（日付付き）
        log_filename = f"jra_data_collector_{datetime.now().strftime('%Y%m%d')}.log"
        log_filepath = log_dir / log_filename

        # ログ設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
            handlers=[
                logging.FileHandler(str(log_filepath), encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ],
            force=True  # 既存のロガー設定を上書き
        )

        # 初期化完了ログ
        logging.info("=" * 60)
        logging.info("🚀 JRA-Data Collector アプリケーション起動")
        logging.info(f"📝 ログファイル: {log_filepath}")
        logging.info(f"🖥️  Python バージョン: {sys.version}")
        logging.info(f"📂 作業ディレクトリ: {Path.cwd()}")
        logging.info("=" * 60)
        
        print(f"📝 ログファイル初期化: {log_filepath}")
        
    except Exception as e:
        # ロギング設定に失敗した場合もアプリケーションは継続
        print(f"⚠️  ログ設定エラー: {e}")
        print("   基本的なログ設定で継続します...")
        logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

# 最優先でロギングを初期化
setup_early_logging()

def run_main_application():
    """
    メインアプリケーションの初期化と起動をカプセル化する関数。
    この関数は必ず管理者権限で実行される。
    """
    try:
        logging.info("管理者権限で実行中。アプリケーションを初期化します。")
        print("🎯 管理者権限でアプリケーションを初期化中...")
        
        # Unicode環境設定
        try:
            setup_unicode_environment()
            logging.info("Unicode環境設定が完了しました")
        except Exception as e:
            logging.warning(f"Unicode環境設定エラー: {e}")
        
        # 64bit環境向けのレジストリ設定を自動構成
        try:
            from src.admin_helper import get_python_architecture
            
            python_arch = get_python_architecture()
            logging.info(f"🔍 Python アーキテクチャ: {python_arch}")
            
            if python_arch == '64bit':
                logging.info("🔧 64bit Python環境を検出。JV-LinkのCOMサロゲート設定を確認・構成します...")
                print("🔧 JV-Link COMサロゲート設定を実行中...")
                
                from src.registry_helper import ensure_com_surrogate_for_jvlink
                ensure_com_surrogate_for_jvlink()
                
                logging.info("✅ レジストリ設定が完了しました。")
                print("✅ レジストリ設定完了")
            else:
                logging.info("32bit Python環境のため、DLLサロゲート設定は不要です")
                
        except ImportError as reg_error:
            logging.warning(f"レジストリヘルパーのインポートエラー: {reg_error}")
            print("⚠️  レジストリ設定をスキップします")
        except Exception as reg_error:
            logging.warning(f"レジストリ設定エラー: {reg_error}")
            print("⚠️  レジストリ設定でエラーが発生しましたが、アプリケーションは継続します")

        # --- ★最重要★ メインアプリケーションのGUIを起動 ---
        logging.info("🚀 メインGUIアプリケーションを起動します...")
        print("🚀 GUIアプリケーションを起動中...")
        
        # src/main.py に定義されたGUI起動関数を呼び出す
        from src.main import launch_gui
        
        logging.info("launch_gui()関数を呼び出します")
        exit_code = launch_gui()
        
        logging.info(f"launch_gui()から戻りました。終了コード: {exit_code}")
        return exit_code

    except ImportError as import_error:
        error_msg = f"重要なモジュールのインポートに失敗しました: {import_error}"
        logging.error(error_msg)
        print(f"❌ {error_msg}")
        
        # GUIツールキットが利用可能であれば、メッセージボックスを表示
        try:
            from PySide6.QtWidgets import QApplication as QApp, QMessageBox
            # QApplicationインスタンスがなければ作成
            if not QApp.instance():
                _ = QApp(sys.argv)
            QMessageBox.critical(None, "モジュールエラー", f"必要なモジュールの読み込みに失敗しました:\n{import_error}")
        except ImportError:
            # GUIが利用できない場合はコンソールに出力
            print("CRITICAL: 必要なモジュールの読み込みに失敗しました。")
        
        return 1
        
    except Exception as critical_error:
        # 予期せぬエラーをログに記録し、ユーザーに通知する
        error_msg = f"アプリケーションの実行中に致命的なエラーが発生しました: {critical_error}"
        logging.exception(error_msg)
        print(f"❌ {error_msg}")
        
        # GUIツールキットが利用可能であれば、メッセージボックスを表示
        try:
            from PySide6.QtWidgets import QApplication as QApp, QMessageBox
            # QApplicationインスタンスがなければ作成
            if not QApp.instance():
                _ = QApp(sys.argv)
            QMessageBox.critical(None, "致命的なエラー", "アプリケーションの起動に失敗しました。\n詳細はログファイルを確認してください。")
        except ImportError:
            # GUIが利用できない場合はコンソールに出力
            print("CRITICAL: アプリケーションの起動に失敗しました。詳細はログファイルを確認してください。")
        
        return 1

def setup_unicode_environment():
    """
    日本語パス対応のためのUnicode環境設定
    """
    # Python UTF-8 モードを有効化
    os.environ['PYTHONUTF8'] = '1'
    os.environ['PYTHONIOENCODING'] = 'utf-8'

    # Windows固有の設定
    if sys.platform == 'win32':
        # Windows Console UTF-8対応
        try:
            # コンソールのコードページをUTF-8に設定
            import subprocess
            subprocess.run(['chcp', '65001'], shell=True, capture_output=True)
        except Exception:
            pass  # エラーが発生しても継続

        # Windows localeの設定
        try:
            locale.setlocale(locale.LC_ALL, '')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_ALL, 'Japanese_Japan.UTF-8')
            except locale.Error:
                pass  # デフォルトのまま継続

    # ファイルシステムエンコーディングの確認
    fs_encoding = sys.getfilesystemencoding()
    logging.info(f"ファイルシステムエンコーディング: {fs_encoding}")

    # 標準入出力のエンコーディング確認
    stdout_encoding = sys.stdout.encoding
    logging.info(f"標準出力エンコーディング: {stdout_encoding}")

if __name__ == "__main__":
    logging.info("🚀 JRA-Data Collector エントリーポイント開始")
    print("🚀 JRA-Data Collector を起動しています...")

    try:
        # 管理者権限ヘルパーをインポート
        from src.admin_helper import is_admin, run_as_admin, get_elevation_status

        if is_admin():
            # === 管理者権限で実行されている場合 ===
            # メインアプリケーションのロジックを直接実行
            logging.info("🔐 管理者権限で実行中です")
            print("🔐 管理者権限で実行されています。")

            # 実行環境の詳細表示
            try:
                elevation_status = get_elevation_status()
                arch = elevation_status.get('python_architecture', 'Unknown')
                pid = elevation_status.get('process_id', 'Unknown')
                logging.info(f"📊 実行環境: {arch} Python, PID: {pid}")
                print(f"📊 実行環境: {arch} Python, プロセスID: {pid}")
            except Exception as e:
                logging.warning(f"実行環境取得エラー: {e}")
                print(f"⚠️  実行環境取得エラー: {e}")

            # メインアプリケーションを実行
            logging.info("メインアプリケーション関数を呼び出します")
            exit_code = run_main_application()
            logging.info(f"アプリケーション終了（終了コード: {exit_code}）")
            
            # 明示的に終了コードで終了
            sys.exit(exit_code)

        else:
            # === 非管理者権限で実行されている場合 ===
            # UACプロンプトを表示して自己昇格を試みる
            logging.info("🔒 非管理者権限で実行中。昇格を試みます")
            print("🔒 JV-Link COMコンポーネントの適切な動作のため、管理者権限が必要です。")
            print("   UACプロンプトが表示されますので、「はい」を選択してください。")
            print()

            # 管理者権限で自己再起動（現在のプロセスは終了される）
            logging.info("管理者権限昇格を実行します...")
            run_as_admin()  # この関数は管理者権限でスクリプトを再起動する
            
            # 通常、run_as_admin()は戻ってこないが、念のため
            logging.warning("run_as_admin()から制御が戻りました。昇格が失敗した可能性があります")
            print("⚠️  管理者権限昇格に失敗した可能性があります")
            sys.exit(1)  # 元の非管理者プロセスはここで完全に終了する

    except ImportError as import_error:
        error_msg = f"管理者権限ヘルパーの読み込みに失敗: {import_error}"
        logging.error(error_msg)
        print(f"❌ {error_msg}")
        print("   管理者権限なしで継続しますが、JV-Link機能に制限が生じる可能性があります。")

        # フォールバック: 管理者権限なしでアプリケーションを実行
        try:
            logging.info("フォールバック実行: 管理者権限なしでアプリケーションを起動")
            exit_code = run_main_application()
            sys.exit(exit_code)
        except Exception as fallback_err:
            fallback_error_msg = f"フォールバック実行も失敗しました: {fallback_err}"
            logging.critical(fallback_error_msg)
            print(f"❌ {fallback_error_msg}")
            input("Enterキーを押して終了...")
            sys.exit(1)

    except Exception as critical_error:
        critical_error_msg = f"アプリケーション起動で予期しないエラー: {critical_error}"
        logging.critical(critical_error_msg)
        print(f"❌ {critical_error_msg}")
        print("   予期しないエラーが発生しました。")
        input("Enterキーを押して終了...")
        sys.exit(1)
