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

# 日本語パス対応: 環境変数とエンコーディング設定


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
    print(f"ファイルシステムエンコーディング: {fs_encoding}")

    # 標準入出力のエンコーディング確認
    stdout_encoding = sys.stdout.encoding
    print(f"標準出力エンコーディング: {stdout_encoding}")


def setup_jvlink_architecture_compatibility():
    """
    64bit Python環境で32bit JV-Link COMコンポーネントを使用するための設定

    DLLサロゲート機能を有効化して、アーキテクチャの不一致問題を解決する
    """
    try:
        # admin_helperを動的インポート（管理者権限確保後）
        from src.admin_helper import get_python_architecture

        # Pythonアーキテクチャの確認
        python_arch = get_python_architecture()
        print(f"🔍 Python アーキテクチャ: {python_arch}")

        if python_arch == "64bit":
            print("📋 64bit Python環境でのJV-Link COMコンポーネント使用のため、DLLサロゲート設定を実行します...")

            # レジストリヘルパーを動的インポート
            from src.registry_helper import ensure_com_surrogate_for_jvlink, get_jvlink_registry_status

            # 現在の設定状況を確認
            print("📊 現在のJV-Linkレジストリ設定を確認中...")
            status = get_jvlink_registry_status()

            if status.get("configuration_complete", False):
                print("✅ DLLサロゲート設定は既に完了しています。")
            else:
                print("⚙️  DLLサロゲート設定を実行中...")
                success = ensure_com_surrogate_for_jvlink()
                if success:
                    print("✅ DLLサロゲート設定が正常に完了しました。")
                    print("   64bit Python環境からの32bit JV-Link呼び出しが可能になりました。")
                else:
                    print("❌ DLLサロゲート設定に失敗しました。")
        else:
            print("✅ 32bit Python環境のため、DLLサロゲート設定は不要です。")

    except ImportError as e:
        print(f"⚠️  ヘルパーモジュールの読み込みに失敗: {e}")
        print("   JV-Link機能に影響する可能性があります。")
    except Exception as e:
        print(f"⚠️  JV-Linkアーキテクチャ互換性設定エラー: {e}")
        print("   JV-Link機能に影響する可能性がありますが、アプリケーションは継続します。")


def run_application():
    """
    メインアプリケーションの実行をカプセル化する関数

    管理者権限で実行されることを前提とした、アプリケーションのメイン処理
    """
    try:
        print("🎯 管理者権限でアプリケーションを起動します...")

        # Unicode環境設定
        setup_unicode_environment()

        # 64bit環境向けのJV-Link設定を自動構成
        setup_jvlink_architecture_compatibility()

        print("🚀 メインGUIアプリケーションを起動します...")

        # メインアプリケーションのGUIを起動
        from src.main import launch_gui
        return launch_gui()

    except ImportError as e:
        error_msg = f"モジュールのインポートに失敗しました: {e}"
        print(f"❌ {error_msg}")
        logging.error(error_msg)
        return 1

    except Exception as e:
        # 予期せぬエラーをログに記録し、ユーザーに通知する
        error_msg = f"アプリケーションの実行中に致命的なエラーが発生しました: {e}"
        print(f"❌ {error_msg}")

        # エラーログファイルに記録
        try:
            import logging
            logging.basicConfig(
                filename='error.log',
                level=logging.ERROR,
                format='%(asctime)s [%(levelname)s] %(message)s',
                encoding='utf-8'
            )
            logging.exception(error_msg)
            print(f"📝 詳細なエラー情報が error.log に記録されました。")
        except Exception as log_err:
            print(f"⚠️  エラーログの記録にも失敗しました: {log_err}")

        return 1


if __name__ == "__main__":
    print("🚀 JRA-Data Collector を起動しています...")

    try:
        # 管理者権限ヘルパーをインポート
        from src.admin_helper import is_admin, run_as_admin, get_elevation_status

        if is_admin():
            # --- 管理者権限で実行されている場合 ---
            print("🔐 管理者権限で実行されています。")

            # 実行環境の詳細表示
            try:
                elevation_status = get_elevation_status()
                print(
                    f"📊 実行環境: {elevation_status.get('python_architecture', 'Unknown')} Python")
                print(
                    f"   プロセスID: {elevation_status.get('process_id', 'Unknown')}")
            except Exception as e:
                print(f"⚠️  実行環境取得エラー: {e}")

            # メインアプリケーションを実行
            exit_code = run_application()
            sys.exit(exit_code)

        else:
            # --- 非管理者権限で実行されている場合 ---
            print("🔒 JV-Link COMコンポーネントの適切な動作のため、管理者権限が必要です。")
            print("   UACプロンプトが表示されますので、「はい」を選択してください。")
            print("   これにより64bit Python環境での32bit JV-Link呼び出しが可能になります。")
            print()

            # 管理者権限で自己再起動（現在のプロセスは終了される）
            run_as_admin()

    except ImportError as e:
        print(f"⚠️  管理者権限ヘルパーの読み込みに失敗: {e}")
        print("   管理者権限なしで継続しますが、JV-Link機能に制限が生じる可能性があります。")

        # フォールバック: 管理者権限なしでアプリケーションを実行
        try:
            exit_code = run_application()
            sys.exit(exit_code)
        except Exception as fallback_err:
            print(f"❌ フォールバック実行も失敗しました: {fallback_err}")
            input("Enterキーを押して終了...")
            sys.exit(1)

    except Exception as e:
        print(f"❌ アプリケーション起動エラー: {e}")
        print("   予期しないエラーが発生しました。")
        input("Enterキーを押して終了...")
        sys.exit(1)
