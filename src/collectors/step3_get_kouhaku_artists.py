"""
Step 3: 紅白出場者リスト取得スクリプト
======================================
WikipediaのMediaWiki APIを使用して紅白歌合戦の出場者リストを取得

出力:
- data/raw/kouhaku/kouhaku_artists.csv: 年別出場者リスト（year, artist, group）
  - group: 紅組/白組
"""

import sys
from pathlib import Path
from datetime import datetime
import requests
import pandas as pd
from bs4 import BeautifulSoup
import time
from typing import Any

from rich.progress import track

from src.core.pipeline import DataPipeline, load_config


class Step3Pipeline(DataPipeline):
    """Step3: 紅白出場者リスト取得パイプライン"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        super().__init__(config, data_dir)
        # TOMLのキーは文字列なのでintに変換
        self.target_years = {
            int(k): v for k, v in config["kouhaku"]["target_years"].items()
        }
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
        「組」列から紅組・白組を判定
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

            # 「曲順」「歌手名」「組」カラムを探す
            order_idx = None
            singer_idx = None
            group_idx = None
            for i, h in enumerate(headers):
                if h == "曲順":
                    order_idx = i
                if h == "歌手名":
                    singer_idx = i
                if h == "組":
                    group_idx = i

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

                # 組を判定
                group = None
                if group_idx is not None and len(cells) > group_idx:
                    group_text = cells[group_idx].get_text(strip=True)
                    if "紅" in group_text:
                        group = "紅組"
                    elif "白" in group_text:
                        group = "白組"

                cell = cells[singer_idx]
                self._extract_artists_from_cell(cell, year, seen, artists, group)

        return artists

    def _parse_pre_broadcast_format(self, soup: BeautifulSoup, year: int) -> list[dict]:
        """
        開催前形式のパース（紅組・白組が横並びのテーブル）
        ヘッダーが「紅組」「白組」の2列構成
        rowspanによりセル数が変動するため、セル位置の前半/後半で紅組・白組を判定
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

            # データ行を処理
            # rowspanによりセル数が変動するため、セル位置の前半/後半で判定
            for row in rows[data_start_idx:]:
                cells = row.find_all(["td", "th"])
                num_cells = len(cells)
                midpoint = num_cells // 2  # セル数の半分を境界とする

                for col_idx, cell in enumerate(cells):
                    # 特別企画枠（背景色Khaki）をスキップ
                    style = cell.get("style", "")
                    if "khaki" in style.lower():
                        continue

                    # セル位置の前半/後半で紅組・白組を判定
                    group = "紅組" if col_idx < midpoint else "白組"

                    self._extract_artists_from_cell(cell, year, seen, artists, group)

        return artists

    def _extract_artists_from_cell(
        self, cell, year: int, seen: set, artists: list[dict], group: str | None = None
    ) -> None:
        """
        セルからアーティスト名を抽出して追加

        Args:
            cell: BeautifulSoupのセル要素
            year: 対象年
            seen: 既出アーティスト名のセット
            artists: アーティストリスト（追加先）
            group: 紅組/白組（Noneの場合は不明）
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
                    "group": group,
                }
            )

    def execute(self) -> bool:
        """パイプライン実行"""
        print("=" * 60)
        print("Step 3: 紅白出場者リスト取得")
        print("=" * 60)

        output_file = self.get_output_files()[0]
        current_year = datetime.now().year

        # 既存データの読み込み
        df_existing = None
        if output_file.exists():
            df_existing = pd.read_csv(output_file)
            df_existing["year"] = df_existing["year"].astype(int)
            print(f"\n既存データ: {len(df_existing)}件")

            # 今年のデータがあれば削除して再取得対象に
            if current_year in df_existing["year"].values:
                past_data = df_existing[df_existing["year"] != current_year]
                print(f"  過去データ: {len(past_data)}件（保持）")
                print(f"  今年データ: {len(df_existing) - len(past_data)}件（再取得）")
                df_existing = past_data
            else:
                print("  今年のデータなし（新規取得）")

        # 取得対象年を決定
        if df_existing is not None and not df_existing.empty:
            existing_years = set(df_existing["year"].values)
            years_to_fetch = {
                y: k
                for y, k in self.target_years.items()
                if y not in existing_years or y == current_year
            }
        else:
            years_to_fetch = self.target_years

        if not years_to_fetch:
            print("\n取得対象の年がありません")
            return True

        print(f"\n取得対象年: {list(years_to_fetch.keys())}")

        all_artists = []

        for year, kai in track(years_to_fetch.items(), description="紅白出場者取得中"):
            html = self.get_kouhaku_page(kai)
            if not html:
                continue

            artists = self.parse_kouhaku_artists(html, year)

            if artists:
                all_artists.extend(artists)

            time.sleep(self.interval)

        if not all_artists and df_existing is None:
            print("\nデータが取得できませんでした")
            return False

        # DataFrame作成（新規取得分）
        df_new = pd.DataFrame(all_artists) if all_artists else pd.DataFrame()

        # 既存データとマージ
        if df_existing is not None and not df_existing.empty:
            df = pd.concat([df_existing, df_new], ignore_index=True)
            df = df.sort_values("year").reset_index(drop=True)
        else:
            df = df_new

        # 保存
        df.to_csv(output_file, index=False, encoding="utf-8-sig")

        print(f"\n{'=' * 60}")
        print(f"保存: {output_file} ({len(df)}件)")

        # 年別集計
        print("\n年別出場者数:")
        print(df.groupby("year").size())

        # 複数年出場アーティスト
        print("\n複数年出場アーティスト（3回以上）:")
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
