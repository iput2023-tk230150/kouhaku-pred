"""
Step 7: 2025年紅白出場者予測スクリプト
================================
学習済みモデルを使用して2025年の紅白出場者を予測
発表済みの出場者リストとの比較・精度評価も行う

入力:
- models/model.pkl: 学習済みモデル
- data/raw/spotify/jp_yearly_stats.csv: Spotifyデータ
- data/raw/kouhaku/kouhaku_artists.csv: 紅白出場者リスト（2025年発表済み含む）

出力:
- data/analysis/predictions_2025.csv: 2025年予測結果
"""

import sys
from pathlib import Path
import pandas as pd
import pickle
from typing import Any

from core.pipeline import DataPipeline, load_config


class Step7Pipeline(DataPipeline):
    """Step7: 2025年予測パイプライン"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        super().__init__(config, data_dir)
        self.raw_spotify_dir = data_dir / "raw" / "spotify"
        self.raw_kouhaku_dir = data_dir / "raw" / "kouhaku"
        # models_dirはdata_dirの外（プロジェクトルート直下）
        project_root = data_dir.parent
        self.models_dir = project_root / config["paths"]["models_dir"]
        self.analysis_dir = data_dir / "analysis"
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        # 特徴量カラム
        self.feature_cols = [
            "weeks_on_chart",
            "total_streams",
            "best_rank",
            "avg_rank",
            "top10_weeks",
            "top1_weeks",
            "has_spotify_data",
            "past_appearances",
            "prev_year_appeared",
            "consecutive_years",
        ]

    def get_output_files(self) -> list[Path]:
        return [self.analysis_dir / "predictions_2025.csv"]

    def check_dependencies(self) -> tuple[bool, list[str]]:
        model_file = self.models_dir / "model.pkl"
        spotify_file = self.raw_spotify_dir / "jp_yearly_stats.csv"
        kouhaku_file = self.raw_kouhaku_dir / "kouhaku_artists.csv"

        missing = []
        if not model_file.exists():
            missing.append(str(model_file))
        if not spotify_file.exists():
            missing.append(str(spotify_file))
        if not kouhaku_file.exists():
            missing.append(str(kouhaku_file))

        return len(missing) == 0, missing

    def execute(self) -> bool:
        """パイプライン実行"""
        print("=" * 60)
        print("Step 7: 2025年紅白出場者予測")
        print("=" * 60)

        # 依存チェック
        ok, missing = self.check_dependencies()
        if not ok:
            print("エラー: 依存ファイルが見つかりません:")
            for f in missing:
                print(f"  - {f}")
            return False

        # ========== [1] データ読み込み ==========
        print("\n[1] データ読み込み")

        # モデル読み込み
        with open(self.models_dir / "model.pkl", "rb") as f:
            model = pickle.load(f)
        print("  モデルを読み込みました")

        # Spotifyデータ読み込み
        df_spotify = pd.read_csv(self.raw_spotify_dir / "jp_yearly_stats.csv")
        df_spotify_2025 = df_spotify[df_spotify["year"] == 2025].copy()
        print(f"  2025年Spotifyデータ: {len(df_spotify_2025)}アーティスト")

        # 紅白出場者データ読み込み
        df_kouhaku = pd.read_csv(self.raw_kouhaku_dir / "kouhaku_artists.csv")
        print(f"  紅白出場者データ: {len(df_kouhaku)}件")

        # 2025年発表済み出場者を取得
        df_kouhaku_2025 = df_kouhaku[df_kouhaku["year"] == 2025].copy()
        actual_artists_2025 = set(df_kouhaku_2025["artist"].unique())
        print(f"  2025年発表済み出場者: {len(actual_artists_2025)}組")

        # ========== [2] 候補者データ作成 ==========
        print("\n[2] 候補者データ作成")

        # 2025年のSpotifyアーティスト + 過去の紅白出場者
        spotify_artists = set(df_spotify_2025["artist"].unique())
        kouhaku_artists = set(df_kouhaku["artist"].unique())
        all_candidates = spotify_artists | kouhaku_artists

        print(f"  Spotifyアーティスト: {len(spotify_artists)}")
        print(f"  紅白出場経験者: {len(kouhaku_artists)}")
        print(f"  候補者合計: {len(all_candidates)}")

        # ========== [3] 特徴量作成 ==========
        print("\n[3] 特徴量作成")

        candidates = []
        for artist in all_candidates:
            row = {"artist": artist, "year": 2025}

            # Spotify特徴量
            spotify_row = df_spotify_2025[df_spotify_2025["artist"] == artist]
            if len(spotify_row) > 0:
                spotify_row = spotify_row.iloc[0]
                row["weeks_on_chart"] = spotify_row["weeks_on_chart"]
                row["total_streams"] = spotify_row["total_streams"]
                row["best_rank"] = spotify_row["best_rank"]
                row["avg_rank"] = spotify_row["avg_rank"]
                row["top10_weeks"] = spotify_row["top10_weeks"]
                row["top1_weeks"] = spotify_row["top1_weeks"]
                row["has_spotify_data"] = 1
            else:
                # Spotifyデータなし
                row["weeks_on_chart"] = 0
                row["total_streams"] = 0
                row["best_rank"] = 999
                row["avg_rank"] = 999
                row["top10_weeks"] = 0
                row["top1_weeks"] = 0
                row["has_spotify_data"] = 0

            # 紅白履歴特徴量
            artist_kouhaku = df_kouhaku[df_kouhaku["artist"] == artist]
            past_appearances = len(artist_kouhaku[artist_kouhaku["year"] < 2025])
            prev_year_appeared = 1 if 2024 in artist_kouhaku["year"].values else 0

            # 連続出場年数
            years = sorted(artist_kouhaku["year"].values)
            consecutive = 0
            for y in range(2024, 2019, -1):  # 2024から遡る
                if y in years:
                    consecutive += 1
                else:
                    break

            row["past_appearances"] = past_appearances
            row["prev_year_appeared"] = prev_year_appeared
            row["consecutive_years"] = consecutive

            candidates.append(row)

        df_candidates = pd.DataFrame(candidates)
        print(f"  特徴量作成完了: {len(df_candidates)}件")

        # ========== [4] 予測 ==========
        print("\n[4] 予測実行")

        X = df_candidates[self.feature_cols]
        probs = model.predict_proba(X)[:, 1]
        predictions = model.predict(X)

        df_candidates["predicted_prob"] = probs
        df_candidates["predicted"] = predictions

        # 実際の出場フラグと紅組・白組を追加
        df_candidates["actual"] = (
            df_candidates["artist"].isin(actual_artists_2025).astype(int)
        )

        # 紅組・白組情報を追加
        artist_to_group = {}
        if "group" in df_kouhaku_2025.columns:
            for _, row in df_kouhaku_2025.iterrows():
                artist_to_group[row["artist"]] = row.get("group")
        df_candidates["group"] = df_candidates["artist"].map(artist_to_group)

        # 確率順にソート（予測順位を付与）
        df_candidates = df_candidates.sort_values(
            "predicted_prob", ascending=False
        ).reset_index(drop=True)
        df_candidates["pred_rank"] = df_candidates.index + 1

        # ========== [5] 結果表示 ==========
        print("\n[5] 予測結果")

        # 出場予測（predicted=1）
        df_predicted = df_candidates[df_candidates["predicted"] == 1]
        print(f"\n  出場予測アーティスト: {len(df_predicted)}組")

        # 発表済み出場者がいる場合は比較表示
        if len(actual_artists_2025) > 0:
            print("\n  Top 50 予測確率ランキング（発表済み出場者との比較）:")
            print("-" * 80)
            print(
                f"  {'順位':>4}  {'予測':>2} {'実際':>2} {'組':>4} {'アーティスト':20s} {'確率':>6} {'過去出場':>6}"
            )
            print("-" * 80)
            for _, row in df_candidates.head(50).iterrows():
                rank = int(row["pred_rank"])
                prob = row["predicted_prob"]
                pred = "◎" if row["predicted"] == 1 else "  "
                actual = "★" if row["actual"] == 1 else "  "
                past = int(row["past_appearances"])
                group = row["group"] if pd.notna(row["group"]) else ""
                group_short = (
                    "紅" if group == "紅組" else ("白" if group == "白組" else "  ")
                )
                print(
                    f"  {rank:4d}. {pred:>2} {actual:>2} {group_short:>4} {row['artist'][:20]:20s} "
                    f"{prob:.3f} {past:6d}回"
                )

            print("-" * 80)
            print("  ◎: モデルが出場と予測  ★: 実際に出場発表  紅/白: 紅組/白組")
        else:
            print("\n  Top 50 予測確率ランキング:")
            print("-" * 70)
            for _, row in df_candidates.head(50).iterrows():
                rank = int(row["pred_rank"])
                prob = row["predicted_prob"]
                pred = "◎" if row["predicted"] == 1 else "  "
                past = int(row["past_appearances"])
                spotify = "S" if row["has_spotify_data"] == 1 else " "
                print(
                    f"  {rank:2d}. {pred} {row['artist'][:20]:20s} "
                    f"確率:{prob:.3f} 過去出場:{past:2d}回 {spotify}"
                )

            print("-" * 70)
            print("  ◎: モデルが出場と予測  S: Spotifyデータあり")

        # 結果保存
        output_path = self.analysis_dir / "predictions_2025.csv"
        df_candidates.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"\n  予測結果を保存: {output_path}")

        # ========== [6] 発表済み出場者の予測順位 ==========
        if len(actual_artists_2025) > 0:
            print("\n[6] 発表済み出場者の予測順位")
            df_actual = df_candidates[df_candidates["actual"] == 1].copy()
            df_actual = df_actual.sort_values("pred_rank")

            print(f"\n  発表済み出場者 {len(df_actual)}組の予測順位:")
            print("-" * 70)
            for _, row in df_actual.iterrows():
                rank = int(row["pred_rank"])
                prob = row["predicted_prob"]
                pred = "◎" if row["predicted"] == 1 else "  "
                group = row["group"] if pd.notna(row["group"]) else ""
                group_short = (
                    "紅" if group == "紅組" else ("白" if group == "白組" else "  ")
                )
                print(
                    f"  {rank:4d}位 {pred} {group_short:>2} {row['artist'][:25]:25s} 確率:{prob:.3f}"
                )
            print("-" * 70)

            # 精度評価
            print("\n[7] 予測精度評価")
            avg_rank = df_actual["pred_rank"].mean()
            median_rank = df_actual["pred_rank"].median()
            min_rank = df_actual["pred_rank"].min()
            max_rank = df_actual["pred_rank"].max()

            print("  発表済み出場者の予測順位:")
            print(f"    平均: {avg_rank:.1f}位")
            print(f"    中央値: {median_rank:.1f}位")
            print(f"    最高: {min_rank}位 / 最低: {max_rank}位")

            # Top N に何人入っているか
            for n in [20, 30, 40, 50, 100]:
                count_in_top_n = (df_actual["pred_rank"] <= n).sum()
                pct = count_in_top_n / len(df_actual) * 100
                print(
                    f"    Top {n:3d} に含まれる出場者: {count_in_top_n:2d}/{len(df_actual)} ({pct:.1f}%)"
                )

            # モデル予測との一致
            predicted_correct = (df_actual["predicted"] == 1).sum()
            print("\n  モデル出場予測との一致:")
            print(
                f"    発表済み出場者のうち出場予測: {predicted_correct}/{len(df_actual)} "
                f"({predicted_correct / len(df_actual) * 100:.1f}%)"
            )

        # ========== [8] 統計情報 ==========
        print(f"\n[{'8' if len(actual_artists_2025) > 0 else '6'}] 統計情報")
        print(f"  出場予測数: {len(df_predicted)}")
        print(f"  うちSpotifyデータあり: {int(df_predicted['has_spotify_data'].sum())}")
        print(f"  うち紅白経験者: {int((df_predicted['past_appearances'] > 0).sum())}")
        print(f"  うち前年出場者: {int(df_predicted['prev_year_appeared'].sum())}")

        print(f"\n{'=' * 60}")
        print("Step 7 完了")
        print("=" * 60)

        return True


def main():
    """スタンドアロン実行用のエントリーポイント"""
    config = load_config()
    data_dir = Path(__file__).parent.parent / config["paths"]["data_dir"]

    pipeline = Step7Pipeline(config, data_dir)
    success = pipeline.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
