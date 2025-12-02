"""
アーティストマッピングモジュール
================================
紅白歌合戦とSpotifyのアーティスト名をマッピングする機能を提供
"""

from pathlib import Path
from difflib import SequenceMatcher
import pandas as pd
from .normalizer import ArtistNameNormalizer


def similarity(a: str, b: str) -> float:
    """2つの文字列の類似度を計算(0〜1)"""
    return SequenceMatcher(None, a, b).ratio()


class ArtistMapper:
    """アーティスト名のマッピングを管理するクラス"""

    def __init__(self, normalizer: ArtistNameNormalizer | None = None):
        """
        初期化

        Args:
            normalizer: ArtistNameNormalizerインスタンス。Noneの場合は新規作成
        """
        self.normalizer = normalizer or ArtistNameNormalizer()
        self.manual_mapping: dict[str, str] = {}
        self.spotify_normalized: dict[str, str] = {}

    def load_manual_mapping(self, filepath: str = "manual_mapping.csv") -> int:
        """
        手動マッピングファイルを読み込む

        Args:
            filepath: マッピングファイルのパス

        Returns:
            読み込んだマッピング数
        """
        if not Path(filepath).exists():
            return 0

        try:
            df = pd.read_csv(filepath)
            if "kouhaku_name" in df.columns and "spotify_name" in df.columns:
                # 空のspotify_nameをスキップ
                df = df[df["spotify_name"].notna() & (df["spotify_name"] != "")]
                self.manual_mapping = dict(zip(df["kouhaku_name"], df["spotify_name"]))
                return len(self.manual_mapping)
        except Exception as e:
            print(f"警告: 手動マッピングファイル読み込みエラー - {e}")

        return 0

    def build_spotify_index(self, spotify_artists: list[str]) -> int:
        """
        Spotifyアーティストの正規化インデックスを構築

        Args:
            spotify_artists: Spotifyのアーティスト名リスト

        Returns:
            作成されたバリエーション数
        """
        self.spotify_normalized = {}

        for artist in spotify_artists:
            variants = self.normalizer.get_name_variants(artist)
            for variant in variants:
                if variant and variant not in self.spotify_normalized:
                    self.spotify_normalized[variant] = artist

        return len(self.spotify_normalized)

    def match_artists(
        self, kouhaku_artists: list[str], similarity_threshold: float = 0.6
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """
        紅白アーティストとSpotifyアーティストをマッチング

        Args:
            kouhaku_artists: 紅白のアーティスト名リスト
            similarity_threshold: 類似度マッチングの閾値(0〜1)

        Returns:
            (matched, similar_candidates, unmatched)のタプル
            - matched: 確定マッチングのリスト
            - similar_candidates: 類似度マッチング候補のリスト
            - unmatched: 未マッチのリスト
        """
        matched = []  # 自動マッチ成功
        similar_candidates = []  # 類似度候補
        unmatched = []  # 未マッチ

        for kouhaku_orig in kouhaku_artists:
            # 1. 手動マッピングを優先
            if kouhaku_orig in self.manual_mapping:
                matched.append(
                    {
                        "kouhaku_name": kouhaku_orig,
                        "spotify_name": self.manual_mapping[kouhaku_orig],
                        "match_type": "manual",
                    }
                )
                continue

            # 2. 正規化マッチング(複数バリエーションを試行)
            kouhaku_variants = self.normalizer.get_name_variants(kouhaku_orig)
            found = False

            for variant in kouhaku_variants:
                if variant in self.spotify_normalized:
                    matched.append(
                        {
                            "kouhaku_name": kouhaku_orig,
                            "spotify_name": self.spotify_normalized[variant],
                            "normalized": variant,
                            "match_type": "normalized",
                        }
                    )
                    found = True
                    break

            if found:
                continue

            # 3. 類似度マッチング(フォールバック)
            best_match = None
            best_score = 0
            best_kouhaku_variant = None
            best_spotify_variant = None

            for kouhaku_variant in kouhaku_variants:
                for spotify_variant, spotify_orig in self.spotify_normalized.items():
                    score = similarity(kouhaku_variant, spotify_variant)
                    if score > best_score and score >= similarity_threshold:
                        best_score = score
                        best_match = spotify_orig
                        best_kouhaku_variant = kouhaku_variant
                        best_spotify_variant = spotify_variant

            if best_match:
                similar_candidates.append(
                    {
                        "kouhaku_name": kouhaku_orig,
                        "spotify_name": best_match,
                        "kouhaku_normalized": best_kouhaku_variant,
                        "spotify_normalized": best_spotify_variant,
                        "similarity": round(best_score, 3),
                        "confirmed": "",
                    }
                )
            else:
                unmatched.append(
                    {
                        "kouhaku_name": kouhaku_orig,
                        "variants_tried": ", ".join(
                            kouhaku_variants[:3]
                        ),  # 最大3つ表示
                    }
                )

        return matched, similar_candidates, unmatched

    def save_results(
        self,
        matched: list[dict],
        similar_candidates: list[dict],
        unmatched: list[dict],
        output_dir: str = ".",
    ) -> None:
        """
        マッチング結果をCSVファイルに保存

        Args:
            matched: 確定マッチングのリスト
            similar_candidates: 類似度マッチング候補のリスト
            unmatched: 未マッチのリスト
            output_dir: 出力先ディレクトリ
        """
        output_path = Path(output_dir)

        # 1. 確定マッピング
        if matched:
            df_matched = pd.DataFrame(matched)[["kouhaku_name", "spotify_name"]]
            df_matched.to_csv(
                output_path / "artist_name_mapping.csv",
                index=False,
                encoding="utf-8-sig",
            )

        # 2. 類似度マッチ候補(手動確認用)
        if similar_candidates:
            df_similar = pd.DataFrame(similar_candidates)
            df_similar.to_csv(
                output_path / "artist_name_mapping_draft.csv",
                index=False,
                encoding="utf-8-sig",
            )

        # 3. 未マッチアーティスト
        if unmatched:
            df_unmatched = pd.DataFrame(unmatched)
            df_unmatched.to_csv(
                output_path / "unmatched_artists.csv", index=False, encoding="utf-8-sig"
            )

            # 手動マッピングテンプレート出力
            manual_mapping_path = output_path / "manual_mapping.csv"
            if not manual_mapping_path.exists():
                template = pd.DataFrame(
                    {
                        "kouhaku_name": [item["kouhaku_name"] for item in unmatched],
                        "spotify_name": [""] * len(unmatched),
                    }
                )
                template.to_csv(manual_mapping_path, index=False, encoding="utf-8-sig")

    def print_summary(
        self,
        matched: list[dict],
        similar_candidates: list[dict],
        unmatched: list[dict],
        kouhaku_total: int,
    ) -> None:
        """
        マッチング結果のサマリーを表示

        Args:
            matched: 確定マッチングのリスト
            similar_candidates: 類似度マッチング候補のリスト
            unmatched: 未マッチのリスト
            kouhaku_total: 紅白アーティスト総数
        """
        print("\n" + "=" * 70)
        print("マッチング結果")
        print("=" * 70)

        print(f"\n自動マッチ成功: {len(matched)}組")
        print(f"類似度候補: {len(similar_candidates)}組")
        print(f"未マッチ: {len(unmatched)}組")

        # 確定マッピングの詳細
        if matched:
            print("\n" + "-" * 70)
            print("[確定] artist_name_mapping.csv")
            print("-" * 70)

            manual_count = sum(1 for m in matched if m.get("match_type") == "manual")
            normalized_count = len(matched) - manual_count
            print(f"  - 手動マッピング: {manual_count}件")
            print(f"  - 自動正規化: {normalized_count}件")

            df_matched = pd.DataFrame(matched)[["kouhaku_name", "spotify_name"]]
            print("\n" + df_matched.head(15).to_string(index=False))
            if len(matched) > 15:
                print(f"  ... 他 {len(matched) - 15}件")

        # 類似度マッチ候補
        if similar_candidates:
            print("\n" + "-" * 70)
            print(
                f"[要確認] artist_name_mapping_draft.csv ({len(similar_candidates)}件)"
            )
            print("-" * 70)
            df_similar = pd.DataFrame(similar_candidates)
            print(
                df_similar[["kouhaku_name", "spotify_name", "similarity"]].to_string(
                    index=False
                )
            )

        # 未マッチアーティスト
        if unmatched:
            print("\n" + "-" * 70)
            print(f"[未マッチ] unmatched_artists.csv ({len(unmatched)}件)")
            print("-" * 70)
            print("manual_mapping.csv に追加してください:")
            for item in unmatched:
                print(f"  {item['kouhaku_name']}")
                print(f"    試行: {item['variants_tried']}")

        # 最終サマリー
        print("\n" + "=" * 70)
        print("サマリー")
        print("=" * 70)
        print(f"紅白アーティスト総数: {kouhaku_total}")
        print(
            f"  - 自動マッチ成功: {len(matched)} ({100*len(matched)/kouhaku_total:.1f}%)"
        )
        print(
            f"  - 類似度候補: {len(similar_candidates)} ({100*len(similar_candidates)/kouhaku_total:.1f}%)"
        )
        print(
            f"  - 未マッチ: {len(unmatched)} ({100*len(unmatched)/kouhaku_total:.1f}%)"
        )

        if similar_candidates or unmatched:
            print("\n次のステップ:")
            print("1. artist_name_mapping_draft.csv を確認し、正しいものを")
            print("   manual_mapping.csv にコピー")
            print("2. unmatched_artists.csv のアーティストを")
            print("   manual_mapping.csv に手動追加")
            print("3. 再度スクリプトを実行")
