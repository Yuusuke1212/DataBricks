#!/usr/bin/env python3
"""
JRA-Data Collector アプリケーション エントリーポイント

このスクリプトは JRA-Data Collector アプリケーションのメインエントリーポイントです。
アプリケーションの初期設定、ログ設定、管理者権限チェックを実行し、
GUIアプリケーションを起動します。

実行方法:
    python run.pyw
    または
    run.pyw (Windowsでファイルをダブルクリック)
"""

import sys
import traceback  # ★追加★: 詳細デバッグ用
from datetime import datetime
from pathlib import Path

# ★追加★: 詳細デバッグ用のグローバル例外ハンドラ
def detailed_exception_handler(exctype, value, tb):
    """詳細な例外情報を出力するグローバルハンドラ"""
    error_msg = f"UNCAUGHT EXCEPTION: {exctype.__name__}: {value}"
    traceback_str = ''.join(traceback.format_tb(tb))
    
    print(f"\n{'='*60}")
    print(f"FATAL ERROR DETECTED")
    print(f"{'='*60}")
    print(f"Exception Type: {exctype.__name__}")
    print(f"Exception Value: {value}")
    print(f"Traceback:")
    print(traceback_str)
    print(f"{'='*60}\n")
    
    # ログファイルにも出力
    try:
        import logging
        logging.error(f"UNCAUGHT EXCEPTION: {error_msg}")
        logging.error(f"Traceback:\n{traceback_str}")
    except:
        pass

# ★追加★: グローバル例外ハンドラを設定
sys.excepthook = detailed_exception_handler

        try:
    from src.main import main
    
    # ★追加★: デバッグ情報の初期出力
    print(f"{'='*60}")
    print(f"JRA-Data Collector Debug Mode")
    print(f"{'='*60}")
    print(f"Python Version: {sys.version}")
    print(f"Python Executable: {sys.executable}")
    print(f"Working Directory: {Path.cwd()}")
    print(f"Script Path: {__file__}")
    print(f"System Arguments: {sys.argv}")
    print(f"{'='*60}\n")
    
    if __name__ == "__main__":
        # ★追加★: 詳細デバッグ実行
        try:
            print("🚀 JRA-Data Collector を起動しています...")
            exit_code = main()
            print(f"✅ アプリケーション正常終了（終了コード: {exit_code}）")
            sys.exit(exit_code)
            
        except KeyboardInterrupt:
            print("\n⚠️ ユーザーによる中断（Ctrl+C）")
            sys.exit(1)
            
        except Exception as e:
            # ★追加★: 最上位レベルの例外ハンドリング
            error_traceback = traceback.format_exc()
            print(f"\n❌ CRITICAL ERROR: {e}")
            print(f"詳細スタックトレース:\n{error_traceback}")
            
            # ★追加★: エラー種別の詳細解析
            if "'str' object has no attribute 'value'" in str(e):
                print("\n🔍 'str' object has no attribute 'value' エラーを検出!")
                print("   このエラーは文字列に対して.valueアクセスしようとした際に発生します")
                print("   Enumオブジェクトが期待されている箇所に文字列が渡されている可能性があります")

                # ★追加★: エラー発生箇所の詳細
                if hasattr(e, '__traceback__') and e.__traceback__:
                    frame = traceback.extract_tb(e.__traceback__)[-1]
                    print(f"   エラー発生ファイル: {frame.filename}")
                    print(f"   エラー発生行番号: {frame.lineno}")
                    print(f"   エラー発生関数: {frame.name}")
                    print(f"   エラー発生コード: {frame.line}")
            
            log_file = Path.cwd() / "logs" / f"jra_data_collector_{datetime.now().strftime('%Y%m%d')}.log"
            print(f"\n📝 詳細は以下のログファイルを確認してください:")
            print(f"   {log_file}")
            
            sys.exit(1)

except ImportError as e:
    # ★追加★: インポートエラーの詳細解析
    error_traceback = traceback.format_exc()
    print(f"\n❌ IMPORT ERROR: {e}")
    print(f"詳細スタックトレース:\n{error_traceback}")
    print(f"\n📋 可能な原因:")
    print(f"   1. 必要なPythonパッケージがインストールされていない")
    print(f"   2. パスの設定に問題がある")
    print(f"   3. src/main.py ファイルが見つからない")
    print(f"\n🔧 対処方法:")
    print(f"   1. pip install -r requirements.txt を実行")
    print(f"   2. カレントディレクトリがプロジェクトルートであることを確認")
    sys.exit(1)

except Exception as e:
    # ★追加★: その他の予期しないエラー
    error_traceback = traceback.format_exc()
    print(f"\n❌ UNEXPECTED ERROR: {e}")
    print(f"詳細スタックトレース:\n{error_traceback}")
        sys.exit(1)
