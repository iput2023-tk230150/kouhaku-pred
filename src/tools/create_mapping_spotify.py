"""
Spotify Search APIを使用したアーティスト名マッピング作成スクリプト（改善版）

従来の文字列類似度マッチングではなく、Spotify検索エンジンを活用して
紅白アーティストとSpotifyアーティストを紐づける。

改善点:
- 検索クエリの多段階化（単純検索 → artist:プレフィックス）
- 候補評価ロジックの改善（類似度 + フォロワー数 + 人気度 + 日本語ボーナス）
- 自動マッチ条件の見直し（スコアベース評価）

使い方:
    cd kouhaku-pred/src
    uv run python -m tools.create_mapping_spotify

出力:
    data/mapping/spotify_mapping.csv - 確定したマッピング
    data/mapping/spotify_mapping_candidates.csv - 手動確認が必要な候補
    data/mapping/spotify_not_found.csv - Spotifyで見つからなかったアーティスト
"""

import os
import re
import time
import math
from pathlib import Path
from difflib import SequenceMatcher

import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv


def load_spotify_client() -> spotipy.Spotify:
    """Spotify APIクライアントを初期化"""
    load_dotenv()

    client_id = os.getenv("SPOTIFY_API_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_API_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError("SPOTIFY_API_CLIENT_ID と SPOTIFY_API_CLIENT_SECRET を .env に設定してください")

    auth_manager = SpotifyClientCredentials(
        client_id=client_id,
        client_secret=client_secret
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def contains_japanese(text: str) -> bool:
    """テキストに日本語が含まれるかチェック"""
    # ひらがな、カタカナ、漢字のいずれかが含まれるか
    return bool(re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FFF]', text))


def normalize_for_comparison(name: str) -> str:
    """比較用に名前を正規化（小文字化、記号除去）"""
    name = name.lower()
    name = re.sub(r'[^\w\s]', '', name)  # 記号除去
    name = re.sub(r'\s+', '', name)  # 空白除去
    return name


def calculate_similarity(name1: str, name2: str) -> float:
    """2つの名前の類似度を計算"""
    norm1 = normalize_for_comparison(name1)
    norm2 = normalize_for_comparison(name2)
    return SequenceMatcher(None, norm1, norm2).ratio()


def score_candidate(kouhaku_name: str, candidate: dict) -> float:
    """
    候補アーティストのスコアを計算（0-100）

    評価基準:
    - 名前の類似度: 40%
    - フォロワー数（対数スケール）: 30%
    - 人気度: 20%
    - 日本語名ボーナス: 10%
    """
    score = 0.0

    # 名前の類似度（重み: 40%）
    similarity = candidate.get('similarity', 0)
    score += similarity * 40

    # フォロワー数（重み: 30%）- 対数スケール、1000万で満点
    followers = candidate.get('followers', 0)
    if followers > 0:
        # log10(10,000,000) = 7
        follower_score = min(math.log10(followers) / 7, 1.0)
        score += follower_score * 30

    # 人気度 popularity（重み: 20%）
    popularity = candidate.get('popularity', 0)
    score += (popularity / 100) * 20

    # 日本語名が含まれるかボーナス（重み: 10%）
    # 紅白アーティストが日本語名の場合、Spotify側も日本語名なら高評価
    if contains_japanese(kouhaku_name) and contains_japanese(candidate.get('spotify_name', '')):
        score += 10

    return score


def search_artist_on_spotify(
    sp: spotipy.Spotify,
    artist_name: str,
    limit: int = 10
) -> list[dict]:
    """
    Spotifyでアーティストを検索（多段階検索）

    Returns:
        検索結果のリスト（重複除去済み）
    """
    seen_ids = set()
    all_results = []

    # 検索クエリのバリエーション
    queries = [
        artist_name,                    # 単純検索
        f'artist:{artist_name}',        # artist:プレフィックス
        f'"{artist_name}"',             # 完全一致検索
    ]

    for query in queries:
        try:
            results = sp.search(q=query, type='artist', limit=limit, market='JP')
            artists = results.get('artists', {}).get('items', [])

            for artist in artists:
                if artist['id'] not in seen_ids:
                    seen_ids.add(artist['id'])
                    all_results.append({
                        'spotify_id': artist['id'],
                        'spotify_name': artist['name'],
                        'followers': artist['followers']['total'],
                        'popularity': artist['popularity'],
                        'genres': artist.get('genres', []),
                        'similarity': calculate_similarity(artist_name, artist['name'])
                    })

            # 十分な結果が得られたら終了
            if len(all_results) >= limit:
                break

        except Exception as e:
            print(f"  検索エラー ({query}): {e}")

        # API rate limit対策
        time.sleep(0.05)

    return all_results


def should_auto_match(kouhaku_name: str, candidates: list[dict]) -> dict | None:
    """
    自動マッチングの判定

    条件:
    1. スコアが70以上で、2位との差が15以上
    2. 完全一致（正規化後）かつフォロワー1000以上
    3. 類似度が0.95以上かつフォロワー10000以上

    Returns:
        マッチした場合はアーティスト情報、しなければNone
    """
    if not candidates:
        return None

    # スコアでソート
    scored = [(c, score_candidate(kouhaku_name, c)) for c in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    best_candidate, best_score = scored[0]
    second_score = scored[1][1] if len(scored) > 1 else 0

    # 条件1: スコアが70以上で、2位との差が15以上
    if best_score >= 70 and (best_score - second_score) >= 15:
        best_candidate['score'] = best_score
        return best_candidate

    # 条件2: 完全一致（正規化後）かつフォロワー1000以上
    norm_kouhaku = normalize_for_comparison(kouhaku_name)
    norm_spotify = normalize_for_comparison(best_candidate['spotify_name'])
    if norm_kouhaku == norm_spotify and best_candidate['followers'] >= 1000:
        best_candidate['score'] = best_score
        return best_candidate

    # 条件3: 類似度が0.95以上かつフォロワー10000以上
    if best_candidate['similarity'] >= 0.95 and best_candidate['followers'] >= 10000:
        best_candidate['score'] = best_score
        return best_candidate

    return None


def main():
    project_root = Path(__file__).parent.parent.parent

    # 出力ディレクトリ
    output_dir = project_root / "data" / "mapping"
    output_dir.mkdir(parents=True, exist_ok=True)

    # 紅白アーティスト読み込み
    kouhaku_path = project_root / "data" / "kouhaku_artists.csv"
    kouhaku_df = pd.read_csv(kouhaku_path, encoding="utf-8-sig")

    # ユニークなアーティスト名を取得
    unique_artists = kouhaku_df['artist'].unique().tolist()
    print(f"紅白アーティスト数: {len(unique_artists)}")

    # Spotifyクライアント初期化
    sp = load_spotify_client()
    print("Spotify API接続成功\n")

    # 結果格納用
    auto_matched = []  # 自動マッチ成功
    candidates = []     # 手動確認必要
    not_found = []      # 検索結果なし

    # 各アーティストを検索
    for i, artist_name in enumerate(unique_artists):
        print(f"[{i+1}/{len(unique_artists)}] 検索中: {artist_name}")

        # API rate limit対策
        time.sleep(0.1)

        search_results = search_artist_on_spotify(sp, artist_name)

        if not search_results:
            print(f"  → 検索結果なし")
            not_found.append({
                'kouhaku_name': artist_name,
                'reason': '検索結果0件'
            })
            continue

        # 自動マッチング試行
        auto_match = should_auto_match(artist_name, search_results)

        if auto_match:
            print(f"  → 自動マッチ: {auto_match['spotify_name']} "
                  f"(スコア: {auto_match['score']:.1f}, "
                  f"類似度: {auto_match['similarity']:.2f}, "
                  f"フォロワー: {auto_match['followers']:,})")
            auto_matched.append({
                'kouhaku_name': artist_name,
                'spotify_id': auto_match['spotify_id'],
                'spotify_name': auto_match['spotify_name'],
                'followers': auto_match['followers'],
                'popularity': auto_match['popularity'],
                'similarity': auto_match['similarity'],
                'score': auto_match['score'],
                'match_type': 'auto'
            })
        else:
            # 候補として保存（スコア順で上位5件）
            scored = [(c, score_candidate(artist_name, c)) for c in search_results]
            scored.sort(key=lambda x: x[1], reverse=True)

            print(f"  → 候補あり（手動確認必要）- 上位: {scored[0][0]['spotify_name']} (スコア: {scored[0][1]:.1f})")

            for j, (result, score) in enumerate(scored[:5]):
                candidates.append({
                    'kouhaku_name': artist_name,
                    'rank': j + 1,
                    'spotify_id': result['spotify_id'],
                    'spotify_name': result['spotify_name'],
                    'followers': result['followers'],
                    'popularity': result['popularity'],
                    'similarity': result['similarity'],
                    'score': score
                })

    # 結果をCSV出力
    print("\n" + "="*60)
    print("結果サマリー")
    print("="*60)

    # 自動マッチ結果
    if auto_matched:
        matched_df = pd.DataFrame(auto_matched)
        matched_path = output_dir / "spotify_mapping.csv"
        matched_df.to_csv(matched_path, index=False, encoding="utf-8-sig")
        print(f"自動マッチ: {len(auto_matched)}件 → {matched_path.name}")

    # 候補（手動確認用）
    unique_candidate_artists = 0
    if candidates:
        candidates_df = pd.DataFrame(candidates)
        candidates_path = output_dir / "spotify_mapping_candidates.csv"
        candidates_df.to_csv(candidates_path, index=False, encoding="utf-8-sig")
        unique_candidate_artists = len(set(c['kouhaku_name'] for c in candidates))
        print(f"手動確認必要: {unique_candidate_artists}件 → {candidates_path.name}")

    # 見つからなかったアーティスト
    if not_found:
        not_found_df = pd.DataFrame(not_found)
        not_found_path = output_dir / "spotify_not_found.csv"
        not_found_df.to_csv(not_found_path, index=False, encoding="utf-8-sig")
        print(f"検索結果なし: {len(not_found)}件 → {not_found_path.name}")

    # 統計
    total = len(unique_artists)
    print(f"\n合計: {total}件")
    print(f"  自動マッチ成功: {len(auto_matched)}件 ({len(auto_matched)/total*100:.1f}%)")
    print(f"  手動確認必要: {unique_candidate_artists}件 ({unique_candidate_artists/total*100:.1f}%)")
    print(f"  検索結果なし: {len(not_found)}件 ({len(not_found)/total*100:.1f}%)")


if __name__ == "__main__":
    main()
