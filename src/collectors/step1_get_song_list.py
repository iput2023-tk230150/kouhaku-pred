"""
Step 1: 曲リスト取得スクリプト
==============================
kworb.net Japan Daily Totalsページから曲リスト（Track ID含む）を取得

出力:
- data/raw/spotify/jp_songs_list.csv: 曲リスト（track_id, artist, title, total等）
"""

import sys
from pathlib import Path
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
from typing import Any

from src.core.pipeline import DataPipeline, load_config


def clean_number(value: str | None) -> int:
    """数値文字列をintに変換"""
    if not value:
        return 0
    cleaned = re.sub(r"[^\d]", "", str(value))
    return int(cleaned) if cleaned else 0


class Step1Pipeline(DataPipeline):
    """Step1: 曲リスト取得パイプライン"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        super().__init__(config, data_dir)
        self.url = config["network"]["urls"]["kworb_jp_daily"]
        self.headers = {"User-Agent": config["network"]["user_agent"]}
        self.timeout = config["network"]["request_timeout"]
        self.raw_spotify_dir = data_dir / "raw" / "spotify"
        self.raw_spotify_dir.mkdir(parents=True, exist_ok=True)

    def get_output_files(self) -> list[Path]:
        return [self.raw_spotify_dir / "jp_songs_list.csv"]

    def fetch_song_list(self) -> list[dict]:
        """
        kworb.netから曲リストを取得

        Returns:
            曲情報の辞書のリスト
        """
        print(f"取得中: {self.url}")
        resp = requests.get(self.url, headers=self.headers, timeout=self.timeout)
        resp.encoding = "utf-8"
        print(f"ステータス: {resp.status_code}")

        if resp.status_code != 200:
            print("ページ取得失敗")
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        table = soup.find("table")

        if not table:
            print("テーブルが見つかりません")
            return []

        rows = table.find_all("tr")[1:]  # ヘッダースキップ
        print(f"総行数: {len(rows)}")

        songs = []

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue

            try:
                # Cell 0: アーティスト-曲名（リンク付き）
                cell0 = cells[0]
                links = cell0.find_all("a")

                if len(links) < 2:
                    continue

                artist_link = links[0]
                track_link = links[1]

                artist = artist_link.get_text(strip=True)
                title = track_link.get_text(strip=True)

                # Track ID抽出: ../track/XXXXX.html -> XXXXX
                track_href = track_link.get("href", "")
                track_id_match = re.search(r"/track/([^.]+)\.html", track_href)
                track_id = track_id_match.group(1) if track_id_match else ""

                # Artist ID抽出
                artist_href = artist_link.get("href", "")
                artist_id_match = re.search(r"/artist/([^.]+)\.html", artist_href)
                artist_id = artist_id_match.group(1) if artist_id_match else ""

                # その他のセル
                days = clean_number(cells[1].get_text(strip=True))
                t10 = clean_number(cells[2].get_text(strip=True))
                peak = clean_number(cells[3].get_text(strip=True))
                pk_streams = clean_number(cells[5].get_text(strip=True))
                total = clean_number(cells[6].get_text(strip=True))

                songs.append(
                    {
                        "track_id": track_id,
                        "artist_id": artist_id,
                        "artist": artist,
                        "title": title,
                        "days": days,
                        "t10": t10,
                        "peak": peak,
                        "pk_streams": pk_streams,
                        "total": total,
                    }
                )

            except Exception:
                continue

        print(f"パース完了: {len(songs)}曲")
        return songs

    def execute(self) -> bool:
        """パイプライン実行"""
        # データ取得
        songs = self.fetch_song_list()

        if not songs:
            print("データが取得できませんでした")
            return False

        # DataFrame作成
        df = pd.DataFrame(songs)

        # 保存
        output_file = self.get_output_files()[0]
        df.to_csv(output_file, index=False, encoding="utf-8-sig")
        print(f"\n保存: {output_file} ({len(df)}曲)")

        # サマリー表示
        print(f"\n{'=' * 60}")
        print("上位20曲（Total順）")
        print("=" * 60)
        top20 = df.nlargest(20, "total")[["artist", "title", "peak", "total"]]
        top20["total"] = top20["total"].apply(lambda x: f"{x:,}")
        print(top20.to_string(index=False))

        # アーティスト別集計
        print(f"\n{'=' * 60}")
        print("アーティスト別曲数（上位20）")
        print("=" * 60)
        artist_counts = (
            df.groupby("artist")
            .agg(song_count=("title", "count"), total_streams=("total", "sum"))
            .sort_values("total_streams", ascending=False)
            .head(20)
        )
        artist_counts["total_streams"] = artist_counts["total_streams"].apply(
            lambda x: f"{x:,}"
        )
        print(artist_counts.to_string())

        return True


def main():
    """スタンドアロン実行用のエントリーポイント"""
    config = load_config()
    data_dir = Path(__file__).parent.parent.parent / config["paths"]["data_dir"]

    pipeline = Step1Pipeline(config, data_dir)
    success = pipeline.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
