"""
Step 4: Googleトレンドデータ取得スクリプト
==========================================
pytrendsを使用してアーティストのGoogle検索トレンドデータを取得

入力:
- data/raw/kouhaku/kouhaku_artists.csv: 紅白出場者リスト（Step 3の出力）
- data/raw/spotify/jp_yearly_stats.csv: Spotify年別統計（Step 2の出力）

出力:
- data/raw/google_trends/artist_trends.csv: アーティスト×年別のトレンドデータ

対象アーティスト:
- 紅白出場者（過去〜現在）
- Spotifyデータに含まれるアーティスト
- 両者を統合してユニークなアーティストリストを作成

審査期間:
- ビルボードジャパン準拠: 11月第4週木曜日〜翌11月第3週水曜日
- 例: 紅白開催年の前年11月第4週木曜日〜開催年11月第4週木曜日の前日
"""

import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from pytrends.request import TrendReq
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from src.core.pipeline import DataPipeline, get_fiscal_year_boundary, load_config

# プロジェクトルートをパスに追加してutilsをインポート
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from utils.normalizer import ArtistNameNormalizer


def get_fiscal_year_period(fiscal_year: int) -> tuple[date, date]:
    """
    審査対象年度の開始日と終了日を取得

    Args:
        fiscal_year: 審査対象年（紅白開催年）

    Returns:
        (開始日, 終了日) のタプル
        例: fiscal_year の前年境界日から当年境界日の前日まで
    """
    # 前年の11月第4週木曜日が開始日
    start_date = get_fiscal_year_boundary(fiscal_year - 1)

    # 当年の11月第4週木曜日の前日（水曜日）が終了日
    end_date = get_fiscal_year_boundary(fiscal_year) - timedelta(days=1)

    return start_date, end_date


class Step4Pipeline(DataPipeline):
    """Step4: Googleトレンドデータ取得パイプライン"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        super().__init__(config, data_dir)

        # 設定読み込み
        self.google_trends_config = config.get("google_trends", {})
        self.enabled = self.google_trends_config.get("enabled", True)
        self.geo = self.google_trends_config.get("geo", "JP")
        self.request_interval = self.google_trends_config.get("request_interval", 30)
        self.max_retries = self.google_trends_config.get("max_retries", 3)
        self.checkpoint_interval = self.google_trends_config.get(
            "checkpoint_interval", 20
        )  # N件ごとに中間保存

        # 対象年
        self.target_years = config["data_collection"]["target_years"]

        # ディレクトリ設定
        self.raw_kouhaku_dir = data_dir / "raw" / "kouhaku"
        self.raw_spotify_dir = data_dir / "raw" / "spotify"
        self.raw_trends_dir = data_dir / "raw" / "google_trends"
        self.raw_trends_dir.mkdir(parents=True, exist_ok=True)
        self.mapping_dir = data_dir / "processed" / "mapping"

        # 名前正規化（旧字体→新字体変換用）
        self.normalizer = ArtistNameNormalizer()

        # Spotify名→日本語名のマッピングを読み込み
        self.name_mapping: dict[str, str] = {}
        mapping_file = self.mapping_dir / "final_mapping.csv"
        if mapping_file.exists():
            df_mapping = pd.read_csv(mapping_file)
            # spotify_name → kouhaku_name のマッピング
            self.name_mapping = dict(
                zip(df_mapping["spotify_name"], df_mapping["kouhaku_name"])
            )

    def get_output_files(self) -> list[Path]:
        return [self.raw_trends_dir / "artist_trends.csv"]

    def check_dependencies(self) -> tuple[bool, list[str]]:
        missing = []
        kouhaku_file = self.raw_kouhaku_dir / "kouhaku_artists.csv"
        spotify_file = self.raw_spotify_dir / "jp_yearly_stats.csv"

        if not kouhaku_file.exists():
            missing.append(str(kouhaku_file))
        if not spotify_file.exists():
            missing.append(str(spotify_file))

        if missing:
            return False, missing
        return True, []

    def get_timeframe_for_year(self, fiscal_year: int) -> str | None:
        """
        審査対象年度の期間をpytrends形式で返す

        Args:
            fiscal_year: 審査対象年（紅白開催年）

        Returns:
            pytrendsのtimeframe形式の文字列、未来期間はNone
        """
        start_date, end_date = get_fiscal_year_period(fiscal_year)
        today = date.today()

        # 開始日が未来の場合はスキップ
        if start_date > today:
            return None

        # 終了日が未来の場合は今日までに調整
        if end_date > today:
            end_date = today

        return f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"

    def get_trends_for_artist(
        self, pytrends: TrendReq, artist: str, fiscal_year: int
    ) -> dict | None:
        """
        アーティストの指定審査年度のGoogleトレンドデータを取得

        基準キーワード「音楽」と比較して相対的な検索量を算出。
        これによりアーティスト間の比較が可能になる。

        Args:
            pytrends: TrendReqインスタンス
            artist: アーティスト名
            fiscal_year: 審査対象年（紅白開催年）

        Returns:
            トレンドデータの辞書、取得失敗時はNone
        """
        timeframe = self.get_timeframe_for_year(fiscal_year)
        if timeframe is None:
            return None

        # 基準キーワード（アーティスト間比較用）
        baseline_keyword = "音楽"

        # 英語名→日本語名に変換（マッピングがあれば）
        japanese_name = self.name_mapping.get(artist, artist)

        # 旧字体→新字体変換（Google Trendsは旧字体を認識しない場合がある）
        search_name = self.normalizer.normalize_for_search(japanese_name)

        for attempt in range(self.max_retries):
            try:
                # リクエスト構築（基準キーワードと同時取得で相対比較）
                pytrends.build_payload(
                    kw_list=[search_name, baseline_keyword],
                    cat=0,  # 全カテゴリ
                    timeframe=timeframe,
                    geo=self.geo,
                )

                # Interest Over Time取得
                df_interest = pytrends.interest_over_time()

                if df_interest.empty or search_name not in df_interest.columns:
                    return None

                # アーティストの値（検索名でカラムを参照）
                artist_values = df_interest[search_name].values

                # 基準キーワードに対する相対値を計算
                if baseline_keyword in df_interest.columns:
                    baseline_values = df_interest[baseline_keyword].values
                    baseline_avg = float(baseline_values.mean())
                    # 基準キーワードの平均が0の場合は相対値を0とする
                    if baseline_avg > 0:
                        relative_interest = (
                            float(artist_values.mean()) / baseline_avg * 100
                        )
                    else:
                        relative_interest = 0.0
                else:
                    relative_interest = 0.0

                return {
                    "trend_avg_interest": float(artist_values.mean()),
                    "trend_peak_interest": float(artist_values.max()),
                    "trend_volatility": float(artist_values.std()),
                    "trend_relative_interest": round(relative_interest, 2),
                    "has_trends_data": 1,
                }

            except Exception as e:
                wait_time = self.request_interval * (2**attempt)
                if attempt < self.max_retries - 1:
                    print(f"    リトライ {attempt + 1}/{self.max_retries}: {e}")
                    time.sleep(wait_time)
                else:
                    print(f"    取得失敗: {artist} ({fiscal_year}年) - {e}")
                    return None

        return None

    def _save_checkpoint(
        self,
        output_file: Path,
        df_existing: pd.DataFrame,
        results: list[dict],
        processed_count: int,
    ) -> None:
        """
        中間結果を保存

        Args:
            output_file: 出力ファイルパス
            df_existing: 既存データのDataFrame
            results: 今回取得した結果リスト
            processed_count: 処理済み件数
        """
        df_new = pd.DataFrame(results)

        if not df_existing.empty:
            df_checkpoint = pd.concat([df_existing, df_new], ignore_index=True)
            df_checkpoint = df_checkpoint.drop_duplicates(
                subset=["artist", "year"], keep="last"
            ).reset_index(drop=True)
        else:
            df_checkpoint = df_new

        df_checkpoint.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\n  [チェックポイント] {processed_count}件処理済み、保存完了")

    def execute(self, retry_failed: bool = False) -> bool:
        """
        パイプライン実行

        Args:
            retry_failed: Trueの場合、has_trends_data=0のデータのみ再取得
        """
        # 有効化チェック
        if not self.enabled:
            print("\nGoogleトレンドデータ取得は無効化されています")
            print("config.toml の [google_trends] enabled = true で有効化できます")
            return True

        # 依存チェック
        ok, missing = self.check_dependencies()
        if not ok:
            print("エラー: 依存ファイルが見つかりません:")
            for f in missing:
                print(f"  - {f}")
            print("先に step1, step3 を実行してください")
            return False

        # ========== [1] データ読み込み ==========
        print("\n[1] データ読み込み")

        # 紅白出場者を読み込み
        kouhaku_file = self.raw_kouhaku_dir / "kouhaku_artists.csv"
        df_kouhaku = pd.read_csv(kouhaku_file)
        kouhaku_artists = set(df_kouhaku["artist"].unique())
        print(f"  紅白出場者: {len(kouhaku_artists)}組")

        # Spotifyデータのアーティストを読み込み
        spotify_file = self.raw_spotify_dir / "jp_yearly_stats.csv"
        df_spotify = pd.read_csv(spotify_file)
        spotify_artists = set(df_spotify["artist"].unique())
        print(f"  Spotifyアーティスト: {len(spotify_artists)}組")

        # 両方を統合してユニークなアーティストリストを作成
        all_artists = kouhaku_artists | spotify_artists
        artists = sorted(list(all_artists))
        print(f"  統合後（重複除去）: {len(artists)}組")
        print(f"  対象年: {self.target_years}")

        # 審査期間の表示
        print("\n  審査対象期間（ビルボードジャパン準拠）:")
        today = date.today()
        for year in self.target_years[-3:]:  # 直近3年分を表示
            start, end = get_fiscal_year_period(year)
            if start <= today:
                actual_end = min(end, today)
                status = "（部分データ）" if end > today else ""
                print(f"    {year}年: {start} 〜 {actual_end} {status}")
            else:
                print(f"    {year}年: （未来のため取得不可）")

        # ========== [2] 既存データの確認 ==========
        print("\n[2] 既存データの確認")

        output_file = self.get_output_files()[0]
        existing_pairs = set()
        failed_pairs = set()
        current_year = datetime.now().year

        if output_file.exists():
            df_existing = pd.read_csv(output_file)
            # 今年のデータは毎回更新（部分データのため）
            df_existing = df_existing[df_existing["year"] != current_year]

            # 失敗したペア（has_trends_data=0）を抽出
            df_failed = df_existing[df_existing["has_trends_data"] == 0]
            failed_pairs = set(zip(df_failed["artist"], df_failed["year"].astype(int)))

            # 成功したペアのみを既存として扱う
            df_success = df_existing[df_existing["has_trends_data"] == 1]
            existing_pairs = set(
                zip(df_success["artist"], df_success["year"].astype(int))
            )
            print(f"  既存データ（成功）: {len(existing_pairs)}件")
            print(f"  既存データ（失敗）: {len(failed_pairs)}件")

            if retry_failed:
                print("  → 失敗データを再取得対象に含めます")
                # 失敗データを除外して保持
                df_existing = df_success
        else:
            df_existing = pd.DataFrame()
            print("  既存データなし（新規作成）")

        # ========== [3] 取得対象の決定 ==========
        print("\n[3] 取得対象の決定")

        # 全組み合わせから既存を除外（取得可能な年のみ）
        fetchable_years = [
            y for y in self.target_years if self.get_timeframe_for_year(y) is not None
        ]
        all_pairs = [(a, y) for a in artists for y in fetchable_years]

        if retry_failed:
            # 失敗データのみ再取得
            pairs_to_fetch = [p for p in all_pairs if p in failed_pairs]
        else:
            # 新規のみ取得（成功済みをスキップ、失敗済みもスキップ）
            pairs_to_fetch = [
                p
                for p in all_pairs
                if p not in existing_pairs and p not in failed_pairs
            ]

        print(f"  全組み合わせ: {len(all_pairs)}件")
        print(f"  既存成功（スキップ）: {len(existing_pairs)}件")
        print(f"  既存失敗: {len(failed_pairs)}件")
        print(f"  取得対象: {len(pairs_to_fetch)}件")

        if not pairs_to_fetch:
            print("\n取得対象がありません")
            return True

        # 推定時間の表示
        estimated_time = len(pairs_to_fetch) * self.request_interval
        print(f"\n  推定所要時間: 約{estimated_time // 60}分{estimated_time % 60}秒")
        print(f"  中間保存間隔: {self.checkpoint_interval}件ごと")

        # ========== [4] Googleトレンドデータ取得 ==========
        print("\n[4] Googleトレンドデータ取得")

        # pytrendsインスタンス作成
        pytrends = TrendReq(
            hl="ja-JP",
            tz=540,
            requests_args={
                "headers": {
                    "Cookie": "NID=527=xYZQD7nDrGV1VwUh7wu5myqgL34NhoH8oA3zpQtw3sJez_9wbCRnv9h34swxsSR5xzAZIEmTc0D4s6p7pDEACYokpqqWSEmLT-8zqo375UBIE4eFRaPXiWhmKFoS6_YOwZeEHDbRxf2rm1JW_zoCNXjeD-ylalvkoK4oxCJZZRsYuRErV_a0RmsiKKVWoUl8M1sVLtS9fkCwIVbQ4AEilDcCaku9O2puF7LSOiNoj_aLGzOKTDORamxfRMjNLyNO5nWBw5GqAFkU-x5OnZPXSgL5ZQwd6Ak7qMR57uSsHNaXc9FRPTXOA9pHeg1VFqYU_zoPnG9MelGo-AJ7w3PiyVqy22WFBDOZLNQBn8JJyOz5zwmP_xc4e625pkTBm6RxIy6zdn4iduGjWNvOvXdAJt97GagDcFBauHEoyg4q3gzBDXFQ4VzoERwGxu3BBDEnN0PDJ7gdmc6GbdOGlMgtMgMI4oa4TG2nGpgQMZBHAmY8Gd3Y5eA6aYQHKttkyVCkAycKIR7XLwGU6QBDPcUvfigfcNF42jsCtWLAJq_E-juSQgh__xWJ6YFiawcV50J6jv1sKIgtW16qU6A692C76UyLmE4zIMU8MJNjMQvlyB3bbLhvb0jvbcSCb7s3kSqHJrt49RKHsKom7BjAvs7XqrQwbIw2hWJM0uzQ0gWwe6Rz1oFvt32jeq-2Hh-3S8rvVhi_d11Fv8EfDje0zWrO6sq1qD0Xet4kskEFAGU3nD8RVNi0M_vhIugwAMYBUDEy87aPyHji6ixhNIZWOBJ13g8TANMUxxzR3m61k7txz1TSj7x8a-fO0OqNsun1VcKlZe8_xIQns-UO4xRNU-CKGAILuA3Tanyq-xphPw-XtYvu3ecXHoobRxvXwY2qh5zQgXC5mcPXWpQzIJVYor9A-9MFiWiri7mu97CaPGorFQUEAkQgW5XvucMp6muxch_Tqe7MhYf1jh60Ryd-f2N_PYUVme72IhT9SE8Hk4LdJxtnXpzoOaU3AGlIWQhhT35xDu66eIcrv92K7Ihz4EP7yKsc9B8EbYSeSbzGJ_GchB2Rvg51ZtB2v9CBA6PJdCM4kXCditjyyhaR6vKx3Vh1KziM7DeFF4ZQ6raJK0gxvFw82nNa7npVpNZnroOF82CLHVVamRpKfAt5P8PqYRaKQeqcNPWAsRig3Ol8xo8N4GL48QfUeGCcZ_kR7l4G5IEJ3OZy4hpYwTIwpQAL4UFNfY4ZrhqtYfoImb0hXwu0Xqvzo_3UFafz83Z0D4NAFQttSPB1bU9Kd-1E7IPmYfiCNcsBX6IJSiZ-l19XGxknjt4QfdL7K0g2oebSKiHgN9rfPANKV632JkErGkDvD-cbcaSewFzwz2AjPu_9e0xc1YQ_TVIBaKeFQ2dSH2jzs9jhedcd8R-z87SfQeQJRpmFNhEN7lrsxJAYItmhVcdzPfdbNI_haDbJewwWqjyeWOsxLPHQfi7qxuQtd94ZeUQQCIdr1Z8PLouYGPWluCRdfj7SlUdsmVBZx8Dodpbq_XvoHFhN8kCRxqlpZURup58jWmPOqKS8TgiplKhXveW0ZhqLFvyEC7Fiz1cMJyji2aIL6qVHR7fVim0OCghdQSuonK3SSyoc9adyPZwo9GWJ-Vpmt1BUDo7Hs7iSL8NUq4c0ijNXx6WR8XZhwXUw8f5viSGHjI5G2uvUH4r_5OMPzBIMRmK_-juGkHP91J5V-LwxaRtUr7c8KCFdQm4j2bg5xBEPhe6dDQPGXUL7JU5XL6Ps70KbXEdsvuWDdfnE8kAbZ6qV6c_LEQKvD09pAuXKeYQU_m8Ngcs9XRs3IYTFO4FDLCvIOFPmdEeBACXbgZkcqXEKBg5x1VNET4tSSlQ8yFQnXMS0MRMYDTIIieg90IOMu7BA8hDObE8vQFdIXIK0ls6C6XxlkiphM_6AdTSUmEMC1pnvyK_uRz2q3Yk4wy_cngza413Kvb30c1zfL6lpb04DqMd6_ycfvpjld10tf4Cvmj1VHoRWcb4uHw5aiW4VM9NU-hZWZ-wSrpPyP3LtJ_OgDmDW5_PkR2U4Bwt7dsF_GhdyziC-XgUrYxbijI664ijDmyzK3l4ZWO3An0AYnjvNJoAXTT_iOZ68MbTwjLeWdiDrePe58BZ9Ik8a-WweJNvqNeiPEaYeKGOnd8MJwPU11Ph5xzoqpo31SPmtQf10btjtMKkUBc_2iBsoEsL_kNH24l7lVoTP6oDa7g52ho6wYqKYZ0nb6YLS-1Wfibq0TJsC1xjs4vBtRiDs2KdhhnY6SfY8H0Afs4-xGaYL6QtT34X313JOnjvoh1NDY0Wclv250VMcX_rV3RUuEtRjpQCFV2PISpJQO2nSURUclNYKdDQwuFBeq7VBtk7H27CKjblyVJKoGsC2vJrz4HNqEm5U3MdfVdmHiZ6Ep75FM2qG31Kr33LbFtGizKXm0E5GBf558WL02C2q2JIW9mm-lLUB_OW7RXaWAezruwF1jFW_kuZJ2LewmSp7rSW5ZcV9Od_JAJtxqFRsruHc7Kj5MxQQ3f_ge7pLv__KWjK7ylHsYi_QmMkcJz1tJHCQ9FidUqau0ronA0qQS5S7GuI8__ie8o2SpqCCgUNBdi3tzqx5RzE5mPufJEXV4wDdwr9x8_E0SoZb3eghlHS6jpF2qRAiWc4zt36YkZ4APWCUEUJc8pKqUgFg1tl-gzcdbty7EmyNK7rmIyotfxMr0ipuvkx75yxhechEhMFWhFSNiw"
                }
            },
        )

        results = []
        success_count = 0
        fail_count = 0
        last_checkpoint = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
        ) as progress:
            task = progress.add_task("トレンド取得中", total=len(pairs_to_fetch))

            for idx, (artist, year) in enumerate(pairs_to_fetch):
                progress.update(task, description=f"{artist} ({year}年)")

                # トレンドデータ取得
                trend_data = self.get_trends_for_artist(pytrends, artist, year)

                if trend_data:
                    results.append(
                        {
                            "artist": artist,
                            "year": year,
                            **trend_data,
                        }
                    )
                    success_count += 1
                else:
                    # データなしの場合もレコードを作成（has_trends_data=0）
                    results.append(
                        {
                            "artist": artist,
                            "year": year,
                            "trend_avg_interest": 0,
                            "trend_peak_interest": 0,
                            "trend_volatility": 0,
                            "trend_relative_interest": 0,
                            "has_trends_data": 0,
                        }
                    )
                    fail_count += 1

                progress.advance(task)

                # 中間保存（checkpoint_interval件ごと）
                processed_count = idx + 1
                if (
                    processed_count - last_checkpoint >= self.checkpoint_interval
                    and results
                ):
                    self._save_checkpoint(
                        output_file, df_existing, results, processed_count
                    )
                    last_checkpoint = processed_count

                # レート制限対策
                time.sleep(self.request_interval)

        # ========== [5] 結果の保存 ==========
        print("\n[5] 結果の保存")

        df_new = pd.DataFrame(results)

        # 既存データとマージ
        if not df_existing.empty:
            df_all = pd.concat([df_existing, df_new], ignore_index=True)
            # 重複除去（新しいデータを優先）
            df_all = df_all.drop_duplicates(
                subset=["artist", "year"], keep="last"
            ).reset_index(drop=True)
        else:
            df_all = df_new

        # 保存
        df_all.to_csv(output_file, index=False, encoding="utf-8-sig")

        print(f"\n{'=' * 60}")
        print(f"保存: {output_file}")
        print(f"  総レコード数: {len(df_all)}件")
        print(f"  今回取得: 成功 {success_count}件, 失敗 {fail_count}件")

        # ========== サマリー ==========
        print(f"\n{'=' * 60}")
        print("データサマリー")
        print("=" * 60)

        print("\n--- 年別データ件数 ---")
        print(df_all.groupby("year").size())

        print("\n--- トレンドデータ有無 ---")
        print(df_all["has_trends_data"].value_counts())

        # トレンド興味度が高いアーティスト（最新年）
        latest_year = df_all["year"].max()
        df_latest = df_all[df_all["year"] == latest_year].sort_values(
            "trend_avg_interest", ascending=False
        )
        if not df_latest.empty:
            print(f"\n--- {latest_year}年 トレンド興味度 Top 10 ---")
            for i, row in df_latest.head(10).iterrows():
                print(f"  {row['artist']:25s}: avg={row['trend_avg_interest']:.1f}")

        return True


def main():
    """スタンドアロン実行用のエントリーポイント"""
    import argparse

    parser = argparse.ArgumentParser(description="Google Trendsデータ取得")
    parser.add_argument(
        "-r",
        "--retry-failed",
        action="store_true",
        help="has_trends_data=0のデータのみ再取得",
    )
    args = parser.parse_args()

    config = load_config()
    data_dir = Path(__file__).parent.parent.parent / config["paths"]["data_dir"]

    pipeline = Step4Pipeline(config, data_dir)
    success = pipeline.execute(retry_failed=args.retry_failed)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
