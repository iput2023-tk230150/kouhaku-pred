"""
kworb.net ページ構造確認デバッグツール
======================================
アーティストページや曲ページのHTML構造を確認して、
スクレイパーの調整に使用するツール

使い方:
python debug_kworb.py [URL]
"""

import sys
from pathlib import Path
import requests
from bs4 import BeautifulSoup

# config.tomlから設定を読み込む
try:
    from kouhaku.pipeline import load_config
    config = load_config()
    HEADERS = {'User-Agent': config['network']['user_agent']}
    DEFAULT_URL = config['network']['urls']['default_debug_url']
except Exception:
    # フォールバック
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    DEFAULT_URL = "https://kworb.net/spotify/artist/4QvgGvpgzgyUOo8Yp8LDm9.html"


def analyze_page(url: str):
    """
    指定URLのページ構造を分析して表示

    Args:
        url: 分析するURL
    """
    print("=" * 60)
    print(f"ページ構造分析: {url}")
    print("=" * 60)

    print("\n取得中...")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    print(f"ステータス: {resp.status_code}")
    print(f"コンテンツサイズ: {len(resp.text):,} バイト")

    if resp.status_code != 200:
        print("ページ取得失敗")
        return

    soup = BeautifulSoup(resp.text, 'html.parser')

    # ページタイトル
    title = soup.find('title')
    print(f"\nページタイトル: {title.get_text() if title else 'N/A'}")

    # 全テーブルを列挙
    tables = soup.find_all('table')
    print(f"\n{'='*60}")
    print(f"テーブル数: {len(tables)}")
    print('='*60)

    for i, table in enumerate(tables):
        print(f"\n--- テーブル {i+1} ---")

        # クラス名
        classes = table.get('class', [])
        print(f"クラス: {classes if classes else 'なし'}")

        # ヘッダー行
        rows = table.find_all('tr')
        if rows:
            header_row = rows[0]
            headers = [cell.get_text(strip=True) for cell in header_row.find_all(['th', 'td'])]
            print(f"ヘッダー ({len(headers)}列): {headers}")

            # 最初の3データ行を表示
            print("サンプル行:")
            for j, row in enumerate(rows[1:4], 1):
                cells = [cell.get_text(strip=True)[:30] for cell in row.find_all(['td', 'th'])]
                print(f"  行 {j}: {cells}")

        print(f"総行数: {len(rows)}")

    # HTMLを保存（デバッグ用）
    debug_file = Path(__file__).parent.parent.parent / 'debug_page_structure.html'
    with open(debug_file, 'w', encoding='utf-8') as f:
        f.write(resp.text)
    print(f"\nフルHTML保存: {debug_file}")


def main():
    """メイン関数"""
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = DEFAULT_URL
        print(f"URLが指定されていないため、デフォルトURLを使用します")
        print(f"使い方: python {Path(sys.argv[0]).name} [URL]\n")

    try:
        analyze_page(url)
    except Exception as e:
        print(f"\nエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()