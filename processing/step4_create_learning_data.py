"""
Step 4: 学習データ作成スクリプト
================================
紅白出場者 + Spotify上位アーティスト を候補者として、
紅白出場予測用の学習データを作成

入力:
- data/raw/spotify/jp_yearly_stats.csv: Spotify年別データ
- data/raw/kouhaku/kouhaku_artists.csv: 紅白出場者リスト
- data/processed/mapping/final_mapping.csv: 紅白⇔Spotify表記揺れ対応表（オプション）

出力:
- data/processed/learning_data.csv: 学習データ
"""

import sys
from pathlib import Path
import pandas as pd
from itertools import product
from typing import Any

from core.pipeline import DataPipeline, load_config


def calc_past_appearances(group):
    """累積出場回数（その年より前）を計算"""
    group = group.sort_values("year")
    group["past_appearances"] = group["appeared"].cumsum().shift(1, fill_value=0)
    return group


def calc_prev_year_appeared(group):
    """前年出場有無を計算"""
    group = group.sort_values("year")
    group["prev_year_appeared"] = group["appeared"].shift(1, fill_value=0)
    return group


def calc_consecutive_years(group):
    """連続出場年数を計算"""
    group = group.sort_values("year")
    consecutive = []
    count = 0
    for appeared in group["appeared"].shift(1, fill_value=0):
        if appeared == 1:
            count += 1
        else:
            count = 0
        consecutive.append(count)
    group["consecutive_years"] = consecutive
    return group


class Step4Pipeline(DataPipeline):
    """Step4: 学習データ作成パイプライン"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        super().__init__(config, data_dir)
        self.target_years = config["data_collection"]["target_years"]
        self.spotify_defaults = config["learning_data"]["spotify_defaults"]
        self.raw_spotify_dir = data_dir / "raw" / "spotify"
        self.raw_kouhaku_dir = data_dir / "raw" / "kouhaku"
        self.processed_dir = data_dir / "processed"
        self.processed_dir.mkdir(parents=True, exist_ok=True)

    def get_output_files(self) -> list[Path]:
        return [self.processed_dir / "learning_data.csv"]

    def check_dependencies(self) -> tuple[bool, list[str]]:
        spotify_file = self.raw_spotify_dir / "jp_yearly_stats.csv"
        kouhaku_file = self.raw_kouhaku_dir / "kouhaku_artists.csv"

        missing = []
        if not spotify_file.exists():
            missing.append(str(spotify_file))
        if not kouhaku_file.exists():
            missing.append(str(kouhaku_file))

        return len(missing) == 0, missing

    def execute(self) -> bool:
        """パイプライン実行"""
        print("=" * 60)
        print("Step 4: 学習データ作成")
        print("=" * 60)

        # 依存チェック
        ok, missing = self.check_dependencies()
        if not ok:
            print("エラー: 依存ファイルが見つかりません:")
            for f in missing:
                print(f"  - {f}")
            print("先に step2, step3 を実行してください")
            return False

        # ========== [1] データ読み込み ==========
        print("\n[1] データ読み込み")

        spotify_file = self.raw_spotify_dir / "jp_yearly_stats.csv"
        kouhaku_file = self.raw_kouhaku_dir / "kouhaku_artists.csv"

        df_spotify = pd.read_csv(spotify_file)
        df_kouhaku = pd.read_csv(kouhaku_file)

        print(
            f"  Spotifyデータ: {len(df_spotify)}行, {df_spotify['artist'].nunique()}アーティスト"
        )
        print(
            f"  紅白データ: {len(df_kouhaku)}行, {df_kouhaku['artist'].nunique()}アーティスト"
        )

        # ========== [2] アーティスト名の正規化 ==========
        print("\n[2] アーティスト名の正規化")

        # 表記揺れ対応表を読み込み（Spotify API で作成したマッピング）
        mapping_file = self.processed_dir / "mapping" / "final_mapping.csv"
        try:
            df_mapping = pd.read_csv(mapping_file)
            name_mapping = dict(
                zip(df_mapping["kouhaku_name"], df_mapping["spotify_name"])
            )
            print(
                f"  表記揺れ対応表: {len(name_mapping)}件読み込み（{mapping_file.name}）"
            )
        except FileNotFoundError:
            print(f"  警告: {mapping_file} が見つかりません")
            print("  表記揺れが解決できない可能性があります")
            name_mapping = {}

        # 正規化
        df_spotify["artist_normalized"] = df_spotify["artist"]
        df_kouhaku["artist_normalized"] = df_kouhaku["artist"].replace(name_mapping)

        # ========== [3] 候補者リスト作成 ==========
        print("\n[3] 候補者リスト作成")

        # 紅白出場者（全員）
        kouhaku_artists = set(df_kouhaku["artist_normalized"].unique())
        print(f"  紅白出場者: {len(kouhaku_artists)}組")

        # Spotify上位アーティスト
        spotify_artists = set(df_spotify["artist_normalized"].unique())
        print(f"  Spotifyアーティスト: {len(spotify_artists)}組")

        # 全候補者 = 紅白 ∪ Spotify
        all_candidates = kouhaku_artists | spotify_artists
        print(f"  全候補者（重複除去）: {len(all_candidates)}組")

        # ========== [4] 候補者 × 年 のベースデータ作成 ==========
        print("\n[4] 候補者 × 年 のベースデータ作成")

        # 全組み合わせ
        base_data = list(product(all_candidates, self.target_years))
        df_base = pd.DataFrame(base_data, columns=["artist_normalized", "year"])
        print(f"  ベースレコード数: {len(df_base)}")

        # ========== [5] Spotifyデータ結合 ==========
        print("\n[5] Spotifyデータ結合")

        # Spotifyデータから必要なカラムを選択
        spotify_cols = [
            "artist_normalized",
            "year",
            "weeks_on_chart",
            "total_streams",
            "best_rank",
            "avg_rank",
            "top10_weeks",
            "top1_weeks",
        ]
        df_spotify_subset = df_spotify[spotify_cols].copy()

        # LEFT JOIN
        df_merged = df_base.merge(
            df_spotify_subset, on=["artist_normalized", "year"], how="left"
        )

        # Spotifyデータ有無フラグ
        df_merged["has_spotify_data"] = df_merged["weeks_on_chart"].notna().astype(int)

        # 欠損値を0埋め
        for col, default in self.spotify_defaults.items():
            df_merged[col] = df_merged[col].fillna(default)

        matched = df_merged["has_spotify_data"].sum()
        print(f"  Spotifyデータあり: {matched}行 ({matched / len(df_merged):.1%})")

        # ========== [6] 紅白出場フラグ作成 ==========
        print("\n[6] 紅白出場フラグ作成")

        kouhaku_set = set(zip(df_kouhaku["artist_normalized"], df_kouhaku["year"]))
        df_merged["appeared"] = df_merged.apply(
            lambda row: (
                1 if (row["artist_normalized"], row["year"]) in kouhaku_set else 0
            ),
            axis=1,
        )

        appeared_count = df_merged["appeared"].sum()
        print(f"  紅白出場レコード: {appeared_count}件")

        # ========== [7] 過去の出場履歴特徴量 ==========
        print("\n[7] 過去の出場履歴特徴量作成")

        df_merged = df_merged.sort_values(["artist_normalized", "year"])

        # 累積出場回数（その年より前）
        df_merged = df_merged.groupby("artist_normalized", group_keys=False).apply(
            calc_past_appearances
        )

        # 前年出場有無
        df_merged = df_merged.groupby("artist_normalized", group_keys=False).apply(
            calc_prev_year_appeared
        )

        # 連続出場年数
        df_merged = df_merged.groupby("artist_normalized", group_keys=False).apply(
            calc_consecutive_years
        )

        # ========== [8] 最終的なカラム整理 ==========
        print("\n[8] カラム整理")

        # アーティスト名（元の名前を復元）
        artist_name_map = dict(
            zip(df_spotify["artist_normalized"], df_spotify["artist"])
        )
        df_merged["artist"] = (
            df_merged["artist_normalized"]
            .map(artist_name_map)
            .fillna(df_merged["artist_normalized"])
        )

        feature_cols = [
            "artist",
            "artist_normalized",
            "year",
            # Spotify特徴量
            "weeks_on_chart",
            "total_streams",
            "best_rank",
            "avg_rank",
            "top10_weeks",
            "top1_weeks",
            "has_spotify_data",
            # 紅白履歴特徴量
            "past_appearances",
            "prev_year_appeared",
            "consecutive_years",
            # 目的変数
            "appeared",
        ]

        df_learning = df_merged[feature_cols].copy()

        # ========== [9] 保存 ==========
        output_file = self.get_output_files()[0]
        df_learning.to_csv(output_file, index=False, encoding="utf-8-sig")

        print(f"\n{'=' * 60}")
        print(f"保存: {output_file} ({len(df_learning)}行)")

        # ========== サマリー ==========
        print(f"\n{'=' * 60}")
        print("データサマリー")
        print("=" * 60)

        print(f"\n総レコード数: {len(df_learning)}")
        print(f"アーティスト数: {df_learning['artist'].nunique()}")
        print(f"対象年: {df_learning['year'].min()} - {df_learning['year'].max()}")

        print("\n--- クラス分布 ---")
        print(df_learning["appeared"].value_counts())
        print(f"出場率: {df_learning['appeared'].mean():.2%}")

        print("\n--- Spotifyデータ有無 ---")
        print(df_learning["has_spotify_data"].value_counts())

        print("\n--- 年別出場者数 ---")
        yearly = df_learning.groupby("year").agg(
            candidates=("artist", "count"),
            appeared=("appeared", "sum"),
            has_spotify=("has_spotify_data", "sum"),
        )
        print(yearly)

        print("\n--- Spotifyデータなしの紅白出場者（2024年） ---")
        no_spotify_appeared = df_learning[
            (df_learning["year"] == 2024)
            & (df_learning["appeared"] == 1)
            & (df_learning["has_spotify_data"] == 0)
        ]["artist"].tolist()
        print(f"  {len(no_spotify_appeared)}組")
        if no_spotify_appeared:
            for a in no_spotify_appeared[:15]:
                print(f"    - {a}")
            if len(no_spotify_appeared) > 15:
                print(f"    ... 他 {len(no_spotify_appeared) - 15}組")

        return True


def main():
    """スタンドアロン実行用のエントリーポイント"""
    config = load_config()
    data_dir = Path(__file__).parent.parent / config["paths"]["data_dir"]

    pipeline = Step4Pipeline(config, data_dir)
    success = pipeline.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
