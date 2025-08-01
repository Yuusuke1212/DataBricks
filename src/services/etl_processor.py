import logging
import pandas as pd
import json
import queue
import threading
import time
from typing import Dict, List
from PyQt5.QtCore import QObject, pyqtSignal as Signal


class EtlDataPipeline(QObject):
    """
    ETLとDB格納のプロデューサー・コンシューマーモデル実装
    データ取得とDB格納処理を並列化してパフォーマンスを向上させる
    """

    # シグナル定義
    item_processed = Signal(str, int)  # data_spec, processed_count
    pipeline_finished = Signal()
    pipeline_error = Signal(str)

    def __init__(self, etl_processor, db_manager, max_queue_size: int = 1000):
        super().__init__()
        self.etl_processor = etl_processor
        self.db_manager = db_manager
        self.data_queue = queue.Queue(maxsize=max_queue_size)
        self.consumer_thread = None
        self.is_running = False
        self.is_cancelled = False
        self.processed_count = 0

    def start_pipeline(self, etl_rule: dict = None):
        """
        パイプラインを開始する
        Args:
            etl_rule: 使用するETLルール
        """
        if self.is_running:
            logging.warning("パイプラインは既に実行中です。")
            return

        self.is_running = True
        self.is_cancelled = False
        self.processed_count = 0
        self.etl_rule = etl_rule or {}

        # コンシューマースレッドを開始
        self.consumer_thread = threading.Thread(
            target=self._consumer_worker, daemon=True)
        self.consumer_thread.start()

        logging.info("ETL パイプラインを開始しました。")

    def add_data(self, data_spec: str, raw_data: str):
        """
        パイプラインにデータを追加する（プロデューサー側）
        Args:
            data_spec: データ種別
            raw_data: 生データ
        """
        if not self.is_running or self.is_cancelled:
            return

        try:
            # タイムアウト付きでキューに追加
            self.data_queue.put((data_spec, raw_data), timeout=5.0)
        except queue.Full:
            logging.warning("データキューが満杯です。データをスキップします。")
        except Exception as e:
            logging.error(f"データ追加中にエラーが発生: {e}")

    def finish_production(self):
        """
        データ生成が完了したことを通知する
        """
        if self.is_running:
            # 終了マーカーをキューに追加
            self.data_queue.put((None, None))
            logging.info("データ生成完了マーカーをキューに追加しました。")

    def cancel_pipeline(self):
        """
        パイプラインをキャンセルする
        """
        logging.info("ETL パイプラインのキャンセルを要求します。")
        self.is_cancelled = True

        # キューをクリア
        while not self.data_queue.empty():
            try:
                self.data_queue.get_nowait()
            except queue.Empty:
                break

        # 終了マーカーを追加してコンシューマーを停止
        self.data_queue.put((None, None))

    def _process_batch(self, batch_data: Dict[str, List[str]]):
        """
        バッチデータを処理する
        Args:
            batch_data: data_spec -> [raw_data_list] の辞書
        """
        import time
        batch_start_time = time.time()
        total_records = sum(len(records) for records in batch_data.values())

        logging.info("=== バッチ処理開始 ===")
        logging.info(
            f"バッチサイズ: {total_records} レコード, データ種別数: {len(batch_data)}")
        for data_spec, records in batch_data.items():
            logging.info(f"  - {data_spec}: {len(records)} レコード")

        for data_spec, raw_data_list in batch_data.items():
            if self.is_cancelled:
                logging.info("バッチ処理がキャンセルされました。")
                break

            try:
                spec_start_time = time.time()
                logging.info(
                    f"データ種別 '{data_spec}' の ETL処理開始: {len(raw_data_list)} レコード")

                # ETL処理
                transformed_dfs = self.etl_processor.transform(
                    raw_data_list, data_spec, rule=self.etl_rule
                )

                etl_end_time = time.time()
                etl_duration = etl_end_time - spec_start_time

                if not transformed_dfs:
                    logging.info(
                        f"データ種別 '{data_spec}': 変換対象データなし (処理時間: {etl_duration:.2f}秒)")
                    continue

                logging.info(f"データ種別 '{data_spec}': ETL変換完了 - {len(transformed_dfs)} テーブル "
                             f"(処理時間: {etl_duration:.2f}秒)")

                # DB格納
                db_start_time = time.time()
                total_inserted = 0
                for table_name, df in transformed_dfs.items():
                    if self.is_cancelled:
                        break

                    insert_start_time = time.time()
                    self.db_manager.bulk_insert(table_name, df)
                    insert_duration = time.time() - insert_start_time

                    total_inserted += len(df)
                    logging.info(f"  テーブル '{table_name}': {len(df)} 件挿入完了 "
                                 f"(処理時間: {insert_duration:.2f}秒, "
                                 f"速度: {len(df)/insert_duration:.1f} レコード/秒)")

                db_duration = time.time() - db_start_time
                spec_total_duration = time.time() - spec_start_time

                logging.info(f"データ種別 '{data_spec}' 完了: 総挿入件数 {total_inserted}, "
                             f"DB格納時間: {db_duration:.2f}秒, 総処理時間: {spec_total_duration:.2f}秒")

                # 処理完了を通知
                self.processed_count += len(raw_data_list)
                self.item_processed.emit(data_spec, len(raw_data_list))

            except Exception as e:
                logging.error(f"データ種別 '{data_spec}' のバッチ処理でエラー発生: {e}")
                logging.error(f"  - 処理対象レコード数: {len(raw_data_list)}")
                logging.error(f"  - エラー詳細: {str(e)}")
                self.pipeline_error.emit(f"バッチ処理エラー ({data_spec}): {e}")

        batch_duration = time.time() - batch_start_time
        logging.info("=== バッチ処理完了 ===")
        logging.info(f"バッチ処理時間: {batch_duration:.2f}秒, "
                     f"処理速度: {total_records/batch_duration:.1f} レコード/秒, "
                     f"累積処理件数: {self.processed_count}")

    def _consumer_worker(self):
        """
        コンシューマーワーカー（別スレッドで実行）
        キューからデータを取得してETL・DB格納処理を実行
        """
        logging.info("ETL コンシューマーワーカーを開始しました。")
        logging.info("  - バッチサイズ: 50 レコード")
        logging.info("  - 処理間隔: 2.0 秒")
        logging.info(f"  - キューサイズ上限: {self.data_queue.maxsize}")

        batch_data = {}  # data_spec -> [raw_data_list]
        batch_size = 50  # バッチサイズ
        last_process_time = time.time()
        process_interval = 2.0  # 2秒間隔で処理
        total_queued_items = 0

        try:
            while True:
                try:
                    # タイムアウト付きでキューからデータを取得
                    data_spec, raw_data = self.data_queue.get(timeout=1.0)

                    # 終了マーカーチェック
                    if data_spec is None:
                        logging.info("データ生成完了マーカーを受信しました。")
                        # 残りのバッチデータを処理
                        if batch_data:
                            logging.info("残りのバッチデータを処理します。")
                            self._process_batch(batch_data)
                        break

                    # キャンセルチェック
                    if self.is_cancelled:
                        logging.info("コンシューマーワーカーがキャンセルされました。")
                        break

                    # バッチデータに追加
                    if data_spec not in batch_data:
                        batch_data[data_spec] = []
                    batch_data[data_spec].append(raw_data)
                    total_queued_items += 1

                    # 10件ごとにキュー状況をログ出力
                    if total_queued_items % 10 == 0:
                        logging.debug(f"キューから受信: 累計 {total_queued_items} アイテム, "
                                      f"現在のバッチサイズ: {sum(len(items) for items in batch_data.values())}")

                    # バッチサイズまたは時間間隔でバッチ処理を実行
                    total_items = sum(len(items)
                                      for items in batch_data.values())
                    current_time = time.time()

                    if (total_items >= batch_size or
                            (current_time - last_process_time) >= process_interval):

                        if batch_data:
                            logging.debug(f"バッチ処理トリガー: アイテム数={total_items}, "
                                          f"経過時間={current_time - last_process_time:.1f}秒")
                            self._process_batch(batch_data)
                            batch_data = {}
                            last_process_time = current_time

                except queue.Empty:
                    # タイムアウト時は蓄積されたバッチデータを処理
                    current_time = time.time()
                    if (batch_data and
                            (current_time - last_process_time) >= process_interval):
                        logging.debug("タイムアウト処理: バッチ処理を実行します。")
                        self._process_batch(batch_data)
                        batch_data = {}
                        last_process_time = current_time
                    continue

        except Exception as e:
            logging.error(f"コンシューマーワーカーでエラーが発生: {e}")
            logging.error(f"  - 処理済みアイテム数: {total_queued_items}")
            logging.error(
                f"  - 残バッチサイズ: {sum(len(items) for items in batch_data.values())}")
            self.pipeline_error.emit(str(e))
        finally:
            self.is_running = False
            logging.info(
                f"ETL コンシューマーワーカーを終了しました。総処理アイテム数: {total_queued_items}")
            self.pipeline_finished.emit()


class EtlProcessor:
    """
    JRA-VANから取得した生データを解析・変換し、
    データベースに格納可能なDataFrame形式に整形する責務を持つ。
    """

    # 全ての蓄積系レコード種別のスキーマ定義
    SPEC_DEFINITIONS = {
        # RA: レース詳細
        'RA': {
            'table_name': 'races',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [1, 'weather_code', 'str'],
                [8, 'data_create_date', 'str'],
                [4, 'kaisai_year', 'str'],
                [4, 'kaisai_month_day', 'str'],
                [2, 'keibajo_code', 'str'],
                [2, 'kaisai_kai', 'str'],
                [2, 'kaisai_nichi', 'str'],
                [2, 'race_bango', 'str'],
                [1, 'weekday_code', 'str'],
                [4, 'tokubetsu_race_bango', 'str'],
                [60, 'race_name_hon', 'str'],
                [60, 'race_name_fuku', 'str'],
                [60, 'race_name_kako', 'str'],
                [120, 'race_name_hon_eng', 'str'],
                [120, 'race_name_fuku_eng', 'str'],
                [120, 'race_name_kako_eng', 'str'],
                [20, 'race_name_ryaku_10', 'str'],
                [12, 'race_name_ryaku_6', 'str'],
                [6, 'race_name_ryaku_3', 'str'],
                [1, 'jusho_kubun', 'str'],
                [3, 'jusho_kai', 'str'],
                [1, 'grade_code', 'str'],
                [1, 'prev_grade_code', 'str'],
                [2, 'race_shubetsu_code', 'str'],
                [3, 'race_kigo_code', 'str'],
                [1, 'juryo_shubetsu_code', 'str'],
                [3, 'joken_code_2yo', 'str'],
                [3, 'joken_code_3yo', 'str'],
                [3, 'joken_code_4yo', 'str'],
                [3, 'joken_code_5yo', 'str'],
                [3, 'joken_code_saizyaku', 'str'],
                [60, 'race_name_chihou', 'str'],
                [4, 'kyori', 'int'],
                [4, 'prev_kyori', 'int'],
                [2, 'track_code', 'str'],
                [2, 'prev_track_code', 'str'],
                [2, 'course_kubun', 'str'],
                [2, 'prev_course_kubun', 'str'],
                [56, 'prize_money', 'str'],  # JSON格納推奨
                [40, 'prev_prize_money', 'str'],  # JSON格納推奨
                [24, 'added_prize', 'str'],  # JSON格納推奨
                [24, 'prev_added_prize', 'str'],  # JSON格納推奨
                [4, 'hassou_time', 'str'],
                [4, 'prev_hassou_time', 'str'],
                [2, 'toroku_tosu', 'int'],
                [2, 'shusso_tosu', 'int'],
                [2, 'nyusen_tosu', 'int'],
                [1, 'shiba_baba_code', 'str'],
                [1, 'dirt_baba_code', 'str'],
                [25, 'lap_times', 'str'],
                [4, 'shogai_mile_time', 'float'],
                [3, 'mae_3f', 'float'],
                [3, 'mae_4f', 'float'],
                [3, 'ato_3f', 'float'],
                [3, 'ato_4f', 'float'],
                [288, 'corner_pass_ranks', 'str'],  # JSON格納推奨
                [1, 'record_koshin_kubun', 'str'],
                [2, 'record_delimiter', 'str']
            ]
        },

        # SE: 馬毎レース情報
        'SE': {
            'table_name': 'race_results',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [4, 'kaisai_year', 'str'],
                [4, 'kaisai_month_day', 'str'],
                [2, 'keibajo_code', 'str'],
                [2, 'kaisai_kai', 'str'],
                [2, 'kaisai_nichi', 'str'],
                [2, 'race_bango', 'str'],
                [2, 'umaban', 'str'],
                [2, 'wakuban', 'str'],
                [10, 'blood_registration_number', 'str'],
                [36, 'horse_name', 'str'],
                [2, 'horse_symbol_code', 'str'],
                [1, 'sex_code', 'str'],
                [1, 'breed_code', 'str'],
                [2, 'color_code', 'str'],
                [2, 'age', 'int'],
                [1, 'belong_code', 'str'],
                [5, 'trainer_code', 'str'],
                [34, 'trainer_name_short', 'str'],
                [6, 'owner_code', 'str'],
                [64, 'owner_name', 'str'],
                [60, 'fukushoku_hyoji', 'str'],
                [60, 'reserved', 'str'],
                [3, 'futan_juryo', 'float'],
                [3, 'prev_futan_juryo', 'float'],
                [1, 'blinker_kubun', 'str'],
                [6, 'reserved_2', 'str'],
                [5, 'jockey_code', 'str'],
                [34, 'jockey_name_short', 'str'],
                [5, 'prev_jockey_code', 'str'],
                [34, 'prev_jockey_name_short', 'str'],
                [1, 'apprentice_code', 'str'],
                [1, 'prev_apprentice_code', 'str'],
                [3, 'horse_weight', 'int'],
                [1, 'weight_change_sign', 'str'],
                [3, 'weight_change', 'int'],
                [2, 'ijou_kubun_code', 'str'],
                [3, 'nyusen_juni', 'int'],
                [3, 'kakutei_chakujun', 'int'],
                [1, 'dochaku_kubun', 'str'],
                [1, 'dochaku_tosu', 'int'],
                [4, 'soha_time', 'float'],
                [3, 'chakusa_code', 'str'],
                [3, 'prev_chakusa_code_1', 'str'],
                [3, 'prev_chakusa_code_2', 'str'],
                [2, 'corner_1_rank', 'int'],
                [2, 'corner_2_rank', 'int'],
                [2, 'corner_3_rank', 'int'],
                [2, 'corner_4_rank', 'int'],
                [4, 'tansho_odds', 'float'],
                [2, 'tansho_ninki', 'int'],
                [8, 'kakutoku_honshokin', 'int'],
                [8, 'kakutoku_fukashokin', 'int'],
                [3, 'reserved_3', 'str'],
                [3, 'ato_3f', 'float'],
                [3, 'ato_4f', 'float'],
                [138, 'aiteuma_info', 'str'],  # JSON格納推奨
                [4, 'time_sa', 'float'],
                [1, 'record_koshin_kubun', 'str'],
                [1, 'mining_kubun', 'str'],
                [5, 'mining_soha_time', 'float'],
                [5, 'mining_yoso_juni', 'int'],
                [1, 'kyakushitsu_hantei', 'str'],
                [2, 'record_delimiter', 'str']
            ]
        },

        # HR: 払戻情報
        'HR': {
            'table_name': 'payouts',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [4, 'kaisai_year', 'str'],
                [4, 'kaisai_month_day', 'str'],
                [2, 'keibajo_code', 'str'],
                [2, 'kaisai_kai', 'str'],
                [2, 'kaisai_nichi', 'str'],
                [2, 'race_bango', 'str'],
                [2, 'toroku_tosu', 'int'],
                [2, 'shusso_tosu', 'int'],
                [1, 'tansho_flag', 'str'],
                [1, 'fukusho_flag', 'str'],
                [1, 'wakuren_flag', 'str'],
                [1, 'umaren_flag', 'str'],
                [1, 'wide_flag', 'str'],
                [1, 'umatan_flag', 'str'],
                [1, 'sanrenpuku_flag', 'str'],
                [1, 'sanrentan_flag', 'str'],
                [1, 'fukusho_key', 'str'],
                [1, 'wide_key', 'str'],
                [1, 'umaren_key', 'str'],
                [1, 'sanrenpuku_key', 'str'],
                [21, 'payout_tansho', 'str'],  # JSON格納推奨
                [63, 'payout_fukusho', 'str'],  # JSON格納推奨
                [21, 'payout_wakuren', 'str'],  # JSON格納推奨
                [21, 'payout_umaren', 'str'],  # JSON格納推奨
                [63, 'payout_wide', 'str'],  # JSON格納推奨
                [28, 'payout_umatan', 'str'],  # JSON格納推奨
                [28, 'payout_sanrenpuku', 'str'],  # JSON格納推奨
                [42, 'payout_sanrentan', 'str'],  # JSON格納推奨
                [2, 'record_delimiter', 'str']
            ]
        },

        # UM: 競走馬マスタ
        'UM': {
            'table_name': 'horses',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [10, 'blood_registration_number', 'str'],
                [1, 'horse_erase_flag', 'str'],
                [8, 'registration_date', 'str'],
                [8, 'erase_date', 'str'],
                [8, 'birth_date', 'str'],
                [36, 'horse_name', 'str'],
                [40, 'horse_kana', 'str'],
                [80, 'horse_name_eng', 'str'],
                [1, 'jra_facility_flag', 'str'],
                [19, 'reserved', 'str'],
                [2, 'horse_symbol_code', 'str'],
                [1, 'sex_code', 'str'],
                [1, 'breed_code', 'str'],
                [2, 'color_code', 'str'],
                [644, 'bloodline_info', 'str'],  # JSON格納推奨
                [1, 'belong_code', 'str'],
                [5, 'trainer_code', 'str'],
                [34, 'trainer_name', 'str'],
                [20, 'invite_area_name', 'str'],
                [8, 'breeder_code', 'str'],
                [72, 'breeder_name', 'str'],
                [20, 'origin_area_name', 'str'],
                [6, 'owner_code', 'str'],
                [64, 'owner_name', 'str'],
                [9, 'flat_base_prize_total', 'int'],
                [9, 'steeple_base_prize_total', 'int'],
                [9, 'flat_added_prize_total', 'int'],
                [9, 'steeple_added_prize_total', 'int'],
                [9, 'flat_earnings_total', 'int'],
                [9, 'steeple_earnings_total', 'int'],
                [488, 'all_race_results', 'str'],  # JSON格納推奨
                [20, 'running_style_tendency', 'str'],
                [12, 'reserved_2', 'str'],
                [5, 'total_races', 'int'],
                [2, 'record_delimiter', 'str']
            ]
        },

        # CK: 調教師マスタ (DUの代替)
        'CK': {
            'table_name': 'trainers',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [5, 'trainer_code', 'str'],
                [1, 'trainer_erase_flag', 'str'],
                [8, 'license_issue_date', 'str'],
                [8, 'license_erase_date', 'str'],
                [8, 'birth_date', 'str'],
                [34, 'trainer_name', 'str'],
                [30, 'trainer_kana', 'str'],
                [34, 'trainer_name_short', 'str'],
                [80, 'trainer_name_eng', 'str'],
                [1, 'sex_code', 'str'],
                [1, 'belong_code', 'str'],
                [20, 'invite_area_name', 'str'],
                [162, 'recent_grade_race_win', 'str'],  # JSON格納推奨
                [3477, 'yearly_results', 'str'],  # JSON格納推奨
                [2, 'record_delimiter', 'str']
            ]
        },

        # KS: 騎手マスタ
        'KS': {
            'table_name': 'jockeys',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [5, 'jockey_code', 'str'],
                [1, 'jockey_erase_flag', 'str'],
                [8, 'license_issue_date', 'str'],
                [8, 'license_erase_date', 'str'],
                [8, 'birth_date', 'str'],
                [34, 'jockey_name', 'str'],
                [30, 'jockey_kana', 'str'],
                [34, 'jockey_name_short', 'str'],
                [80, 'jockey_name_eng', 'str'],
                [1, 'sex_code', 'str'],
                [1, 'jockey_license_code', 'str'],
                [1, 'apprentice_code', 'str'],
                [1, 'belong_code', 'str'],
                [20, 'invite_area_name', 'str'],
                [5, 'belong_trainer_code', 'str'],
                [34, 'belong_trainer_name', 'str'],
                [162, 'first_ride_flat', 'str'],  # JSON格納推奨
                [162, 'first_win_flat', 'str'],  # JSON格納推奨
                [162, 'first_ride_steeple', 'str'],  # JSON格納推奨
                [162, 'first_win_steeple', 'str'],  # JSON格納推奨
                [162, 'recent_grade_race_win', 'str'],  # JSON格納推奨
                [3156, 'yearly_results', 'str'],  # JSON格納推奨
                [2, 'record_delimiter', 'str']
            ]
        },

        # O1: 単勝・複勝・枠連オッズ
        'O1': {
            'table_name': 'odds_tanpuku_waku',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [4, 'kaisai_year', 'str'],
                [4, 'kaisai_month_day', 'str'],
                [2, 'keibajo_code', 'str'],
                [2, 'kaisai_kai', 'str'],
                [2, 'kaisai_nichi', 'str'],
                [2, 'race_bango', 'str'],
                [8, 'announce_time', 'str'],
                [2, 'toroku_tosu', 'int'],
                [2, 'shusso_tosu', 'int'],
                [1, 'tansho_flag', 'str'],
                [1, 'fukusho_flag', 'str'],
                [1, 'wakuren_flag', 'str'],
                [1, 'fukusho_key', 'str'],
                [224, 'odds_tansho', 'str'],  # JSON格納推奨
                [236, 'odds_fukusho', 'str'],  # JSON格納推奨
                [324, 'odds_wakuren', 'str'],  # JSON格納推奨
                [11, 'total_votes_tansho', 'int'],
                [11, 'total_votes_fukusho', 'int'],
                [11, 'total_votes_wakuren', 'int'],
                [2, 'record_delimiter', 'str']
            ]
        },

        # O2: 馬連オッズ
        'O2': {
            'table_name': 'odds_umaren',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [4, 'kaisai_year', 'str'],
                [4, 'kaisai_month_day', 'str'],
                [2, 'keibajo_code', 'str'],
                [2, 'kaisai_kai', 'str'],
                [2, 'kaisai_nichi', 'str'],
                [2, 'race_bango', 'str'],
                [8, 'announce_time', 'str'],
                [2, 'toroku_tosu', 'int'],
                [2, 'shusso_tosu', 'int'],
                [1, 'umaren_flag', 'str'],
                [1989, 'odds_umaren', 'str'],  # JSON格納推奨
                [11, 'total_votes_umaren', 'int'],
                [2, 'record_delimiter', 'str']
            ]
        },

        # O3: ワイドオッズ
        'O3': {
            'table_name': 'odds_wide',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [4, 'kaisai_year', 'str'],
                [4, 'kaisai_month_day', 'str'],
                [2, 'keibajo_code', 'str'],
                [2, 'kaisai_kai', 'str'],
                [2, 'kaisai_nichi', 'str'],
                [2, 'race_bango', 'str'],
                [8, 'announce_time', 'str'],
                [2, 'toroku_tosu', 'int'],
                [2, 'shusso_tosu', 'int'],
                [1, 'wide_flag', 'str'],
                [2604, 'odds_wide', 'str'],  # JSON格納推奨
                [11, 'total_votes_wide', 'int'],
                [2, 'record_delimiter', 'str']
            ]
        },

        # O4: 馬単オッズ
        'O4': {
            'table_name': 'odds_umatan',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [4, 'kaisai_year', 'str'],
                [4, 'kaisai_month_day', 'str'],
                [2, 'keibajo_code', 'str'],
                [2, 'kaisai_kai', 'str'],
                [2, 'kaisai_nichi', 'str'],
                [2, 'race_bango', 'str'],
                [8, 'announce_time', 'str'],
                [2, 'toroku_tosu', 'int'],
                [2, 'shusso_tosu', 'int'],
                [1, 'umatan_flag', 'str'],
                [3978, 'odds_umatan', 'str'],  # JSON格納推奨
                [11, 'total_votes_umatan', 'int'],
                [2, 'record_delimiter', 'str']
            ]
        },

        # O5: 3連複オッズ
        'O5': {
            'table_name': 'odds_sanrenpuku',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [4, 'kaisai_year', 'str'],
                [4, 'kaisai_month_day', 'str'],
                [2, 'keibajo_code', 'str'],
                [2, 'kaisai_kai', 'str'],
                [2, 'kaisai_nichi', 'str'],
                [2, 'race_bango', 'str'],
                [8, 'announce_time', 'str'],
                [2, 'toroku_tosu', 'int'],
                [2, 'shusso_tosu', 'int'],
                [1, 'sanrenpuku_flag', 'str'],
                [12240, 'odds_sanrenpuku', 'str'],  # JSON格納推奨
                [11, 'total_votes_sanrenpuku', 'int'],
                [2, 'record_delimiter', 'str']
            ]
        },

        # O6: 3連単オッズ
        'O6': {
            'table_name': 'odds_sanrentan',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'data_create_date', 'str'],
                [4, 'kaisai_year', 'str'],
                [4, 'kaisai_month_day', 'str'],
                [2, 'keibajo_code', 'str'],
                [2, 'kaisai_kai', 'str'],
                [2, 'kaisai_nichi', 'str'],
                [2, 'race_bango', 'str'],
                [8, 'announce_time', 'str'],
                [2, 'toroku_tosu', 'int'],
                [2, 'shusso_tosu', 'int'],
                [1, 'sanrentan_flag', 'str'],
                [83332, 'odds_sanrentan', 'str'],  # JSON格納推奨
                [11, 'total_votes_sanrentan', 'int'],
                [2, 'record_delimiter', 'str']
            ]
        },

        # DU: 調教師データ（テスト互換用 - CKを推奨）
        'DU': {
            'table_name': 'trainers_test',
            'layout': [
                [2, 'record_spec_id', 'str'],
                [1, 'data_kubun', 'str'],
                [8, 'create_date', 'str'],
                [5, 'trainer_code', 'str'],
                [1, 'trainer_flag', 'str'],
                [8, 'trainer_name', 'str'],
                [16, 'trainer_name_kana', 'str'],
                [40, 'trainer_name_english', 'str'],
                [1, 'gender_code', 'str'],
                [1, 'east_west_code', 'str'],
                [60, 'trainer_info', 'str'],  # JSON格納
                [1, 'record_update_kubun', 'str'],
                [2, 'record_delimiter', 'str']
            ]
        }
    }

    @classmethod
    def get_spec(cls, record_id: str) -> dict | None:
        """SPEC_DEFINITIONSからスキーマ定義を取得"""
        return cls.SPEC_DEFINITIONS.get(record_id)

    def __init__(self):
        """コンストラクタ"""
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(message)s')

    def transform(self, raw_data_list: list, data_spec: str, rule: dict = None) -> dict[str, pd.DataFrame]:
        """
        生データのリストをデータ種別と指定されたルールに応じて変換し、
        テーブル名をキー、DataFrameを値とする辞書を返す。
        """
        if rule is None:
            rule = {}

        if not raw_data_list:
            return {}

        record_spec_id = raw_data_list[0][:2]  # 先頭2バイトがレコード種別

        spec = self.get_spec(record_spec_id)
        if spec is None:
            logging.warning(f"'{record_spec_id}' に対応する変換定義が見つかりません。")
            return {}

        table_name = spec['table_name']
        layout = spec['layout']

        parsed_records = []
        for raw_record in raw_data_list:
            try:
                # 改行コードなどを除去
                clean_record = raw_record.strip()
                # Shift-JISとしてバイト列にエンコード（エラーハンドリング強化）
                try:
                    record_bytes = clean_record.encode('cp932')
                except UnicodeEncodeError as e:
                    logging.warning(
                        f"Encoding error for record, using fallback: {e}")
                    # フォールバック: エラー文字を無視してエンコード
                    record_bytes = clean_record.encode(
                        'cp932', errors='ignore')

                record_data = {}
                current_pos = 0
                for length, name, _type in layout:
                    # バイト列からスライス
                    field_bytes = record_bytes[current_pos: current_pos + length]
                    # 再び文字列にデコードして前後の空白を除去（エラーハンドリング強化）
                    try:
                        field_str = field_bytes.decode('cp932').strip()
                    except UnicodeDecodeError as e:
                        logging.warning(
                            f"Decoding error for field {name}, using fallback: {e}")
                        # フォールバック: エラー文字を置換してデコード
                        field_str = field_bytes.decode(
                            'cp932', errors='replace').strip()

                    # 型変換とJSON対応
                    try:
                        if _type == 'int':
                            record_data[name] = int(
                                field_str) if field_str else None
                        elif _type == 'float':
                            record_data[name] = float(
                                field_str) if field_str else None
                        else:
                            # 複雑なデータ（払戻、オッズ、票数、マスタ情報）をJSON形式で格納
                            if self._is_json_field(name):
                                record_data[name] = self._parse_complex_field(
                                    field_str, name, record_spec_id)
                            else:
                                record_data[name] = field_str
                    except (ValueError, TypeError):
                        record_data[name] = None  # 変換失敗時はNone

                    current_pos += length
                parsed_records.append(record_data)

            except Exception as e:
                logging.error(
                    f"レコードのパース中にエラーが発生: {e}\nRecord: {raw_record[:100]}...")
                continue

        if not parsed_records:
            return {}

        df = pd.DataFrame(parsed_records)

        # ルールを適用
        if df.empty:
            return {table_name: df}

        # 1. カラム名のリネーム（Snake Caseへ）
        df.columns = [self.to_snake_case(col) for col in df.columns]

        # 2. ルールに基づくカラム除外
        target_table = rule.get("target_table")
        if target_table == table_name:
            ignored_columns = rule.get("ignored_columns", [])
            if ignored_columns:
                # 存在しないカラムを除外しようとするとエラーになるため、存在するカラムのみを対象とする
                cols_to_drop = [
                    col for col in ignored_columns if col in df.columns]
                df = df.drop(columns=cols_to_drop)
                logging.info(
                    f"ルール適用: テーブル '{table_name}' から {len(cols_to_drop)} 個のカラムを除外しました。")

        logging.info(f"'{record_spec_id}' のデータ変換が完了しました。{len(df)}件")
        return {table_name: df}

    def _is_json_field(self, field_name: str) -> bool:
        """JSONとして格納すべきフィールドかどうかを判定"""
        json_keywords = [
            'payback', 'odds', 'votes', 'pedigree', 'performance', 'prediction',
            'training', 'market_price', 'holder_info', 'jyusho_annnai',
            'win5_data', 'corner_pass_order', 'lap_time'
        ]
        return any(keyword in field_name.lower() for keyword in json_keywords)

    def _parse_complex_field(self, field_str: str, field_name: str, record_type: str) -> str:
        """複雑なフィールド（払戻、オッズ等）をJSON形式に変換"""
        if not field_str:
            return json.dumps({})

        try:
            # 基本的にはそのまま文字列として保存し、後で必要に応じてアプリケーション層で解析
            # ここでは複雑な解析は行わず、生データをJSON文字列として保存
            return json.dumps({"raw_data": field_str})
        except Exception as e:
            logging.warning(f"JSON変換エラー in {field_name}: {e}")
            return json.dumps({"raw_data": field_str, "error": str(e)})

    def to_snake_case(self, name):
        # 簡易的なスネークケース変換
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
