"""
Admin Helper Module for DataBriocks

64bit Python環境で32bit JV-Link COMコンポーネントを使用するために、
管理者権限での実行とDLLサロゲート設定を自動化するモジュール。

エラーコード REGDB_E_CLASSNOTREG (-2147221164) の解決を目的とする。
"""

import ctypes
import sys
import os
import logging
from typing import Optional


def is_admin() -> bool:
    """
    現在のプロセスが管理者権限で実行されているかを確認

    Returns:
        bool: 管理者権限で実行されている場合True
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except AttributeError:
        # Windowsでない場合（開発環境等）
        return True
    except Exception as e:
        logging.warning(f"管理者権限確認エラー: {e}")
        return False


def request_admin_privileges() -> None:
    """
    管理者権限を要求してアプリケーションを再起動

    UACプロンプトを表示し、ユーザーが許可すると管理者権限で再起動される。
    現在のプロセスは即座に終了する。
    
    参考実装: https://gist.github.com/leixingyu/a2cc64cec76638d2367cd4c2fc1b94ec
    """
    try:
        # 現在のスクリプトのパスを取得
        script_path = os.path.abspath(sys.argv[0])

        # 引数の処理（参考実装に基づく改善版）
        if len(sys.argv) > 1:
            # 引数がある場合は適切にエスケープ
            args = []
            for arg in sys.argv[1:]:
                if ' ' in arg:
                    args.append(f'"{arg}"')
                else:
                    args.append(arg)
            params = ' '.join(args)
        else:
            params = ''

        logging.info("管理者権限を要求しています...")
        logging.info(f"Python実行ファイル: {sys.executable}")
        logging.info(f"スクリプトパス: {script_path}")
        logging.info(f"引数: {params}")

        # パラメータ文字列を構築（参考実装に基づく改良版）
        if params:
            command_params = f'"{script_path}" {params}'
        else:
            command_params = f'"{script_path}"'

        logging.info(f"実行コマンド: {sys.executable} {command_params}")

        # ShellExecuteWでrunas動詞を使用して管理者権限で再起動
        # https://docs.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew
        result = ctypes.windll.shell32.ShellExecuteW(
            None,                    # hwnd (親ウィンドウハンドル)
            "runas",                 # lpVerb (管理者として実行)
            sys.executable,          # lpFile (Python実行ファイル)
            command_params,          # lpParameters (スクリプトパス + 引数)
            None,                    # lpDirectory (作業ディレクトリ)
            1                        # nShowCmd (SW_SHOWNORMAL)
        )

        # 結果の確認（ShellExecuteWは成功時に32より大きい値を返す）
        if result <= 32:
            # ShellExecuteWのエラーコード（https://docs.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-shellexecutew）
            error_messages = {
                0: "システムのメモリまたはリソースが不足しています",
                2: "指定されたファイルが見つかりませんでした",
                3: "指定されたパスが見つかりませんでした",
                5: "オペレーティングシステムがファイルへのアクセスを拒否しました",
                8: "システムのメモリが不足してファイルを開けませんでした",
                26: "共有違反が発生しました",
                27: "ファイル名の関連付けが不完全または無効です",
                28: "DDE トランザクションがタイムアウトしました",
                29: "DDE トランザクションが失敗しました",
                30: "DDE トランザクションがビジー状態のため完了できませんでした",
                31: "指定された関数はサポートされていません"
            }
            error_msg = error_messages.get(result, f"不明なエラー (コード: {result})")
            
            # 特別なケース：ユーザーがUACをキャンセルした場合（通常はエラーコード5）
            if result == 5:
                logging.warning("ユーザーがUACプロンプトをキャンセルしました")
                print("⚠️  UACプロンプトがキャンセルされました。")
                print("   管理者権限が必要です。アプリケーションを手動で管理者として実行してください。")
            else:
                logging.error(f"管理者権限での再起動に失敗: {error_msg}")
                print(f"❌ 管理者権限での再起動に失敗: {error_msg}")
                print("   手動で管理者権限でアプリケーションを起動してください。")
            
            input("Enterキーを押して終了...")
            sys.exit(1)
        else:
            # 成功時
            logging.info(f"管理者権限での再起動を開始しました（結果コード: {result}）")
            logging.info("現在のプロセスを終了します")
            
            # 少し待機してから終了（新しいプロセスの起動を待つ）
            import time
            time.sleep(0.5)

    except Exception as e:
        logging.error(f"管理者権限要求中に予期しないエラー: {e}")
        print(f"\n❌ 管理者権限要求エラー: {e}")
        print("手動で管理者権限でアプリケーションを起動してください。")
        input("Enterキーを押して終了...")
        sys.exit(1)

    # 現在のプロセスを終了
    sys.exit(0)


def ensure_admin_privileges() -> None:
    """
    管理者権限の確保を保証する

    管理者権限で実行されていない場合、自動的に昇格を試行する。
    この関数はアプリケーションのエントリーポイントで最初に呼び出すべき。
    """
    if not is_admin():
        print("🔒 JV-Link COMコンポーネントの適切な動作のため、管理者権限が必要です。")
        print("    UACプロンプトが表示されますので、「はい」を選択してください。")
        print("    これにより64bit Python環境での32bit JV-Link呼び出しが可能になります。")
        print()
        request_admin_privileges()
    else:
        logging.info("✅ 管理者権限で実行されています。")


def run_as_admin() -> None:
    """
    管理者権限でアプリケーションを再起動

    現在のプロセスを管理者権限で再起動し、現在のプロセスは終了します。
    この関数は、非管理者権限プロセスからのみ呼び出されるべきです。
    """
    request_admin_privileges()


def get_python_architecture() -> str:
    """
    現在のPythonインタープリタのアーキテクチャを取得

    Returns:
        str: "32bit" または "64bit"
    """
    return "64bit" if sys.maxsize > 2**32 else "32bit"


def get_elevation_status() -> dict:
    """
    現在の昇格状態の詳細情報を取得

    Returns:
        dict: 昇格状態の詳細情報
    """
    try:
        is_elevated = is_admin()

        # Pythonのアーキテクチャ情報
        python_arch = "64bit" if sys.maxsize > 2**32 else "32bit"

        # プロセス情報
        process_info = {
            "is_admin": is_elevated,
            "python_architecture": python_arch,
            "python_executable": sys.executable,
            "process_id": os.getpid(),
            "script_path": os.path.abspath(sys.argv[0]),
            "working_directory": os.getcwd()
        }

        return process_info

    except Exception as e:
        logging.error(f"昇格状態取得エラー: {e}")
        return {"error": str(e)}


if __name__ == "__main__":
    # テスト実行
    print("=== Admin Helper Test ===")

    # 現在の状態を詳細表示
    status = get_elevation_status()
    print("\n📊 現在の実行環境:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    # 管理者権限の判定
    admin_status = is_admin()
    print(f"\n🔐 管理者権限ステータス: {'✅ はい' if admin_status else '❌ いいえ'}")

    if not admin_status:
        print("\n⚠️  管理者権限が必要です。")
        print("📝 実際の運用では、UACプロンプトで「はい」を選択すると管理者権限で再起動されます。")
        print("🧪 テスト環境のため、昇格は実行しません。")

        # テスト環境ではensure_admin_privileges()を呼び出さない
        # ensure_admin_privileges()
    else:
        print("\n✅ 既に管理者権限で実行されています。")
        print("🎯 JV-Linkのレジストリ設定が安全に実行できる状態です。")
