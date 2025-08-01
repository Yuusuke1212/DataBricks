"""
Registry Helper Module for DataBriocks

64bit Python環境で32bit JV-Link COMコンポーネントを使用するために、
WindowsのDLLサロゲート機能を有効化するレジストリ設定を自動化するモジュール。

参考文献: 
- Microsoft Docs: COM Surrogate Process (dllhost.exe)
- Windows Registry for COM Components and DLL Surrogate configuration
"""

import winreg
import logging
import sys
from typing import Optional, Tuple, Dict, Any


class RegistryConfigurationError(Exception):
    """レジストリ設定関連のエラー"""
    pass


def get_registry_access_flags() -> Dict[str, int]:
    """
    現在のPython環境に応じた適切なレジストリアクセスフラグを取得

    参考: https://bugs.python.org/msg100396
    32bit apps can query 64bit registry using KEY_WOW64_64KEY (0x0100)
    64bit apps can read/write 32bit registry using KEY_WOW64_32KEY

    Returns:
        Dict[str, int]: レジストリアクセス用のフラグ辞書
    """
    python_arch = "64bit" if sys.maxsize > 2**32 else "32bit"

    # KEY_WOW64_64KEY = 0x0100  # 64bitレジストリビューにアクセス
    # KEY_WOW64_32KEY = 0x0200  # 32bitレジストリビューにアクセス (Wow6432Node)

    flags = {
        "standard": winreg.KEY_READ,
        "write": winreg.KEY_WRITE,
        "64bit_view": winreg.KEY_READ | 0x0100,  # KEY_WOW64_64KEY
        "32bit_view": winreg.KEY_READ | 0x0200,  # KEY_WOW64_32KEY
        "write_64bit": winreg.KEY_WRITE | 0x0100,
        "write_32bit": winreg.KEY_WRITE | 0x0200
    }

    logging.info(f"Python アーキテクチャ: {python_arch}")

    if python_arch == "64bit":
        # 64bit Python環境では、32bit COMコンポーネント用に32bitビューを優先的に使用
        flags["preferred_read"] = flags["32bit_view"]
        flags["preferred_write"] = flags["write_32bit"]
        logging.info("64bit Python環境: 32bitレジストリビュー（Wow6432Node）を優先使用")
    else:
        # 32bit Python環境では標準的なアクセスを使用
        flags["preferred_read"] = flags["standard"]
        flags["preferred_write"] = flags["write"]
        logging.info("32bit Python環境: 標準レジストリアクセスを使用")

    return flags


def get_progid_clsid(progid: str) -> Optional[str]:
    """
    ProgIDからCLSIDを取得（64bit/32bit対応強化版）

    Args:
        progid: プログラムID（例: "JVDTLab.JVLink"）

    Returns:
        Optional[str]: CLSID文字列、見つからない場合はNone
    """
    flags = get_registry_access_flags()

    # 複数のレジストリビューで試行（優先順位付き）
    access_attempts = [
        ("preferred", flags["preferred_read"]),
        ("standard", flags["standard"]),
        ("64bit_view", flags["64bit_view"]),
        ("32bit_view", flags["32bit_view"])
    ]

    for view_name, access_flag in access_attempts:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"{progid}\\CLSID", 0, access_flag) as key:
                clsid, _ = winreg.QueryValueEx(key, "")
                logging.info(
                    f"ProgID '{progid}' のCLSID: {clsid} ({view_name} レジストリビューで発見)")
                return clsid
        except FileNotFoundError:
            logging.debug(f"ProgID '{progid}' が {view_name} レジストリビューで見つかりません")
            continue
        except Exception as e:
            logging.debug(f"ProgID->CLSID変換エラー ({view_name}): {e}")
            continue

    logging.warning(f"ProgID '{progid}' が全てのレジストリビューで見つかりません")
    return None


def check_clsid_exists(clsid: str) -> bool:
    """
    CLSIDがレジストリに登録されているかを確認（64bit/32bit対応強化版）

    Args:
        clsid: クラスID

    Returns:
        bool: 登録されている場合True
    """
    flags = get_registry_access_flags()

    # 複数のレジストリビューで確認
    access_attempts = [
        ("preferred", flags["preferred_read"]),
        ("standard", flags["standard"]),
        ("64bit_view", flags["64bit_view"]),
        ("32bit_view", flags["32bit_view"])
    ]

    for view_name, access_flag in access_attempts:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}", 0, access_flag) as key:
                logging.info(
                    f"CLSID '{clsid}' は {view_name} レジストリビューに登録されています")
                return True
        except FileNotFoundError:
            logging.debug(f"CLSID '{clsid}' が {view_name} レジストリビューで見つかりません")
            continue
        except Exception as e:
            logging.debug(f"CLSID存在確認エラー ({view_name}): {e}")
            continue

    logging.warning(f"CLSID '{clsid}' が全てのレジストリビューで見つかりません")
    return False


def get_appid_from_clsid(clsid: str) -> Optional[str]:
    """
    CLSIDからAppIDを取得（64bit/32bit対応強化版）

    Args:
        clsid: クラスID

    Returns:
        Optional[str]: AppID、見つからない場合はNone
    """
    flags = get_registry_access_flags()

    access_attempts = [
        ("preferred", flags["preferred_read"]),
        ("standard", flags["standard"]),
        ("32bit_view", flags["32bit_view"]),
        ("64bit_view", flags["64bit_view"])
    ]

    for view_name, access_flag in access_attempts:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}", 0, access_flag) as key:
                appid, _ = winreg.QueryValueEx(key, "AppID")
                logging.info(
                    f"CLSID '{clsid}' のAppID: {appid} ({view_name} レジストリビューで発見)")
                return appid
        except FileNotFoundError:
            logging.debug(f"CLSID '{clsid}' にAppIDが設定されていません ({view_name})")
            continue
        except Exception as e:
            logging.debug(f"AppID取得エラー ({view_name}): {e}")
            continue

    logging.info(f"CLSID '{clsid}' にAppIDが設定されていません（全ビュー確認済み）")
    return None


def set_appid_for_clsid(clsid: str, appid: str) -> bool:
    """
    CLSIDにAppIDを設定（64bit/32bit対応強化版）

    Args:
        clsid: クラスID
        appid: アプリケーションID

    Returns:
        bool: 設定成功の場合True
    """
    flags = get_registry_access_flags()

    # 書き込み用のアクセスフラグで試行
    write_attempts = [
        ("preferred", flags["preferred_write"]),
        ("write_32bit", flags["write_32bit"]),
        ("standard", flags["write"]),
        ("write_64bit", flags["write_64bit"])
    ]

    for view_name, write_flag in write_attempts:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"CLSID\\{clsid}", 0, write_flag) as key:
                winreg.SetValueEx(key, "AppID", 0, winreg.REG_SZ, appid)
                logging.info(
                    f"CLSID '{clsid}' にAppID '{appid}' を設定しました ({view_name})")
                return True
        except PermissionError:
            logging.debug(f"AppID設定: 管理者権限が不足しています ({view_name})")
            continue
        except FileNotFoundError:
            logging.debug(f"CLSID '{clsid}' が見つかりません ({view_name})")
            continue
        except Exception as e:
            logging.debug(f"AppID設定エラー ({view_name}): {e}")
            continue

    logging.error(f"CLSID '{clsid}' へのAppID設定が全てのレジストリビューで失敗しました")
    return False


def check_dll_surrogate_enabled(appid: str) -> bool:
    """
    AppIDのDLLサロゲートが有効化されているかを確認（64bit/32bit対応強化版）

    Args:
        appid: アプリケーションID

    Returns:
        bool: DLLサロゲートが有効の場合True
    """
    flags = get_registry_access_flags()

    access_attempts = [
        ("preferred", flags["preferred_read"]),
        ("32bit_view", flags["32bit_view"]),
        ("standard", flags["standard"]),
        ("64bit_view", flags["64bit_view"])
    ]

    for view_name, access_flag in access_attempts:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"AppID\\{appid}", 0, access_flag) as key:
                try:
                    # DllSurrogateキーの存在確認（値は空でも良い）
                    surrogate_value, _ = winreg.QueryValueEx(
                        key, "DllSurrogate")
                    logging.info(
                        f"AppID '{appid}' のDllSurrogate: '{surrogate_value}' ({view_name} レジストリビューで発見)")
                    return True
                except FileNotFoundError:
                    logging.debug(
                        f"AppID '{appid}' にDllSurrogateが設定されていません ({view_name})")
                    continue
        except FileNotFoundError:
            logging.debug(f"AppID '{appid}' が見つかりません ({view_name})")
            continue
        except Exception as e:
            logging.debug(f"DllSurrogate確認エラー ({view_name}): {e}")
            continue

    logging.info(f"AppID '{appid}' にDllSurrogateが設定されていません（全ビュー確認済み）")
    return False


def enable_dll_surrogate(appid: str) -> bool:
    """
    AppIDのDLLサロゲートを有効化（64bit/32bit対応強化版）

    Args:
        appid: アプリケーションID

    Returns:
        bool: 設定成功の場合True
    """
    flags = get_registry_access_flags()

    # 書き込み用のアクセスフラグで試行
    write_attempts = [
        ("preferred", flags["preferred_write"]),
        ("write_32bit", flags["write_32bit"]),
        ("standard", flags["write"]),
        ("write_64bit", flags["write_64bit"])
    ]

    for view_name, write_flag in write_attempts:
        try:
            # AppIDキーを作成または開く
            with winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, f"AppID\\{appid}") as key:
                # 適切なアクセス権で再度開く
                with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, f"AppID\\{appid}", 0, write_flag) as write_key:
                    # DllSurrogateを空文字列で設定（これによりデフォルトのdllhost.exeが使用される）
                    winreg.SetValueEx(
                        write_key, "DllSurrogate", 0, winreg.REG_SZ, "")
                    logging.info(
                        f"AppID '{appid}' にDllSurrogateを設定しました ({view_name})")
                    return True
        except PermissionError:
            logging.debug(f"DllSurrogate設定: 管理者権限が不足しています ({view_name})")
            continue
        except Exception as e:
            logging.debug(f"DllSurrogate設定エラー ({view_name}): {e}")
            continue

    logging.error(f"AppID '{appid}' のDllSurrogate有効化が全てのレジストリビューで失敗しました")
    return False


def ensure_com_surrogate_for_jvlink() -> bool:
    """
    JV-LinkのDLLサロゲートを確実に有効化（64bit/32bit対応強化版）

    64bit Python環境で32bit JV-Link COMコンポーネントを呼び出せるようにする。
    複数のレジストリビューを考慮した堅牢な実装。

    Returns:
        bool: 設定成功の場合True

    Raises:
        RegistryConfigurationError: 設定に失敗した場合
    """
    progid = "JVDTLab.JVLink"

    try:
        logging.info("=== JV-Link DLLサロゲート設定を開始（64bit/32bit対応版） ===")

        # 現在のPython環境情報をログ出力
        python_arch = "64bit" if sys.maxsize > 2**32 else "32bit"
        logging.info(f"実行環境: {python_arch} Python")

        # ステップ1: ProgIDからCLSIDを取得
        clsid = get_progid_clsid(progid)
        if not clsid:
            raise RegistryConfigurationError(
                f"ProgID '{progid}' からCLSIDを取得できません。"
                f"JV-Linkが正しくインストールされているか確認してください。"
            )

        # ステップ2: CLSIDの存在確認
        if not check_clsid_exists(clsid):
            raise RegistryConfigurationError(
                f"CLSID '{clsid}' が登録されていません。"
                f"JV-Linkが正しくインストールされているか確認してください。"
            )

        # ステップ3: 既存のAppIDを確認
        existing_appid = get_appid_from_clsid(clsid)

        # AppIDを決定（既存のものがあればそれを使用、なければCLSIDを使用）
        appid = existing_appid if existing_appid else clsid
        logging.info(f"使用するAppID: {appid}")

        # ステップ4: CLSIDにAppIDを設定（必要に応じて）
        if not existing_appid:
            logging.info(f"CLSID '{clsid}' にAppID '{appid}' を設定します...")
            if not set_appid_for_clsid(clsid, appid):
                raise RegistryConfigurationError(
                    f"CLSID '{clsid}' にAppIDを設定できません")

        # ステップ5: DLLサロゲートの確認と設定
        if check_dll_surrogate_enabled(appid):
            logging.info(f"✅ DLLサロゲートは既に有効化されています (AppID: {appid})")
            return True
        else:
            logging.info(f"DLLサロゲートを有効化します (AppID: {appid})")
            if enable_dll_surrogate(appid):
                logging.info(f"✅ DLLサロゲートの有効化が完了しました")

                # 成功後、再度確認
                if check_dll_surrogate_enabled(appid):
                    logging.info(f"🔍 DLLサロゲート設定の確認: 正常に有効化されています")
                    return True
                else:
                    logging.warning(f"⚠️  DLLサロゲート設定後の確認で問題が見つかりました")
                    return False
            else:
                raise RegistryConfigurationError(
                    f"AppID '{appid}' のDLLサロゲート有効化に失敗しました")

    except RegistryConfigurationError:
        raise
    except Exception as e:
        error_msg = f"JV-Link DLLサロゲート設定で予期しないエラー: {e}"
        logging.error(error_msg)
        raise RegistryConfigurationError(error_msg)
    finally:
        logging.info("=== JV-Link DLLサロゲート設定を終了 ===")


def get_jvlink_registry_status() -> Dict[str, Any]:
    """
    JV-Linkのレジストリ設定状況を取得（64bit/32bit対応強化版）

    Returns:
        Dict[str, Any]: 設定状況の詳細情報
    """
    progid = "JVDTLab.JVLink"
    python_arch = "64bit" if sys.maxsize > 2**32 else "32bit"

    status = {
        "progid": progid,
        "python_architecture": python_arch,
        "clsid": None,
        "clsid_exists": False,
        "appid": None,
        "dll_surrogate_enabled": False,
        "configuration_complete": False,
        "registry_views_checked": []
    }

    try:
        # レジストリアクセスフラグ情報を追加
        flags = get_registry_access_flags()
        status["registry_access_info"] = {
            "preferred_access": "32bit_view" if python_arch == "64bit" else "standard",
            "flags_used": list(flags.keys())
        }

        # CLSID取得
        clsid = get_progid_clsid(progid)
        status["clsid"] = clsid

        if clsid:
            # CLSID存在確認
            status["clsid_exists"] = check_clsid_exists(clsid)

            if status["clsid_exists"]:
                # AppID取得
                appid = get_appid_from_clsid(clsid)
                status["appid"] = appid

                if appid:
                    # DLLサロゲート確認
                    status["dll_surrogate_enabled"] = check_dll_surrogate_enabled(
                        appid)
                    status["configuration_complete"] = status["dll_surrogate_enabled"]

                    if status["dll_surrogate_enabled"]:
                        status["surrogate_info"] = {
                            "appid": appid,
                            "dll_host": "dllhost.exe",
                            "bitness": "32bit COM server in 64bit Python environment" if python_arch == "64bit" else "Native architecture"
                        }

    except Exception as e:
        status["error"] = str(e)
        logging.error(f"レジストリ状況取得エラー: {e}")

    return status


if __name__ == "__main__":
    # テスト実行
    print("=== Registry Helper Test ===")

    # 現在の状況確認
    status = get_jvlink_registry_status()
    print("\n現在のJV-Linkレジストリ設定:")
    for key, value in status.items():
        print(f"  {key}: {value}")

    # DLLサロゲート設定の実行
    print("\nDLLサロゲート設定を実行します...")
    try:
        result = ensure_com_surrogate_for_jvlink()
        print(f"設定結果: {'成功' if result else '失敗'}")
    except RegistryConfigurationError as e:
        print(f"設定エラー: {e}")
    except Exception as e:
        print(f"予期しないエラー: {e}")

    # 設定後の状況確認
    print("\n設定後のJV-Linkレジストリ設定:")
    status_after = get_jvlink_registry_status()
    for key, value in status_after.items():
        print(f"  {key}: {value}")
