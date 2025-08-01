"""
JRA-VAN データレコード定義
YAML仕様ファイルに基づく型安全なdataclassモデル

このモジュールは specs/ ディレクトリのYAML仕様から生成される
データ構造を定義し、ETLパイプライン全体で使用される
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class RaceDetail:
    """
    レース詳細情報 (RA レコード)

    JRA-VAN RA仕様に基づくレース基本情報
    specs/RA.yaml に対応
    """

    # レコード識別
    record_spec_id: str = ""  # 2文字
    data_kubun: str = ""      # 1文字
    create_date: str = ""     # 8文字

    # 開催情報
    kaisai_year: int = 0      # 4桁
    kaisai_date: str = ""     # 4文字 (MMDD)
    keibajo_code: str = ""    # 競馬場コード 2文字
    kaisai_kaiji: int = 0     # 開催回次 2桁
    kaisai_nichiji: int = 0   # 開催日次 2桁
    race_number: int = 0      # レース番号 2桁
    weekday_code: str = ""    # 曜日コード 1文字

    # レース名
    tokubetsu_race_no: int = 0           # 特別レース番号 4桁
    race_name_main: str = ""             # レース名本文 60文字
    race_name_sub: str = ""              # レース名副題 60文字
    race_name_paren: str = ""            # レース名カッコ内 60文字
    race_name_main_en: str = ""          # レース名本文(英語) 120文字
    race_name_sub_en: str = ""           # レース名副題(英語) 120文字
    race_name_paren_en: str = ""         # レース名カッコ内(英語) 120文字
    race_name_short10: str = ""          # レース名短縮10文字 20文字
    race_name_short6: str = ""           # レース名短縮6文字 12文字
    race_name_short3: str = ""           # レース名短縮3文字 6文字
    race_name_kubun: str = ""            # レース名区分 1文字

    # グレード・条件
    grade_times: int = 0      # グレード回数 3桁
    grade_code: str = ""      # グレードコード 1文字
    before_grade_code: str = ""  # 前回グレードコード 1文字
    race_type_code: str = ""  # レース種別コード 2文字
    race_symbol_code: str = ""  # レース記号コード 3文字
    weight_type_code: str = ""  # 重量種別コード 1文字

    # 出走条件
    condition_2yo: str = ""   # 2歳条件 3文字
    condition_3yo: str = ""   # 3歳条件 3文字
    condition_4yo: str = ""   # 4歳条件 3文字
    condition_5up: str = ""   # 5歳以上条件 3文字
    condition_min_age: str = ""  # 最低出走年齢 3文字
    condition_name: str = ""  # 条件名 60文字

    # 距離・コース
    distance: int = 0         # 距離 4桁
    before_distance: int = 0  # 前回距離 4桁
    track_code: str = ""      # トラックコード 2文字
    before_track_code: str = ""  # 前回トラックコード 2文字
    course_kubun: str = ""    # コース区分 2文字
    before_course_kubun: str = ""  # 前回コース区分 2文字

    # 賞金・時刻
    prize_money: str = ""           # 本賞金 56文字
    before_prize_money: str = ""    # 前回本賞金 40文字
    additional_prize: str = ""      # 付加賞金 40文字
    before_additional_prize: str = ""  # 前回付加賞金 24文字
    start_time: str = ""            # 発走時刻 4文字
    before_start_time: str = ""     # 前回発走時刻 4文字

    # 頭数
    registered_headcount: int = 0   # 登録頭数 2桁
    starter_headcount: int = 0      # 出走頭数 2桁
    finish_headcount: int = 0       # 完走頭数 2桁

    # 天候・馬場
    weather_code: str = ""          # 天候コード 1文字
    turf_condition_code: str = ""   # 芝馬場状態コード 1文字
    dirt_condition_code: str = ""   # ダート馬場状態コード 1文字

    # タイム情報
    lap_time: str = ""              # ラップタイム 75文字
    obstacle_mile_time: str = ""    # 障害1マイルタイム 4文字
    first3f: str = ""               # 前3F 3文字
    first4f: str = ""               # 前4F 3文字
    last3f: str = ""                # 後3F 3文字
    last4f: str = ""                # 後4F 3文字
    corner_pass_order: str = ""     # コーナー通過順位 288文字

    # 更新情報
    record_update_kubun: str = ""   # レコード更新区分 1文字
    record_delimiter: str = ""      # レコード区切り 2文字

    def __post_init__(self):
        """データクレンジングと検証"""
        # 文字列フィールドのトリミング
        for field_name, field_value in self.__dataclass_fields__.items():
            current_value = getattr(self, field_name)
            if isinstance(current_value, str):
                setattr(self, field_name, current_value.strip())


@dataclass
class HorseRaceInfo:
    """
    馬毎レース情報 (SE レコード)

    JRA-VAN SE仕様に基づく出走馬詳細情報
    specs/SE.yaml に対応
    """

    # レコード識別
    record_spec_id: str = ""        # 2文字
    data_kubun: str = ""            # 1文字
    create_date: str = ""           # 8文字

    # 開催・レース情報
    kaisai_year: int = 0            # 4桁
    kaisai_date: str = ""           # 4文字 (MMDD)
    keibajo_code: str = ""          # 競馬場コード 2文字
    kaisai_kaiji: int = 0           # 開催回次 2桁
    kaisai_nichiji: int = 0         # 開催日次 2桁
    race_number: int = 0            # レース番号 2桁

    # 出走馬識別
    wakuban: int = 0                # 枠番 1桁
    umaban: int = 0                 # 馬番 2桁
    ketto_toroku_bango: str = ""    # 血統登録番号 10文字

    # 馬基本情報
    bamei: str = ""                 # 馬名 36文字
    bakyugo_code: str = ""          # 馬記号コード 2文字
    sex_code: str = ""              # 性別コード 1文字
    breed_code: str = ""            # 品種コード 1文字
    color_code: str = ""            # 毛色コード 2文字
    age: int = 0                    # 年齢 2桁
    belong_code: str = ""           # 所属コード 1文字

    # 厩舎・騎手・馬主
    trainer_code: str = ""          # 調教師コード 5文字
    trainer_name_short: str = ""    # 調教師名短縮 8文字
    owner_code: str = ""            # 馬主コード 6文字
    owner_name: str = ""            # 馬主名 64文字
    silk_color: str = ""            # 服色 60文字
    reserved1: str = ""             # 予備 60文字

    # 重量・装具
    handicap: float = 0.0           # ハンデ重量 3桁
    before_handicap: float = 0.0    # 前回ハンデ重量 3桁
    blinker_flag: str = ""          # ブリンカー 1文字
    reserved2: str = ""             # 予備 1文字

    # 騎手情報
    jockey_code: str = ""           # 騎手コード 5文字
    before_jockey_code: str = ""    # 前回騎手コード 5文字
    jockey_name_short: str = ""     # 騎手名短縮 8文字
    before_jockey_name_short: str = ""  # 前回騎手名短縮 8文字
    jockey_apprentice_code: str = ""  # 見習区分 1文字
    before_jockey_apprentice_code: str = ""  # 前回見習区分 1文字

    # 馬体重
    weight: int = 0                 # 馬体重 3桁
    weight_diff_sign: str = ""      # 馬体重増減符号 1文字
    weight_diff: int = 0            # 馬体重増減 3桁

    # レース結果
    abnormal_code: str = ""         # 異常区分 1文字
    passing_order: int = 0          # 確定着順 2桁
    official_finish_position: int = 0  # 公式着順 2桁
    dead_heat_flag: str = ""        # 同着区分 1文字
    dead_heat_horse_count: int = 0  # 同着頭数 1桁
    time: str = ""                  # タイム 4文字

    # 着差情報
    margin_code: str = ""           # 着差コード 3文字
    margin_code_plus: str = ""      # 着差コード+ 3文字
    margin_code_plus2: str = ""     # 着差コード++ 3文字

    # コーナー順位
    corner1_order: int = 0          # 1コーナー順位 2桁
    corner2_order: int = 0          # 2コーナー順位 2桁
    corner3_order: int = 0          # 3コーナー順位 2桁
    corner4_order: int = 0          # 4コーナー順位 2桁

    # 人気・オッズ
    odds: str = ""                  # 単勝オッズ 4文字
    odds_rank: int = 0              # 人気 2桁

    # 賞金
    prize: int = 0                  # 獲得賞金 8桁
    additional_prize: int = 0       # 獲得付加賞金 8桁

    # 追加情報
    reserved3: str = ""             # 予備 3文字
    reserved4: str = ""             # 予備 3文字
    last4f_time: str = ""           # 後4Fタイム 3文字
    last3f_time: str = ""           # 後3Fタイム 3文字
    first_place_horse_info: str = ""  # 1着馬情報 138文字
    time_diff: str = ""             # 着差タイム 4文字

    # 更新・マイニング情報
    record_update_kubun: str = ""   # レコード更新区分 1文字
    mining_flag: str = ""           # マイニング予想フラグ 1文字
    mining_predicted_time: str = ""  # マイニング予想タイム 5文字
    mining_error_plus: str = ""     # マイニング誤差+ 4文字
    mining_error_minus: str = ""    # マイニング誤差- 4文字
    mining_rank: int = 0            # マイニング順位 2桁
    race_running_style: str = ""    # レース脚質 1文字
    record_delimiter: str = ""      # レコード区切り 2文字

    def __post_init__(self):
        """データクレンジングと検証"""
        # 文字列フィールドのトリミング
        for field_name, field_value in self.__dataclass_fields__.items():
            current_value = getattr(self, field_name)
            if isinstance(current_value, str):
                setattr(self, field_name, current_value.strip())

    @property
    def weight_change(self) -> Optional[int]:
        """馬体重増減を符号付きで返す"""
        if self.weight_diff_sign == "+":
            return self.weight_diff
        elif self.weight_diff_sign == "-":
            return -self.weight_diff
        return None


@dataclass
class ProcessingMetadata:
    """
    データ処理メタデータ

    ETLパイプラインで使用されるメタ情報を格納
    """

    source_file: str = ""           # ソースファイル名
    processed_at: Optional[datetime] = None  # 処理日時
    record_count: int = 0           # レコード数
    error_count: int = 0            # エラー数
    validation_status: str = "pending"  # 検証ステータス
    checksum: str = ""              # チェックサム
    encoding: str = "shift_jis"     # ファイルエンコーディング
    file_size: int = 0              # ファイルサイズ

    def __post_init__(self):
        """メタデータの初期化後処理"""
        if self.processed_at is None:
            self.processed_at = datetime.now()


# レコード種別とdataclassのマッピング
RECORD_CLASS_MAPPING: Dict[str, type] = {
    "RA": RaceDetail,
    "SE": HorseRaceInfo,
}


def create_record_from_dict(record_spec: str, data: Dict[str, Any]) -> Optional[Any]:
    """
    辞書データからdataclassインスタンスを作成

    Args:
        record_spec: レコード種別 ("RA", "SE", etc.)
        data: 辞書形式のデータ

    Returns:
        適切なdataclassインスタンス
    """
    record_class = RECORD_CLASS_MAPPING.get(record_spec.upper())

    if record_class is None:
        return None

    try:
        # フィールド名のマッピングと型変換
        filtered_data = {}
        for field_name, field_def in record_class.__dataclass_fields__.items():
            if field_name in data:
                value = data[field_name]
                # 型変換
                if field_def.type == int and isinstance(value, str):
                    filtered_data[field_name] = int(
                        value) if value.isdigit() else 0
                elif field_def.type == float and isinstance(value, str):
                    filtered_data[field_name] = float(
                        value) if value.replace('.', '').isdigit() else 0.0
                else:
                    filtered_data[field_name] = value

        return record_class(**filtered_data)

    except Exception as e:
        # ログ出力などのエラーハンドリングは呼び出し側で行う
        raise ValueError(f"Failed to create {record_spec} record: {e}")


def validate_record(record: Any) -> List[str]:
    """
    レコードの検証を行い、エラーメッセージのリストを返す

    Args:
        record: 検証対象のdataclassインスタンス

    Returns:
        エラーメッセージのリスト（空の場合は検証成功）
    """
    errors = []

    if isinstance(record, RaceDetail):
        # レース詳細の検証
        if not record.race_number or record.race_number <= 0:
            errors.append("レース番号が無効です")
        if not record.distance or record.distance <= 0:
            errors.append("距離が無効です")
        if not record.keibajo_code:
            errors.append("競馬場コードが必須です")

    elif isinstance(record, HorseRaceInfo):
        # 馬毎レース情報の検証
        if not record.umaban or record.umaban <= 0:
            errors.append("馬番が無効です")
        if not record.ketto_toroku_bango:
            errors.append("血統登録番号が必須です")
        if record.age <= 0:
            errors.append("年齢が無効です")

    return errors


# ETL処理で使用するヘルパー関数
def extract_race_key(record) -> str:
    """
    レコードからレース識別キーを抽出

    Returns:
        "{年度}{競馬場}{開催回次}{開催日次}{レース番号}" 形式の文字列
    """
    if hasattr(record, 'kaisai_year') and hasattr(record, 'keibajo_code'):
        return f"{record.kaisai_year}{record.keibajo_code}{record.kaisai_kaiji:02d}{record.kaisai_nichiji:02d}{record.race_number:02d}"
    return ""


def extract_horse_key(record: HorseRaceInfo) -> str:
    """
    馬毎レース情報から馬識別キーを抽出

    Returns:
        血統登録番号
    """
    return record.ketto_toroku_bango
