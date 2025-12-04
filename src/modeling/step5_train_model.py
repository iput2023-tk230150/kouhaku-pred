"""
Step 5: モデル学習スクリプト
================================
LightGBMを使用して紅白出場予測モデルを学習

入力:
- data/processed/learning_data.csv: 学習データ

出力:
- data/models/model.pkl: 学習済みモデル
- data/analysis/feature_importance.csv: 特徴量重要度
- data/analysis/evaluation_results.csv: 評価結果
- data/analysis/predictions_2024.csv: 2024年予測結果

評価方法:
- 時系列CV: 過去の年で学習し、未来を予測
  例: 2020-2022で学習 → 2023を予測
      2020-2023で学習 → 2024を予測
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np
import pickle
import lightgbm as lgb
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    classification_report,
)
from typing import Any

from core.pipeline import DataPipeline, load_config


class Step5Pipeline(DataPipeline):
    """Step5: モデル学習パイプライン"""

    def __init__(self, config: dict[str, Any], data_dir: Path):
        super().__init__(config, data_dir)
        self.processed_dir = data_dir / "processed"
        self.models_dir = data_dir / "models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir = data_dir / "analysis"
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

        # 特徴量カラム（学習に使用）
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
        self.target_col = "appeared"

    def get_output_files(self) -> list[Path]:
        return [
            self.models_dir / "model.pkl",
            self.analysis_dir / "feature_importance.csv",
            self.analysis_dir / "evaluation_results.csv",
            self.analysis_dir / "predictions_2024.csv",
        ]

    def check_dependencies(self) -> tuple[bool, list[str]]:
        learning_data_file = self.processed_dir / "learning_data.csv"
        if not learning_data_file.exists():
            return False, [str(learning_data_file)]
        return True, []

    def execute(self) -> bool:
        """パイプライン実行"""
        print("=" * 60)
        print("Step 5: モデル学習")
        print("=" * 60)

        # 依存チェック
        ok, missing = self.check_dependencies()
        if not ok:
            print(f"エラー: 依存ファイルが見つかりません:")
            for f in missing:
                print(f"  - {f}")
            print("先に step4 を実行してください")
            return False

        # ========== [1] データ読み込み ==========
        print("\n[1] データ読み込み")
        df = pd.read_csv(self.processed_dir / "learning_data.csv")
        print(f"  総レコード数: {len(df)}")
        print(f"  対象年: {df['year'].min()} - {df['year'].max()}")

        # 紅白データがある年のみ使用（2016-2019は紅白データがない）
        df_with_kouhaku = df[df.groupby("year")["appeared"].transform("sum") > 0]
        available_years = sorted(df_with_kouhaku["year"].unique())
        print(f"  紅白データがある年: {available_years}")

        if len(available_years) < 2:
            print("エラー: 時系列CVには最低2年分のデータが必要です")
            return False

        # ========== [2] 時系列CV ==========
        print("\n[2] 時系列クロスバリデーション")
        print("  訓練: 過去の年 → テスト: 翌年")

        cv_results = []

        # 各テスト年について評価
        for i in range(1, len(available_years)):
            train_years = available_years[:i]
            test_year = available_years[i]

            print(f"\n  --- Fold {i}: 訓練={train_years}, テスト={test_year} ---")

            # 訓練・テストデータ分割
            df_train = df[df["year"].isin(train_years)]
            df_test = df[df["year"] == test_year]

            X_train = df_train[self.feature_cols]
            y_train = df_train[self.target_col]
            X_test = df_test[self.feature_cols]
            y_test = df_test[self.target_col]

            print(f"    訓練: {len(X_train)}件 (出場: {y_train.sum()}件)")
            print(f"    テスト: {len(X_test)}件 (出場: {y_test.sum()}件)")

            # LightGBMモデル学習
            model = lgb.LGBMClassifier(
                objective="binary",
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                num_leaves=31,
                min_child_samples=10,
                class_weight="balanced",  # クラス不均衡対策
                random_state=42,
                verbose=-1,
            )

            model.fit(X_train, y_train)

            # 予測
            y_pred = model.predict(X_test)
            y_prob = model.predict_proba(X_test)[:, 1]

            # 評価指標計算
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)

            print(f"    Accuracy:  {accuracy:.3f}")
            print(f"    Precision: {precision:.3f}")
            print(f"    Recall:    {recall:.3f}")
            print(f"    F1-score:  {f1:.3f}")

            # 混同行列
            cm = confusion_matrix(y_test, y_pred)
            tn, fp, fn, tp = cm.ravel()
            print(f"    混同行列: TN={tn}, FP={fp}, FN={fn}, TP={tp}")

            cv_results.append(
                {
                    "fold": i,
                    "train_years": str(train_years),
                    "test_year": test_year,
                    "train_size": len(X_train),
                    "test_size": len(X_test),
                    "accuracy": accuracy,
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "true_negatives": tn,
                    "false_positives": fp,
                    "false_negatives": fn,
                    "true_positives": tp,
                }
            )

        # ========== [3] CV結果サマリー ==========
        print("\n[3] クロスバリデーション結果サマリー")
        df_cv = pd.DataFrame(cv_results)

        print(f"\n  平均スコア:")
        print(f"    Accuracy:  {df_cv['accuracy'].mean():.3f} ± {df_cv['accuracy'].std():.3f}")
        print(f"    Precision: {df_cv['precision'].mean():.3f} ± {df_cv['precision'].std():.3f}")
        print(f"    Recall:    {df_cv['recall'].mean():.3f} ± {df_cv['recall'].std():.3f}")
        print(f"    F1-score:  {df_cv['f1'].mean():.3f} ± {df_cv['f1'].std():.3f}")

        # 評価結果保存
        eval_path = self.analysis_dir / "evaluation_results.csv"
        df_cv.to_csv(eval_path, index=False, encoding="utf-8-sig")
        print(f"\n  評価結果を保存: {eval_path}")

        # ========== [4] 最終モデル学習 ==========
        print("\n[4] 最終モデル学習（全データ使用）")

        # 紅白データがある全年で学習
        df_all = df[df["year"].isin(available_years)]
        X_all = df_all[self.feature_cols]
        y_all = df_all[self.target_col]

        print(f"  訓練データ: {len(X_all)}件 (出場: {y_all.sum()}件)")

        final_model = lgb.LGBMClassifier(
            objective="binary",
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            num_leaves=31,
            min_child_samples=10,
            class_weight="balanced",
            random_state=42,
            verbose=-1,
        )

        final_model.fit(X_all, y_all)

        # モデル保存
        model_path = self.models_dir / "model.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(final_model, f)
        print(f"  モデルを保存: {model_path}")

        # ========== [5] Feature Importance ==========
        print("\n[5] 特徴量重要度分析")

        importance = final_model.feature_importances_
        df_importance = pd.DataFrame(
            {
                "feature": self.feature_cols,
                "importance": importance,
                "importance_pct": importance / importance.sum() * 100,
            }
        ).sort_values("importance", ascending=False)

        print("\n  特徴量重要度ランキング:")
        for i, row in df_importance.iterrows():
            bar = "#" * int(row["importance_pct"] / 2)
            print(f"    {row['feature']:20s}: {row['importance_pct']:5.1f}% {bar}")

        # 重要度保存
        importance_path = self.analysis_dir / "feature_importance.csv"
        df_importance.to_csv(importance_path, index=False, encoding="utf-8-sig")
        print(f"\n  特徴量重要度を保存: {importance_path}")

        # ========== [6] 2024年の予測結果詳細 ==========
        print("\n[6] 2024年の予測結果詳細")

        # 2024年以外で学習し、2024年を予測
        train_years_for_2024 = [y for y in available_years if y != 2024]
        df_train_2024 = df[df["year"].isin(train_years_for_2024)]
        df_test_2024 = df[df["year"] == 2024]

        if len(df_test_2024) > 0:
            X_train_2024 = df_train_2024[self.feature_cols]
            y_train_2024 = df_train_2024[self.target_col]
            X_test_2024 = df_test_2024[self.feature_cols]
            y_test_2024 = df_test_2024[self.target_col]

            model_2024 = lgb.LGBMClassifier(
                objective="binary",
                n_estimators=100,
                learning_rate=0.1,
                max_depth=5,
                num_leaves=31,
                min_child_samples=10,
                class_weight="balanced",
                random_state=42,
                verbose=-1,
            )
            model_2024.fit(X_train_2024, y_train_2024)

            y_prob_2024 = model_2024.predict_proba(X_test_2024)[:, 1]

            df_pred_2024 = df_test_2024[["artist", "artist_normalized"]].copy()
            df_pred_2024["actual"] = y_test_2024.values
            df_pred_2024["predicted_prob"] = y_prob_2024
            df_pred_2024["predicted"] = (y_prob_2024 >= 0.5).astype(int)

            # 予測確率Top20
            print("\n  予測確率 Top 20:")
            top20 = df_pred_2024.nlargest(20, "predicted_prob")
            for i, row in top20.iterrows():
                actual_mark = "◯" if row["actual"] == 1 else "×"
                print(
                    f"    {row['artist']:25s}: {row['predicted_prob']:.3f} (実際: {actual_mark})"
                )

            # 予測結果保存
            pred_path = self.analysis_dir / "predictions_2024.csv"
            df_pred_2024.to_csv(pred_path, index=False, encoding="utf-8-sig")
            print(f"\n  2024年予測結果を保存: {pred_path}")

            # 分類レポート
            print("\n  分類レポート (2024年):")
            print(classification_report(y_test_2024, (y_prob_2024 >= 0.5).astype(int),
                                         target_names=["非出場", "出場"]))

        print(f"\n{'='*60}")
        print("Step 5 完了")
        print("=" * 60)

        return True


def main():
    """スタンドアロン実行用のエントリーポイント"""
    config = load_config()
    data_dir = Path(__file__).parent.parent.parent / config["paths"]["data_dir"]

    pipeline = Step5Pipeline(config, data_dir)
    success = pipeline.execute()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
