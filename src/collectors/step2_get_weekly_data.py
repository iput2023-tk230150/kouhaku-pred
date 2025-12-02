"""
Step 2: 週次データ取得スクリプト
================================
Step1で取得した曲リストから、各曲の週次日本チャートデータを取得

入力:
- data/jp_songs_list.csv（Step1の出力）

出力:
- data/jp_weekly_data.csv: 全曲の週次JPデータ
- data/jp_yearly_stats.csv: 年別・アーティスト別集計

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
from typing import Any

from core.pipeline import DataPipeline, load_config


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

    def get_output_files(self) -> list[Path]:
        return [
            self.data_dir / "jp_weekly_data.csv",
            self.data_dir / "jp_yearly_stats.csv",
        ]

    def check_dependencies(self) -> tuple[bool, list[str]]:
        input_file = self.data_dir / "jp_songs_list.csv"
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
                    year = int(date_str[:4])
                    weekly_data.append(
                        {
                            "date": date_str,
                            "year": year,
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

        input_file = self.data_dir / "jp_songs_list.csv"
        df_songs = pd.read_csv(input_file)
        print(f"読み込み曲数: {len(df_songs)}")

        # 取得対象を制限
        if self.top_n:
            df_songs = df_songs.head(self.top_n)
            print(f"取得対象: 上位 {self.top_n} 曲")
        else:
            print(f"取得対象: 全 {len(df_songs)} 曲")

        all_weekly = []

        print(f"\n取得開始...")
        print(f"対象年: {self.target_years}")
        print(f"リクエスト間隔: {self.interval}秒")
        print()

        for idx, row in df_songs.iterrows():
            track_id = row["track_id"]
            artist = row["artist"]
            title = row["title"]

            # 進捗表示
            if (idx + 1) % 10 == 0:
                print(
                    f"  {idx + 1}/{len(df_songs)} 処理中... (取得データ: {len(all_weekly)}件)"
                )

            weekly = self.get_track_weekly_jp(track_id)

            # 対象年のみフィルタ
            for w in weekly:
                if w["year"] in self.target_years:
                    w["track_id"] = track_id
                    w["artist"] = artist
                    w["title"] = title
                    all_weekly.append(w)

            time.sleep(self.interval)

        print(f"\n取得完了: {len(all_weekly)} レコード")

        if not all_weekly:
            print("データが取得できませんでした")
            return False

        # DataFrame作成
        df_weekly = pd.DataFrame(all_weekly)

        # 週次データ保存
        weekly_file = self.get_output_files()[0]
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
        print(f"\n{'='*60}")
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
    data_dir = Path(__file__).parent.parent.parent / config["paths"]["data_dir"]

    pipeline = Step2Pipeline(config, data_dir)
    success = pipeline.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
