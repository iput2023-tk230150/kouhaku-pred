"""
Step 7: SHAP値分析スクリプト
================================
学習済みモデルの解釈可能性を高めるためのSHAP値分析

入力:
- models/model.pkl: 学習済みモデル
- data/processed/learning_data.csv: 学習データ

出力:
- data/analysis/shap_summary.png: SHAP summary plot
- data/analysis/shap_importance.csv: SHAP値ベースの特徴量重要度
- data/analysis/shap_dependence_*.png: 依存性プロット
"""

import pickle
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from src.core.pipeline import DataPipeline, load_config


class Step7Pipeline(DataPipeline):
    """Step7: SHAP値分析パイプライン"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        super().__init__(config, data_dir)
        self.processed_dir = data_dir / "processed"
        # models_dirはdata_dirの外（プロジェクトルート直下）
        project_root = data_dir.parent
        self.models_dir = project_root / config["paths"]["models_dir"]
        self.analysis_dir = data_dir / "analysis"
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        # 特徴量カラム（基本）
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
        # Googleトレンド特徴量（オプション）
        self.trends_feature_cols = [
            "trend_avg_interest",
            "trend_peak_interest",
            "trend_volatility",
        ]

    def get_output_files(self) -> list[Path]:
        return [
            self.analysis_dir / "shap_summary.png",
            self.analysis_dir / "shap_importance.csv",
        ]

    def check_dependencies(self) -> tuple[bool, list[str]]:
        model_file = self.models_dir / "model.pkl"
        learning_data_file = self.processed_dir / "learning_data.csv"

        missing = []
        if not model_file.exists():
            missing.append(str(model_file))
        if not learning_data_file.exists():
            missing.append(str(learning_data_file))

        return len(missing) == 0, missing

    def execute(self) -> bool:
        """パイプライン実行"""
        # 依存チェック
        ok, missing = self.check_dependencies()
        if not ok:
            print("エラー: 依存ファイルが見つかりません:")
            for f in missing:
                print(f"  - {f}")
            print("先に step5 を実行してください")
            return False

        # ========== [1] データ・モデル読み込み ==========
        print("\n[1] データ・モデル読み込み")

        # モデル読み込み
        with open(self.models_dir / "model.pkl", "rb") as f:
            model = pickle.load(f)
        print("  モデルを読み込みました")

        # 学習データ読み込み
        df = pd.read_csv(self.processed_dir / "learning_data.csv")

        # Googleトレンド特徴量が存在すれば追加
        for col in self.trends_feature_cols:
            if col in df.columns and col not in self.feature_cols:
                self.feature_cols.append(col)
        print(f"  使用特徴量: {len(self.feature_cols)}個")

        # 紅白データがある年のみ使用
        df_with_kouhaku = df[df.groupby("year")["appeared"].transform("sum") > 0]
        X = df_with_kouhaku[self.feature_cols]

        print(f"  データ: {len(X)}件")

        # ========== [2] SHAP値計算 ==========
        print("\n[2] SHAP値計算")

        # TreeExplainerを使用（LightGBM用）
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X)

        # LightGBMの場合、shap_valuesはリスト[負クラス, 正クラス]の場合がある
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # 正クラス（出場）のSHAP値を使用

        print(f"  SHAP値の形状: {shap_values.shape}")

        # ========== [3] SHAP Summary Plot ==========
        print("\n[3] SHAP Summary Plot作成")

        plt.figure(figsize=(10, 8))
        shap.summary_plot(
            shap_values,
            X,
            feature_names=self.feature_cols,
            show=False,
            plot_size=(10, 8),
        )
        plt.tight_layout()
        summary_path = self.analysis_dir / "shap_summary.png"
        plt.savefig(summary_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  保存: {summary_path}")

        # ========== [4] SHAP値ベース特徴量重要度 ==========
        print("\n[4] SHAP値ベース特徴量重要度")

        # 各特徴量の平均絶対SHAP値
        shap_importance = np.abs(shap_values).mean(axis=0)
        df_shap_importance = pd.DataFrame(
            {
                "feature": self.feature_cols,
                "mean_abs_shap": shap_importance,
                "importance_pct": shap_importance / shap_importance.sum() * 100,
            }
        ).sort_values("mean_abs_shap", ascending=False)

        print("\n  SHAP値ベース特徴量重要度ランキング:")
        for _, row in df_shap_importance.iterrows():
            bar = "#" * int(row["importance_pct"] / 2)
            print(f"    {row['feature']:20s}: {row['importance_pct']:5.1f}% {bar}")

        importance_path = self.analysis_dir / "shap_importance.csv"
        df_shap_importance.to_csv(importance_path, index=False, encoding="utf-8-sig")
        print(f"\n  保存: {importance_path}")

        # ========== [5] 上位特徴量の依存性プロット ==========
        print("\n[5] 依存性プロット作成")

        top_features = df_shap_importance.head(4)["feature"].tolist()

        for feature in top_features:
            plt.figure(figsize=(8, 6))
            shap.dependence_plot(
                feature,
                shap_values,
                X,
                feature_names=self.feature_cols,
                show=False,
            )
            plt.title(f"SHAP Dependence: {feature}")
            plt.tight_layout()
            dep_path = self.analysis_dir / f"shap_dependence_{feature}.png"
            plt.savefig(dep_path, dpi=150, bbox_inches="tight")
            plt.close()
            print(f"  保存: {dep_path}")

        # ========== [6] Bar Plot（重要度比較） ==========
        print("\n[6] 重要度バープロット作成")

        plt.figure(figsize=(10, 6))
        shap.summary_plot(
            shap_values,
            X,
            feature_names=self.feature_cols,
            plot_type="bar",
            show=False,
        )
        plt.tight_layout()
        bar_path = self.analysis_dir / "shap_bar.png"
        plt.savefig(bar_path, dpi=150, bbox_inches="tight")
        plt.close()
        print(f"  保存: {bar_path}")

        # ========== [7] 個別予測の説明（2024年Top予測） ==========
        print("\n[7] 2024年予測の個別説明")

        df_2024 = df[df["year"] == 2024].copy()
        if len(df_2024) > 0:
            X_2024 = df_2024[self.feature_cols]
            shap_2024 = explainer.shap_values(X_2024)
            if isinstance(shap_2024, list):
                shap_2024 = shap_2024[1]

            # 予測確率を計算
            probs = model.predict_proba(X_2024)[:, 1]
            df_2024["predicted_prob"] = probs

            # Top5アーティストを表示
            top5 = df_2024.nlargest(5, "predicted_prob")

            print("\n  2024年 予測確率Top5の特徴量寄与:")
            for idx, (_, row) in enumerate(top5.iterrows()):
                print(
                    f"\n  [{idx + 1}] {row['artist']} (確率: {row['predicted_prob']:.3f})"
                )

                # このアーティストのSHAP値
                artist_idx = df_2024.index.get_loc(row.name)
                artist_shap = shap_2024[artist_idx]

                # 寄与が大きい順にソート
                sorted_idx = np.argsort(np.abs(artist_shap))[::-1]
                for i in sorted_idx[:3]:
                    feature = self.feature_cols[i]
                    value = row[feature]
                    shap_val = artist_shap[i]
                    direction = "+" if shap_val > 0 else "-"
                    print(
                        f"      {feature}: {value:.0f} ({direction}{abs(shap_val):.3f})"
                    )

        print(f"\n{'=' * 60}")
        print("Step 6 完了")
        print("=" * 60)

        return True


def main():
    """スタンドアロン実行用のエントリーポイント"""
    config = load_config()
    data_dir = Path(__file__).parent.parent.parent / config["paths"]["data_dir"]

    pipeline = Step7Pipeline(config, data_dir)
    success = pipeline.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
