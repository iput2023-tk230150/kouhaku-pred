"""
Step 3: 紅白出場者リスト取得スクリプト
======================================
WikipediaのMediaWiki APIを使用して紅白歌合戦の出場者リストを取得

出力:
- data/raw/kouhaku/kouhaku_artists.csv: 年別出場者リスト（year, artist）
"""

import sys
from pathlib import Path
import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
from typing import Any

from core.pipeline import DataPipeline, load_config


class Step3Pipeline(DataPipeline):
    """Step3: 紅白出場者リスト取得パイプライン"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        super().__init__(config, data_dir)
        self.target_years = config["kouhaku"]["target_years"]
        self.api_url = config["network"]["urls"]["wikipedia_api"]
        self.headers = {"User-Agent": config["network"]["user_agent"]}
        self.interval = config["network"]["request_interval"]
        self.raw_kouhaku_dir = data_dir / "raw" / "kouhaku"
        self.raw_kouhaku_dir.mkdir(parents=True, exist_ok=True)

    def get_output_files(self) -> list[Path]:
        return [self.raw_kouhaku_dir / "kouhaku_artists.csv"]

    def get_kouhaku_page(self, kai_number: int) -> str | None:
        """
        MediaWiki APIで紅白歌合戦のページHTMLを取得

        Args:
            kai_number: 回数（例: 75）

        Returns:
            HTMLテキスト、取得失敗時はNone
        """
        title = f"第{kai_number}回NHK紅白歌合戦"

        params = {
            "action": "parse",
            "page": title,
            "format": "json",
            "prop": "text",
        }

        try:
            resp = requests.get(
                self.api_url, params=params, headers=self.headers, timeout=30
            )
            data = resp.json()

            if "parse" in data:
                return data["parse"]["text"]["*"]
            return None
        except Exception as e:
            print(f"  エラー: {e}")
            return None

    def parse_kouhaku_artists(self, html: str, year: int) -> list[dict]:
        """
        Wikipediaの紅白歌合戦ページから歌手名を抽出
        開催後（曲順・歌手名カラム形式）と開催前（紅組・白組横並び形式）の
        両方の構造に対応

        Args:
            html: WikipediaページのHTML
            year: 対象年

        Returns:
            アーティスト情報の辞書のリスト
        """
        soup = BeautifulSoup(html, "html.parser")

        # まず開催後形式（曲順・歌手名カラム）を試す
        artists = self._parse_post_broadcast_format(soup, year)

        # 取得できなければ開催前形式（紅組・白組横並び）を試す
        if not artists:
            artists = self._parse_pre_broadcast_format(soup, year)

        return artists

    def _parse_post_broadcast_format(
        self, soup: BeautifulSoup, year: int
    ) -> list[dict]:
        """
        開催後形式のパース（曲順・歌手名カラムを持つテーブル）
        """
        artists = []
        seen = set()

        tables = soup.find_all("table", class_="wikitable")

        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # ヘッダー行を確認
            header_cells = rows[0].find_all(["th", "td"])
            headers = [c.get_text(strip=True) for c in header_cells]

            # 「曲順」と「歌手名」カラムを探す
            order_idx = None
            singer_idx = None
            for i, h in enumerate(headers):
                if h == "曲順":
                    order_idx = i
                if h == "歌手名":
                    singer_idx = i

            if singer_idx is None or order_idx is None:
                continue

            # データ行を処理
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) <= max(singer_idx, order_idx):
                    continue

                # 曲順が数字かチェック（企画枠除外）
                order_text = cells[order_idx].get_text(strip=True)
                if not order_text.isdigit():
                    continue

                cell = cells[singer_idx]
                self._extract_artists_from_cell(cell, year, seen, artists)

        return artists

    def _parse_pre_broadcast_format(self, soup: BeautifulSoup, year: int) -> list[dict]:
        """
        開催前形式のパース（紅組・白組が横並びのテーブル）
        ヘッダーが「紅組」「白組」の2列構成
        """
        artists = []
        seen = set()

        tables = soup.find_all("table", class_="wikitable")

        for table in tables:
            rows = table.find_all("tr")
            if not rows:
                continue

            # ヘッダー行を確認（「紅組」「白組」を探す）
            header_cells = rows[0].find_all(["th", "td"])
            headers = [c.get_text(strip=True) for c in header_cells]

            # 紅組・白組の横並び形式かチェック
            if not ("紅組" in headers and "白組" in headers):
                continue

            # サブヘッダー行（「歌手名」「回」など）をスキップ
            data_start_idx = 1
            if len(rows) > 1:
                second_row_text = rows[1].get_text(strip=True)
                if "歌手名" in second_row_text or "回" in second_row_text:
                    data_start_idx = 2

            # データ行を処理（各行の全セルからアーティストを抽出）
            for row in rows[data_start_idx:]:
                cells = row.find_all(["td", "th"])
                for cell in cells:
                    self._extract_artists_from_cell(cell, year, seen, artists)

        return artists

    def _extract_artists_from_cell(
        self, cell, year: int, seen: set, artists: list[dict]
    ) -> None:
        """
        セルからアーティスト名を抽出して追加

        Args:
            cell: BeautifulSoupのセル要素
            year: 対象年
            seen: 既出アーティスト名のセット
            artists: アーティストリスト（追加先）
        """
        links = cell.find_all("a")
        for link in links:
            name = link.get_text(strip=True)

            # フィルタ
            if not name:
                continue
            if name.startswith("["):  # 注釈リンク
                continue
            if len(name) < 2:
                continue
            # 数字のみ（出場回数など）をスキップ
            if name.isdigit():
                continue
            # 「初」などの出場回数表記をスキップ
            if name in ("初", "返り咲き"):
                continue
            if name in seen:
                continue

            seen.add(name)
            artists.append(
                {
                    "year": year,
                    "artist": name,
                }
            )

    def execute(self) -> bool:
        """パイプライン実行"""
        print("=" * 60)
        print("Step 3: 紅白出場者リスト取得")
        print("=" * 60)

        all_artists = []

        for year, kai in self.target_years.items():
            print(f"\n[{year}年 第{kai}回]")

            html = self.get_kouhaku_page(kai)
            if not html:
                print("  ページ取得失敗")
                continue

            artists = self.parse_kouhaku_artists(html, year)
            print(f"  取得アーティスト数: {len(artists)}")

            if artists:
                sample = [a["artist"] for a in artists[:5]]
                print(f"  サンプル: {sample}")

            all_artists.extend(artists)
            time.sleep(self.interval)

        if not all_artists:
            print("\nデータが取得できませんでした")
            return False

        # DataFrame作成
        df = pd.DataFrame(all_artists)

        # 保存
        output_file = self.get_output_files()[0]
        df.to_csv(output_file, index=False, encoding="utf-8-sig")

        print(f"\n{'='*60}")
        print(f"保存: {output_file} ({len(df)}件)")

        # 年別集計
        print(f"\n年別出場者数:")
        print(df.groupby("year").size())

        # 複数年出場アーティスト
        print(f"\n複数年出場アーティスト（3回以上）:")
        artist_counts = df.groupby("artist").size().sort_values(ascending=False)
        multi_year = artist_counts[artist_counts >= 3]
        if len(multi_year) > 0:
            print(multi_year.head(15))
        else:
            print("  該当なし")

        return True


def main():
    """スタンドアロン実行用のエントリーポイント"""
    config = load_config()
    data_dir = Path(__file__).parent.parent.parent / config["paths"]["data_dir"]

    pipeline = Step3Pipeline(config, data_dir)
    success = pipeline.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
