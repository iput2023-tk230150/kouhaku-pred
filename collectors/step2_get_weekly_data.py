"""
Step 2: 週次データ取得スクリプト
================================
Step1で取得した曲リストから、各曲の週次日本チャートデータを取得

入力:
- data/raw/spotify/jp_songs_list.csv（Step1の出力）

出力:
- data/raw/spotify/jp_weekly_data.csv: 全曲の週次JPデータ
- data/raw/spotify/jp_yearly_stats.csv: 年別・アーティスト別集計

注意:
- 6000曲以上あるため、全曲取得には数時間かかる
- config.toml の top_n_songs で取得曲数を制限可能（テスト用）
"""

import sys
from pathlib import Path
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
import time
from datetime import date, timedelta
from typing import Any

from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    MofNCompleteColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from core.pipeline import DataPipeline, load_config


def get_fiscal_year_boundary(year: int) -> date:
    """
    指定年の11月第4週木曜日（年度境界日）を取得
    kworb.netは木曜始まりのため、木曜日を境界とする

    ビルボードジャパンの年間チャート集計期間に準拠:
    例: 2025年チャート = 2024年11月25日〜2025年11月23日
    """
    nov_1 = date(year, 11, 1)
    # 11月1日から最初の木曜日を探す（木曜=3）
    days_until_thursday = (3 - nov_1.weekday()) % 7
    first_thursday = nov_1 + timedelta(days=days_until_thursday)
    # 第4木曜日 = 最初の木曜日 + 3週間
    fourth_thursday = first_thursday + timedelta(weeks=3)
    return fourth_thursday


def parse_jp_value(value: str) -> tuple[int | None, int | None]:
    """
    JP値をパース: '1(26,291)' -> (1, 26291)
    '--' -> (None, None)
    """
    if not value or value == "--":
        return None, None

    match = re.match(r"(\d+)\(([0-9,]+)\)", value)
    if match:
        rank = int(match.group(1))
        streams = int(match.group(2).replace(",", ""))
        return rank, streams

    # 順位のみの場合
    if value.isdigit():
        return int(value), None

    return None, None


class Step2Pipeline(DataPipeline):
    """Step2: 週次データ取得パイプライン"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        super().__init__(config, data_dir)
        self.headers = {"User-Agent": config["network"]["user_agent"]}
        self.timeout = config["network"]["request_timeout"]
        self.interval = config["network"]["request_interval"]
        self.target_years = config["data_collection"]["target_years"]
        self.top_n = config["data_collection"]["top_n_songs"]
        self.raw_spotify_dir = data_dir / "raw" / "spotify"
        self.raw_spotify_dir.mkdir(parents=True, exist_ok=True)

    def get_output_files(self) -> list[Path]:
        return [
            self.raw_spotify_dir / "jp_weekly_data.csv",
            self.raw_spotify_dir / "jp_yearly_stats.csv",
        ]

    def check_dependencies(self) -> tuple[bool, list[str]]:
        input_file = self.raw_spotify_dir / "jp_songs_list.csv"
        if not input_file.exists():
            return False, [str(input_file)]
        return True, []

    def get_track_weekly_jp(self, track_id: str) -> list[dict]:
        """個別曲ページからWeekly JPデータを取得"""
        url = f"https://kworb.net/spotify/track/{track_id}.html"

        try:
            resp = requests.get(url, headers=self.headers, timeout=self.timeout)
            resp.encoding = "utf-8"

            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "html.parser")
            tables = soup.find_all("table")

            if len(tables) < 1:
                return []

            # Table 1 = Weekly
            weekly_table = tables[0]

            # ヘッダーからJPカラムのインデックスを特定
            header_row = weekly_table.find("tr")
            if not header_row:
                return []

            headers = [
                th.get_text(strip=True) for th in header_row.find_all(["th", "td"])
            ]

            jp_index = None
            for i, h in enumerate(headers):
                if h == "JP":
                    jp_index = i
                    break

            if jp_index is None:
                return []

            # データ行を処理（Total, Peakをスキップ）
            rows = weekly_table.find_all("tr")[1:]
            weekly_data = []

            for row in rows:
                cells = row.find_all("td")
                if len(cells) <= jp_index:
                    continue

                date_str = cells[0].get_text(strip=True)

                # Total, Peak行はスキップ
                if date_str in ["Total", "Peak"]:
                    continue

                # 日付形式チェック
                if not re.match(r"\d{4}/\d{2}/\d{2}", date_str):
                    continue

                jp_value = cells[jp_index].get_text(strip=True)
                rank, streams = parse_jp_value(jp_value)

                if rank is not None:
                    # 審査年度を計算（11月第4週木曜日を境界とする）
                    year_num = int(date_str[:4])
                    month_num = int(date_str[5:7])
                    day_num = int(date_str[8:10])

                    # 12月は常に翌年度、11月は境界判定
                    if month_num == 12:
                        fiscal_year = year_num + 1
                    elif month_num == 11:
                        current_date = date(year_num, month_num, day_num)
                        boundary = get_fiscal_year_boundary(year_num)
                        fiscal_year = (
                            year_num + 1 if current_date >= boundary else year_num
                        )
                    else:
                        fiscal_year = year_num

                    weekly_data.append(
                        {
                            "date": date_str,
                            "year": fiscal_year,
                            "jp_rank": rank,
                            "jp_streams": streams,
                        }
                    )

            return weekly_data

        except Exception:
            return []

    def execute(self) -> bool:
        """パイプライン実行"""
        print("=" * 60)
        print("Step 2: 週次データ取得")
        print("=" * 60)

        # 依存チェック
        ok, missing = self.check_dependencies()
        if not ok:
            print(f"エラー: 依存ファイルが見つかりません: {missing[0]}")
            print("先に step1_get_song_list.py を実行してください")
            return False

        input_file = self.raw_spotify_dir / "jp_songs_list.csv"
        df_songs = pd.read_csv(input_file)
        print(f"読み込み曲数: {len(df_songs)}")

        # 取得対象を制限
        if self.top_n:
            df_songs = df_songs.head(self.top_n)
            print(f"取得対象: 上位 {self.top_n} 曲")
        else:
            print(f"取得対象: 全 {len(df_songs)} 曲")

        # 既存データの読み込み（差分取得用）
        weekly_file = self.get_output_files()[0]
        df_existing = None
        existing_track_ids = set()
        last_date = None

        if weekly_file.exists():
            df_existing = pd.read_csv(weekly_file)
            existing_track_ids = set(df_existing["track_id"].unique())
            last_date = pd.to_datetime(df_existing["date"]).max()
            print("\n差分取得モード:")
            print(f"  既存曲数: {len(existing_track_ids)}")
            print(f"  最新日付: {last_date.strftime('%Y/%m/%d')}")

        all_weekly = []
        new_track_count = 0
        updated_track_count = 0

        print("\n取得開始...")
        print(f"対象年: {self.target_years}")
        print(f"リクエスト間隔: {self.interval}秒")
        print()

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
        ) as progress:
            task = progress.add_task("週次データ取得中", total=len(df_songs))

            for _, row in df_songs.iterrows():
                track_id = row["track_id"]
                artist = row["artist"]
                title = row["title"]

                is_new_track = track_id not in existing_track_ids

                weekly = self.get_track_weekly_jp(track_id)

                # 対象年のみフィルタ
                filtered_weekly = []
                for w in weekly:
                    if w["year"] in self.target_years:
                        # 差分取得: 既存曲は最新日付以降のみ
                        if not is_new_track and last_date:
                            w_date = pd.to_datetime(w["date"])
                            if w_date <= last_date:
                                continue

                        w["track_id"] = track_id
                        w["artist"] = artist
                        w["title"] = title
                        filtered_weekly.append(w)

                if filtered_weekly:
                    all_weekly.extend(filtered_weekly)
                    if is_new_track:
                        new_track_count += 1
                    else:
                        updated_track_count += 1

                # プログレスバー更新
                progress.update(
                    task,
                    advance=1,
                    description=f"取得中 (新規:{new_track_count} 更新:{updated_track_count})",
                )

                time.sleep(self.interval)

        print("\n取得完了:")
        print(f"  新規曲: {new_track_count}")
        print(f"  更新曲: {updated_track_count}")
        print(f"  新規レコード: {len(all_weekly)}")

        # 差分なしの場合は既存データのまま集計のみ
        if not all_weekly and df_existing is not None:
            print("新規データなし。既存データで集計を更新します。")
            df_weekly = df_existing
        elif not all_weekly:
            print("データが取得できませんでした")
            return False
        else:
            # 既存データとマージ
            df_new = pd.DataFrame(all_weekly)
            if df_existing is not None:
                df_weekly = pd.concat([df_existing, df_new], ignore_index=True)
                # 重複削除（date + track_id で一意）
                df_weekly = df_weekly.drop_duplicates(subset=["date", "track_id"])
                # 日付でソート
                df_weekly = df_weekly.sort_values(["date", "track_id"]).reset_index(
                    drop=True
                )
                print(f"マージ後レコード数: {len(df_weekly)}")
            else:
                df_weekly = df_new

            # 週次データ保存
            df_weekly.to_csv(weekly_file, index=False, encoding="utf-8-sig")
            print(f"保存: {weekly_file}")

        # 年別・アーティスト別集計
        yearly_stats = (
            df_weekly.groupby(["artist", "year"])
            .agg(
                weeks_on_chart=("date", "count"),
                total_streams=("jp_streams", "sum"),
                best_rank=("jp_rank", "min"),
                avg_rank=("jp_rank", "mean"),
                top10_weeks=("jp_rank", lambda x: (x <= 10).sum()),
                top1_weeks=("jp_rank", lambda x: (x == 1).sum()),
            )
            .reset_index()
        )

        stats_file = self.get_output_files()[1]
        yearly_stats.to_csv(stats_file, index=False, encoding="utf-8-sig")
        print(f"保存: {stats_file}")

        # サマリー表示
        print(f"\n{'=' * 60}")
        print("年別・アーティスト別 ストリーム数ランキング（2024年）")
        print("=" * 60)

        rank_2024 = (
            yearly_stats[yearly_stats["year"] == 2024]
            .sort_values("total_streams", ascending=False)
            .head(20)
        )

        for _, row in rank_2024.iterrows():
            streams = row["total_streams"]
            streams_str = f"{streams:,.0f}" if pd.notna(streams) else "N/A"
            print(
                f"  {row['artist']}: {streams_str} streams, Best: {row['best_rank']:.0f}"
            )

        return True


def main():
    """スタンドアロン実行用のエントリーポイント"""
    config = load_config()
    data_dir = Path(__file__).parent.parent / config["paths"]["data_dir"]

    pipeline = Step2Pipeline(config, data_dir)
    success = pipeline.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
