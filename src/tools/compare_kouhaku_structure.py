"""
紅白歌合戦Wikipediaページ構造比較スクリプト
============================================
2024年（第75回）と2025年（第76回）のWikipediaページ構造を比較し、
パース処理の問題点を特定する。

使用法:
    python -m tools.compare_kouhaku_structure
"""

import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# 設定読み込み
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.pipeline import load_config


def get_kouhaku_page(api_url: str, kai_number: int, headers: dict) -> str | None:
    """
    MediaWiki APIで紅白歌合戦のページHTMLを取得
    """
    title = f"第{kai_number}回NHK紅白歌合戦"

    params = {
        "action": "parse",
        "page": title,
        "format": "json",
        "prop": "text",
    }

    try:
        resp = requests.get(api_url, params=params, headers=headers, timeout=30)
        data = resp.json()

        if "parse" in data:
            return data["parse"]["text"]["*"]
        return None
    except Exception as e:
        print(f"  エラー: {e}")
        return None


def analyze_table_structure(html: str, year: int, kai: int) -> None:
    """
    Wikitableの構造を詳細に分析して出力
    """
    print(f"\n{'='*70}")
    print(f"【{year}年 第{kai}回 紅白歌合戦】")
    print(f"{'='*70}")

    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table", class_="wikitable")

    print(f"\n発見されたwikitableの数: {len(tables)}")

    for i, table in enumerate(tables):
        print(f"\n{'-'*50}")
        print(f"テーブル #{i + 1}")
        print(f"{'-'*50}")

        rows = table.find_all("tr")
        print(f"行数: {len(rows)}")

        if not rows:
            print("  (行なし)")
            continue

        # ヘッダー行を確認
        header_cells = rows[0].find_all(["th", "td"])
        headers = [c.get_text(strip=True) for c in header_cells]
        print(f"ヘッダー ({len(headers)}列): {headers}")

        # colspanを確認
        for j, cell in enumerate(header_cells):
            colspan = cell.get("colspan")
            rowspan = cell.get("rowspan")
            text = cell.get_text(strip=True)
            if colspan or rowspan:
                print(f"  セル{j} '{text}': colspan={colspan}, rowspan={rowspan}")

        # 紅組・白組が含まれているかチェック
        if "紅組" in headers or "白組" in headers:
            print(f"\n  *** 紅組/白組横並びテーブルを発見 ***")

            # 全行を分析（背景色を確認）
            for row_idx, row in enumerate(rows):
                cells = row.find_all(["td", "th"])
                # 行のstyle属性を確認
                row_style = row.get("style", "")
                row_bg = row.get("bgcolor", "")

                for cell_idx, cell in enumerate(cells):
                    text = cell.get_text(strip=True)[:30]
                    style = cell.get("style", "")
                    bgcolor = cell.get("bgcolor", "")

                    # 背景色がある場合のみ表示
                    if style or bgcolor or row_style or row_bg:
                        links = cell.find_all("a")
                        link_texts = [a.get_text(strip=True) for a in links[:3]]
                        print(f"  行{row_idx}[{cell_idx}] '{text}' style='{style}' bgcolor='{bgcolor}' row_style='{row_style}' links={link_texts}")

        # 「曲順」と「歌手名」カラムを探す
        order_idx = None
        singer_idx = None
        for idx, h in enumerate(headers):
            if h == "曲順":
                order_idx = idx
            if h == "歌手名":
                singer_idx = idx

        if order_idx is not None:
            print(f"  -> 「曲順」カラム: インデックス {order_idx}")
        if singer_idx is not None:
            print(f"  -> 「歌手名」カラム: インデックス {singer_idx}")

        # 出場者テーブルかどうか判定
        is_artist_table = order_idx is not None and singer_idx is not None

        if is_artist_table:
            print(f"\n  *** 出場者テーブルとして認識 ***")

            # 最初の数行のデータを表示
            print(f"\n  データ行サンプル (最大5行):")
            data_rows = rows[1:6]
            for j, row in enumerate(data_rows):
                cells = row.find_all(["td", "th"])
                if len(cells) <= max(singer_idx, order_idx):
                    print(f"    行{j+1}: (セル数不足: {len(cells)}セル)")
                    continue

                order_text = cells[order_idx].get_text(strip=True)
                singer_cell = cells[singer_idx]

                # 歌手名セルの詳細
                links = singer_cell.find_all("a")
                link_texts = [a.get_text(strip=True) for a in links]
                cell_text = singer_cell.get_text(strip=True)

                print(f"    行{j+1}: 曲順='{order_text}' | セル内容='{cell_text[:50]}...' | リンク数={len(links)}")
                if links:
                    print(f"           リンクテキスト: {link_texts[:5]}")

            # 抽出できるアーティスト数をカウント
            extracted = []
            seen = set()
            for row in rows[1:]:
                cells = row.find_all(["td", "th"])
                if len(cells) <= max(singer_idx, order_idx):
                    continue

                order_text = cells[order_idx].get_text(strip=True)
                if not order_text.isdigit():
                    continue

                singer_cell = cells[singer_idx]
                links = singer_cell.find_all("a")
                for link in links:
                    name = link.get_text(strip=True)
                    if not name or name.startswith("[") or len(name) < 2:
                        continue
                    if name not in seen:
                        seen.add(name)
                        extracted.append(name)

            print(f"\n  抽出アーティスト数: {len(extracted)}")
            if extracted:
                print(f"  サンプル: {extracted[:10]}")

        else:
            # 出場者テーブルでない場合、内容を確認
            print("  (出場者テーブルではない)")
            if rows:
                first_row_text = rows[0].get_text(strip=True)[:100]
                print(f"  最初の行: {first_row_text}...")

    # 他の構造も確認（出場者リスト用のdiv等があるか）
    print(f"\n{'-'*50}")
    print("その他の構造確認")
    print(f"{'-'*50}")

    # 紅組・白組の見出しを探す
    headings = soup.find_all(["h2", "h3", "h4"])
    relevant_headings = [h.get_text(strip=True) for h in headings
                         if any(word in h.get_text() for word in ["紅組", "白組", "出場", "歌手"])]
    print(f"関連見出し: {relevant_headings[:10]}")

    # 出場歌手に関連するセクションを探す
    for heading in headings:
        text = heading.get_text(strip=True)
        if "出場歌手" in text or "出演者" in text:
            print(f"\n見出し発見: '{text}'")
            # 次の要素を確認
            next_elem = heading.find_next_sibling()
            if next_elem:
                print(f"  次の要素タグ: {next_elem.name}")
                if next_elem.name == "table":
                    print("  -> テーブルが直後にあります")
                elif next_elem.name == "ul":
                    print("  -> リストが直後にあります")
                    items = next_elem.find_all("li")[:5]
                    for item in items:
                        print(f"     - {item.get_text(strip=True)[:50]}")


def main():
    """メイン処理"""
    config = load_config()

    api_url = config["network"]["urls"]["wikipedia_api"]
    headers = {"User-Agent": config["network"]["user_agent"]}

    # 比較対象の年
    target_years = {
        2024: 75,  # 開催済み（構造が変わっている可能性）
        2025: 76,  # 未開催 or 開催直後（構造が異なる）
    }

    print("紅白歌合戦Wikipediaページ構造比較")
    print("=" * 70)

    for year, kai in target_years.items():
        html = get_kouhaku_page(api_url, kai, headers)
        if html:
            analyze_table_structure(html, year, kai)
        else:
            print(f"\n{year}年（第{kai}回）のページ取得に失敗しました")

    print(f"\n{'='*70}")
    print("分析完了")
    print("=" * 70)


if __name__ == "__main__":
    main()
