"""
JRA-VAN DataBriocks カスタム例外階層
JV-Linkエラーコードに基づく包括的なエラーハンドリング
"""

from typing import Optional, Dict, Any


class JVLinkError(Exception):
    """
    JV-Linkエラーの基底クラス

    すべてのJV-Link関連エラーはこのクラスを継承する
    """

    def __init__(self, message: str, error_code: Optional[int] = None, context: Optional[Dict[str, Any]] = None):
        """
        JV-Linkエラーを初期化

        Args:
            message: エラーメッセージ
            error_code: JV-Linkエラーコード
            context: エラーのコンテキスト情報
        """
        super().__init__(message)
        self.error_code = error_code
        self.context = context or {}

    def __str__(self) -> str:
        if self.error_code is not None:
            return f"[JV-Link Error {self.error_code}] {super().__str__()}"
        return super().__str__()


class JVLinkAuthError(JVLinkError):
    """
    認証関連エラー (致命的エラー)

    エラーコード: -1, -3, -4
    対処: サービスキー確認、ユーザー通知
    """
    pass


class JVLinkNetworkError(JVLinkError):
    """
    ネットワーク関連エラー (リトライ可能)

    エラーコード: -2, -5, -6
    対処: 指数バックオフでリトライ
    """

    def __init__(self, message: str, error_code: Optional[int] = None,
                 context: Optional[Dict[str, Any]] = None, retry_count: int = 0):
        super().__init__(message, error_code, context)
        self.retry_count = retry_count


class JVLinkParameterError(JVLinkError):
    """
    パラメータエラー (プログラムロジックエラー)

    エラーコード: -7, -8, -9
    対処: パラメータ検証、ログ出力
    """
    pass


class JVLinkStateError(JVLinkError):
    """
    状態エラー (JV-Link未初期化等)

    エラーコード: -10, -11
    対処: 初期化処理の実行
    """
    pass


class JVLinkDataError(JVLinkError):
    """
    データ関連エラー

    エラーコード: -12, -13, -14
    対処: データ再取得、フォーマット確認
    """
    pass


class JVLinkResourceError(JVLinkError):
    """
    リソース関連エラー

    エラーコード: -15, -16
    対処: リソース解放、メモリ確認
    """
    pass


class JVLinkTimeoutError(JVLinkError):
    """
    タイムアウトエラー (リトライ可能)

    エラーコード: -17, -18
    対処: タイムアウト値調整、リトライ
    """

    def __init__(self, message: str, error_code: Optional[int] = None,
                 context: Optional[Dict[str, Any]] = None, timeout_seconds: Optional[float] = None):
        super().__init__(message, error_code, context)
        self.timeout_seconds = timeout_seconds


# データベース関連の例外
class DatabaseError(Exception):
    """データベース操作エラーの基底クラス"""

    def __init__(self, message: str, operation: Optional[str] = None,
                 context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.operation = operation
        self.context = context or {}


class DatabaseConnectionError(DatabaseError):
    """データベース接続エラー"""
    pass


class DatabaseIntegrityError(DatabaseError):
    """データベース整合性エラー"""
    pass


class DatabaseTransactionError(DatabaseError):
    """データベーストランザクションエラー"""
    pass


# 設定関連の例外
class ConfigurationError(Exception):
    """設定関連エラーの基底クラス"""

    def __init__(self, message: str, config_section: Optional[str] = None,
                 config_key: Optional[str] = None):
        super().__init__(message)
        self.config_section = config_section
        self.config_key = config_key


class ConfigurationMissingError(ConfigurationError):
    """必須設定項目の不足エラー"""
    pass


class ConfigurationValidationError(ConfigurationError):
    """設定値の検証エラー"""
    pass


# ETL処理関連の例外
class ETLError(Exception):
    """ETL処理エラーの基底クラス"""

    def __init__(self, message: str, stage: Optional[str] = None,
                 record_count: Optional[int] = None):
        super().__init__(message)
        self.stage = stage  # 'extract', 'transform', 'load'
        self.record_count = record_count


class ETLExtractionError(ETLError):
    """データ抽出エラー"""
    pass


class ETLTransformationError(ETLError):
    """データ変換エラー"""
    pass


class ETLLoadError(ETLError):
    """データロードエラー"""
    pass


# ファイル処理関連の例外
class FileProcessingError(Exception):
    """ファイル処理エラーの基底クラス"""

    def __init__(self, message: str, file_path: Optional[str] = None,
                 encoding: Optional[str] = None):
        super().__init__(message)
        self.file_path = file_path
        self.encoding = encoding


class FileEncodingError(FileProcessingError):
    """ファイルエンコーディングエラー"""
    pass


class FileFormatError(FileProcessingError):
    """ファイルフォーマットエラー"""
    pass


# JV-Linkエラーコードマッピング
ERROR_CODE_MAPPING: Dict[int, type] = {
    # 認証エラー
    -1: JVLinkAuthError,
    -3: JVLinkAuthError,
    -4: JVLinkAuthError,

    # ネットワークエラー
    -2: JVLinkNetworkError,
    -5: JVLinkNetworkError,
    -6: JVLinkNetworkError,

    # パラメータエラー
    -7: JVLinkParameterError,
    -8: JVLinkParameterError,
    -9: JVLinkParameterError,

    # 状態エラー
    -10: JVLinkStateError,
    -11: JVLinkStateError,

    # データエラー
    -12: JVLinkDataError,
    -13: JVLinkDataError,
    -14: JVLinkDataError,

    # リソースエラー
    -15: JVLinkResourceError,
    -16: JVLinkResourceError,

    # タイムアウトエラー
    -17: JVLinkTimeoutError,
    -18: JVLinkTimeoutError,
}


# エラーコード詳細説明
ERROR_CODE_DESCRIPTIONS: Dict[int, str] = {
    -1: "認証エラー: サービスキーが無効です",
    -2: "ネットワークエラー: サーバーに接続できません",
    -3: "認証エラー: 利用権限がありません",
    -4: "認証エラー: 認証に失敗しました",
    -5: "ネットワークエラー: データ取得に失敗しました",
    -6: "ネットワークエラー: 通信がタイムアウトしました",
    -7: "パラメータエラー: 不正なパラメータです",
    -8: "パラメータエラー: パラメータが不足しています",
    -9: "パラメータエラー: パラメータの組み合わせが不正です",
    -10: "状態エラー: JV-Linkが初期化されていません",
    -11: "状態エラー: 不正な状態です",
    -12: "データエラー: データが見つかりません",
    -13: "データエラー: データ形式が不正です",
    -14: "データエラー: データが破損しています",
    -15: "リソースエラー: メモリが不足しています",
    -16: "リソースエラー: ファイルにアクセスできません",
    -17: "タイムアウトエラー: 処理がタイムアウトしました",
    -18: "タイムアウトエラー: レスポンス待機がタイムアウトしました",
}


def create_jvlink_error(error_code: int, message: Optional[str] = None,
                        context: Optional[Dict[str, Any]] = None) -> JVLinkError:
    """
    JV-Linkエラーコードから適切な例外インスタンスを作成

    Args:
        error_code: JV-Linkエラーコード
        message: カスタムメッセージ（省略時はデフォルトメッセージを使用）
        context: エラーのコンテキスト情報

    Returns:
        適切な例外インスタンス
    """
    if message is None:
        message = ERROR_CODE_DESCRIPTIONS.get(
            error_code, f"未知のJV-Linkエラー: {error_code}")

    exception_class = ERROR_CODE_MAPPING.get(error_code, JVLinkError)

    return exception_class(message, error_code, context)


def is_retryable_error(exception: Exception) -> bool:
    """
    エラーがリトライ可能かどうかを判定

    Args:
        exception: 判定対象の例外

    Returns:
        リトライ可能な場合True
    """
    return isinstance(exception, (JVLinkNetworkError, JVLinkTimeoutError))


def get_retry_delay(retry_count: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
    """
    リトライ回数に基づく指数バックオフ遅延時間を計算

    Args:
        retry_count: リトライ回数
        base_delay: 基本遅延時間（秒）
        max_delay: 最大遅延時間（秒）

    Returns:
        遅延時間（秒）
    """
    delay = base_delay * (2 ** retry_count)
    return min(delay, max_delay)


# レガシーコードとの互換性のためのエイリアス
ConnectionError = JVLinkNetworkError  # 既存のConnectionErrorの置き換え
