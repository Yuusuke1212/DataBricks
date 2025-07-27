import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, text, ForeignKey, PrimaryKeyConstraint, JSON, Text
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class SpecialEntry(Base):
    __tablename__ = 'special_entries'
    id = Column(Text, primary_key=True)
    race_id = Column(Text)
    data_kubun = Column(Text)
    data_sakusei_nengappi = Column(Text)
    tokubetsu_kyoso_bango = Column(Integer)
    race_name_hondai = Column(Text)
    race_name_fukudai = Column(Text)
    race_name_kakko = Column(Text)
    race_name_hondai_eiji = Column(Text)
    race_name_fukudai_eiji = Column(Text)
    race_name_kakko_eiji = Column(Text)
    race_name_ryaku_10 = Column(Text)
    race_name_ryaku_6 = Column(Text)
    race_name_ryaku_3 = Column(Text)
    joken_code_sai2 = Column(Text)
    joken_code_sai3 = Column(Text)
    joken_code_sai4 = Column(Text)
    joken_code_sai5_ijo = Column(Text)
    joken_code_saijaku = Column(Text)
    grade_code = Column(Text)
    kyori = Column(Integer)
    track_code = Column(Text)
    course_kubun = Column(Text)
    hande_happyo_nengappi = Column(Text)
    toroku_tosu = Column(Integer)
    entry_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Race(Base):
    __tablename__ = 'races'
    race_id = Column(Text, primary_key=True)
    data_kubun = Column(Text)
    data_sakusei_nengappi = Column(Text)
    kaisai_nen = Column(Integer)
    kaisai_tsukihi = Column(Text)
    keibajo_code = Column(Text)
    kaisai_kaiji = Column(Integer)
    kaisai_nichiji = Column(Integer)
    race_bango = Column(Integer)
    yobi_code = Column(Text)
    tokubetsu_kyoso_bango = Column(Integer)
    race_name_hondai = Column(Text)
    race_name_fukudai = Column(Text)
    race_name_kakko = Column(Text)
    race_name_hondai_eiji = Column(Text)
    race_name_fukudai_eiji = Column(Text)
    race_name_kakko_eiji = Column(Text)
    race_name_ryaku_10 = Column(Text)
    race_name_ryaku_6 = Column(Text)
    race_name_ryaku_3 = Column(Text)
    joken_code_sai2 = Column(Text)
    joken_code_sai3 = Column(Text)
    joken_code_sai4 = Column(Text)
    joken_code_sai5_ijo = Column(Text)
    joken_code_saijaku = Column(Text)
    grade_code = Column(Text)
    kyori = Column(Integer)
    track_code = Column(Text)
    course_kubun = Column(Text)
    honshokin = Column(JSON)
    fukashokin = Column(JSON)
    toroku_tosu = Column(Integer)
    shusso_tosu = Column(Integer)
    nyusen_tosu = Column(Integer)
    tenko_code = Column(Text)
    shiba_baba_jotai_code = Column(Text)
    dirt_baba_jotai_code = Column(Text)
    lap_times = Column(JSON)
    shogai_mile_time = Column(Float)
    zenhan_3f_time = Column(Float)
    zenhan_4f_time = Column(Float)
    kohan_3f_time = Column(Float)
    kohan_4f_time = Column(Float)
    corner_tsuka_juni = Column(JSON)
    record_koshin_kubun = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class RaceEntry(Base):
    __tablename__ = 'race_entries'
    race_id = Column(Text, primary_key=True)
    umaban = Column(Integer, primary_key=True)
    wakuban = Column(Integer)
    ketto_toroku_bango = Column(Text, nullable=False)
    horse_name = Column(Text)
    bamei_shokai_kubun = Column(Text)
    seibetsu_code = Column(Text)
    hinshu_code = Column(Text)
    keiro_code = Column(Text)
    barei = Column(Integer)
    tozai_shozoku_code = Column(Text)
    chokyoshi_code = Column(Text)
    chokyoshi_name_ryaku = Column(Text)
    banushi_code = Column(Text)
    banushi_name = Column(Text)
    fukushoku_hyoji = Column(Text)
    futan_juryo = Column(Float)
    henkobae_futan_juryo = Column(Float)
    blinker_shiyo_kubun = Column(Text)
    yobi_1 = Column(Text)
    kishu_code = Column(Text)
    henkobae_kishu_code = Column(Text)
    kishu_name_ryaku = Column(Text)
    henkobae_kishu_name_ryaku = Column(Text)
    kishu_minarai_code = Column(Text)
    henkobae_kishu_minarai_code = Column(Text)
    bataijuu = Column(Integer)
    zogen_fugo = Column(Text)
    zogen_sa = Column(Integer)
    ijo_kubun_code = Column(Text)
    nyusen_juni = Column(Integer)
    kakutei_chakujun = Column(Integer)
    dochaku_kubun = Column(Text)
    dochaku_tosu = Column(Integer)
    soha_time = Column(Float)
    chakusa_code_1 = Column(Text)
    chakusa_code_2 = Column(Text)
    chakusa_code_3 = Column(Text)
    corner_jun_i_1 = Column(Integer)
    corner_jun_i_2 = Column(Integer)
    corner_jun_i_3 = Column(Integer)
    corner_jun_i_4 = Column(Integer)
    tansho_odds = Column(Float)
    tansho_ninki_jun = Column(Integer)
    kakutoku_honshokin = Column(Float)
    kakutoku_fukashokin = Column(Float)
    yobi_2 = Column(Text)
    yobi_3 = Column(Text)
    kohan_3f_time = Column(Float)
    aiteuma_joho = Column(JSON)
    time_sa = Column(Float)
    kesshutsu_kubun = Column(Text)
    kyakushitsu_hantei = Column(Text)
    win5_taishoflag = Column(Boolean)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Payout(Base):
    __tablename__ = 'payouts'
    race_id = Column(Text, primary_key=True)
    fuseiritsu_flags = Column(JSON)
    tokubarai_flags = Column(JSON)
    henkan_flags = Column(JSON)
    henkan_umabans = Column(JSON)
    henkan_wakubans = Column(JSON)
    henkan_dowakus = Column(JSON)
    payout_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Vote(Base):
    __tablename__ = 'votes'
    race_id = Column(Text, primary_key=True)
    bet_type = Column(Text, primary_key=True)
    is_released_flag = Column(Boolean)
    henkan_info = Column(JSON)
    votes_data = Column(JSON)
    total_votes = Column(Integer)
    henkan_votes = Column(Integer)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Odd(Base):
    __tablename__ = 'odds'
    race_id = Column(Text, primary_key=True)
    bet_type = Column(Text, primary_key=True)
    happyo_jippu = Column(Text, primary_key=True)
    is_released_flag = Column(Boolean)
    odds_data = Column(JSON)
    total_votes = Column(Integer)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Horse(Base):
    __tablename__ = 'horses'
    ketto_toroku_bango = Column(Text, primary_key=True)
    is_retired = Column(Boolean)
    massho_nengappi = Column(Text)
    touroku_nengappi = Column(Text)
    birthday = Column(Text)
    horse_name = Column(Text)
    horse_name_kana = Column(Text)
    horse_name_eiji = Column(Text)
    zairai_flag = Column(Text)
    yobi_4 = Column(Text)
    umakigo_code = Column(Text)
    seibetsu_code = Column(Text)
    hinshu_code = Column(Text)
    keiro_code = Column(Text)
    sandai_ketto_joho = Column(JSON)
    tozai_shozoku_code = Column(Text)
    chokyoshi_code = Column(Text)
    chokyoshi_name_ryaku = Column(Text)
    shodai_chiki = Column(Text)
    seisansha_code = Column(Text)
    seisansha_name = Column(Text)
    sanchi_name = Column(Text)
    banushi_code = Column(Text)
    banushi_name = Column(Text)
    heichi_honshokin = Column(Float)
    shogai_honshokin = Column(Float)
    heichi_fukashokin = Column(Float)
    shogai_fukashokin = Column(Float)
    heichi_shutoku_shokin = Column(Float)
    shogai_shutoku_shokin = Column(Float)
    chakudosu_data = Column(JSON)
    kyakushitsu_keiko = Column(JSON)
    toroku_race_su = Column(Integer)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Jockey(Base):
    __tablename__ = 'jockeys'
    kishu_code = Column(Text, primary_key=True)
    is_retired = Column(Boolean)
    menkyo_kofu_nengappi = Column(Text)
    menkyo_massho_nengappi = Column(Text)
    birthday = Column(Text)
    kishu_name = Column(Text)
    kishu_name_kana = Column(Text)
    kishu_name_ryaku = Column(Text)
    kishu_name_eiji = Column(Text)
    tozai_shozoku_code = Column(Text)
    shozoku_chokyoshi_code = Column(Text)
    shozoku_chokyoshi_name = Column(Text)
    kishu_minarai_code = Column(Text)
    heichi_chakudosu = Column(JSON)
    shogai_chakudosu = Column(JSON)
    honnen_heichi_seiseki = Column(JSON)
    honnen_shogai_seiseki = Column(JSON)
    zenen_heichi_seiseki = Column(JSON)
    zenen_shogai_seiseki = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Trainer(Base):
    __tablename__ = 'trainers'
    chokyoshi_code = Column(Text, primary_key=True)
    is_retired = Column(Boolean)
    menkyo_kofu_nengappi = Column(Text)
    menkyo_massho_nengappi = Column(Text)
    birthday = Column(Text)
    chokyoshi_name = Column(Text)
    chokyoshi_name_kana = Column(Text)
    chokyoshi_name_ryaku = Column(Text)
    chokyoshi_name_eiji = Column(Text)
    tozai_shozoku_code = Column(Text)
    shozoku_chiki_code = Column(Text)
    heichi_chakudosu = Column(JSON)
    shogai_chakudosu = Column(JSON)
    honnen_heichi_seiseki = Column(JSON)
    honnen_shogai_seiseki = Column(JSON)
    zenen_heichi_seiseki = Column(JSON)
    zenen_shogai_seiseki = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Owner(Base):
    __tablename__ = 'owners'
    banushi_code = Column(Text, primary_key=True)
    banushi_name = Column(Text)
    banushi_name_kana = Column(Text)
    banushi_name_eiji = Column(Text)
    fukushoku_shubetsu_code = Column(Text)
    fukushoku_gara_code_1 = Column(Text)
    fukushoku_gara_code_2 = Column(Text)
    fukushoku_iro_code_1 = Column(Text)
    fukushoku_iro_code_2 = Column(Text)
    fukushoku_iro_code_3 = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Producer(Base):
    __tablename__ = 'producers'
    seisansha_code = Column(Text, primary_key=True)
    seisansha_name = Column(Text)
    seisansha_name_kana = Column(Text)
    seisansha_name_eiji = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Broodmare(Base):
    __tablename__ = 'broodmares'
    ketto_toroku_bango = Column(Text, primary_key=True)
    horse_name = Column(Text)
    seisansha_name = Column(Text)
    sanchi_name = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Foal(Base):
    __tablename__ = 'foals'
    id = Column(Text, primary_key=True)
    ketto_toroku_bango = Column(Text)
    sanji = Column(Integer)
    birthday = Column(Text)
    seibetsu_code = Column(Text)
    keiro_code = Column(Text)
    shusshoji_chokyoshi_code = Column(Text)
    ketto_toroku_bango_chichi = Column(Text)
    ketto_toroku_bango_haha = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Bloodline(Base):
    __tablename__ = 'bloodlines'
    ketto_toroku_bango = Column(Text, primary_key=True)
    sanji_flg = Column(Integer)
    ketto_name = Column(Text)
    keito_code_1 = Column(Text)
    keito_code_2 = Column(Text)
    keito_code_3 = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class MiningPrediction(Base):
    __tablename__ = 'mining_predictions'
    id = Column(Text, primary_key=True)
    race_id = Column(Text)
    umaban = Column(Integer)
    mining_yoso_type = Column(Text)
    shukkeiso_kubun = Column(Text)
    yoso_soha_time = Column(Float)
    yoso_gokei_jun = Column(Integer)
    yoso_score = Column(Float)
    mining_teki_kyakushitsu = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class HorsePerformance(Base):
    __tablename__ = 'horse_performances'
    race_id = Column(Text, primary_key=True)
    umaban = Column(Integer, primary_key=True)
    blood_ana_score = Column(Float)
    chokyo_ana_score = Column(Float)
    jockey_ana_score = Column(Float)
    stable_ana_score = Column(Float)
    time_ana_score = Column(Float)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Record(Base):
    __tablename__ = 'records'
    id = Column(Text, primary_key=True)
    record_kubun = Column(Text)
    record_shubetsu_id = Column(Text)
    keibajo_code = Column(Text)
    track_code = Column(Text)
    kyori = Column(Integer)
    joken_code = Column(Text)
    record_time = Column(Float)
    record_holder_info = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Schedule(Base):
    __tablename__ = 'schedules'
    id = Column(Text, primary_key=True)
    kaisai_nen = Column(Integer)
    kaisai_tsukihi = Column(Text)
    keibajo_code = Column(Text)
    kaisai_kaiji = Column(Integer)
    kaisai_nichiji = Column(Integer)
    yobi_code = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Win5Info(Base):
    __tablename__ = 'win5_info'
    win5_id = Column(Text, primary_key=True)
    kaisai_nen = Column(Integer)
    kaisai_tsukihi = Column(Text)
    hyosu_sum = Column(Integer)
    tekichu_hyosu = Column(Integer)
    payout = Column(Integer)
    carry_over = Column(Integer)
    race_ids = Column(JSON)
    umabans = Column(JSON)
    ninkis = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class Win5Exclusion(Base):
    __tablename__ = 'win5_exclusions'
    win5_id = Column(Text, primary_key=True)
    race_id = Column(Text, primary_key=True)
    umaban = Column(Integer, primary_key=True)
    ketto_toroku_bango = Column(Text)
    bamei = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class SlopeTraining(Base):
    __tablename__ = 'slope_training'
    id = Column(Text, primary_key=True)
    ketto_toroku_bango = Column(Text)
    chokyo_nen_tsuki_hi = Column(Text)
    training_center_code = Column(Text)
    track_code = Column(Text)
    chokyo_time = Column(Float)
    chokyo_ashi = Column(Text)
    ippai_do = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class WoodchipTraining(Base):
    __tablename__ = 'woodchip_training'
    id = Column(Text, primary_key=True)
    ketto_toroku_bango = Column(Text)
    chokyo_nen_tsuki_hi = Column(Text)
    training_center_code = Column(Text)
    chokyo_keishiki = Column(Text)
    chokyo_time_data = Column(JSON)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class HorseSale(Base):
    __tablename__ = 'horse_sales'
    id = Column(Text, primary_key=True)
    ketto_toroku_bango = Column(Text)
    sales_code = Column(Text)
    sales_nen = Column(Integer)
    rakusatsu_gaku = Column(Integer)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class HorseNameOrigin(Base):
    __tablename__ = 'horse_name_origins'
    ketto_toroku_bango = Column(Text, primary_key=True)
    horse_name_origin = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class CourseInfo(Base):
    __tablename__ = 'course_info'
    id = Column(Text, primary_key=True)
    keibajo_code = Column(Text)
    track_code = Column(Text)
    kyori = Column(Integer)
    joken_code = Column(Text)
    record_time = Column(Float)
    standard_time = Column(Float)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class TcovHoten(Base):
    __tablename__ = 'tcov_hoten'
    id = Column(Text, primary_key=True)
    ketto_toroku_bango = Column(Text)
    chokyo_nen_tsuki_hi = Column(Text)
    chokyo_juni = Column(Integer)
    data_kubun = Column(Text)
    data = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)


class RcovHoten(Base):
    __tablename__ = 'rcov_hoten'
    id = Column(Text, primary_key=True)
    race_id = Column(Text)
    umaban = Column(Integer)
    data_kubun = Column(Text)
    data = Column(Text)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(),
                        onupdate=func.now(), nullable=False)
