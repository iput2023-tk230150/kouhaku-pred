"""
アーティスト名 表記揺れ対応表 作成スクリプト v2
======================================================
改善点:
1. 長音の正規化(OU→O, UU→U など)
2. 姓名逆転パターンの試行
3. 手動マッピングファイルの読み込み・統合

出力:
- artist_name_mapping.csv: 確定マッピング(kouhaku_name → spotify_name)
- artist_name_mapping_draft.csv: 手動確認用候補
- unmatched_artists.csv: マッチしなかったアーティスト一覧

使い方:
    cd kouhaku-pred/src
    uv run python -m tools.create_mapping
"""

import sys
from pathlib import Path

import pandas as pd
from utils import ArtistNameNormalizer, ArtistMapper


def main():
    print("=" * 70)
    print("アーティスト名 表記揺れ対応表 作成 v2")
    print("(長音正規化 + 姓名逆転 + 手動マッピング対応)")
    print("=" * 70)

    # データ読み込み
    try:
        # プロジェクトルートのデータファイルを読み込む (src/tools/ → src/ → kouhaku-pred/)
        project_root = Path(__file__).parent.parent.parent
        df_spotify = pd.read_csv(project_root / "data" / "jp_yearly_stats.csv")
        df_kouhaku = pd.read_csv(project_root / "data" / "kouhaku_artists.csv")
    except FileNotFoundError as e:
        print(f"エラー: ファイルが見つかりません - {e}")
        print(f"プロジェクトルート: {project_root}")
        print("data/jp_yearly_stats.csv と data/kouhaku_artists.csv が必要です")
        sys.exit(1)

    # 正規化とマッピング実行
    normalizer = ArtistNameNormalizer()
    mapper = ArtistMapper(normalizer)

    # ユニークなアーティスト名を取得
    spotify_artists = df_spotify["artist"].unique().tolist()
    kouhaku_artists = df_kouhaku["artist"].unique().tolist()

    print(f"\nSpotifyアーティスト数: {len(spotify_artists)}")
    print(f"紅白アーティスト数: {len(kouhaku_artists)}")

    # 手動マッピングを読み込み
    manual_count = mapper.load_manual_mapping(str(project_root / "manual_mapping.csv"))
    if manual_count > 0:
        print(f"手動マッピング読み込み: {manual_count}件")

    # Spotify側の正規化インデックスを構築
    print("\n正規化処理中...")
    variant_count = mapper.build_spotify_index(spotify_artists)
    print(f"Spotify正規化バリエーション数: {variant_count}")

    # マッチング実行
    print("\nマッチング実行中...")
    matched, similar_candidates, unmatched = mapper.match_artists(
        kouhaku_artists, similarity_threshold=0.6
    )

    # 結果を保存
    mapper.save_results(matched, similar_candidates, unmatched, str(project_root))

    # サマリーを表示
    mapper.print_summary(matched, similar_candidates, unmatched, len(kouhaku_artists))


if __name__ == "__main__":
    main()
