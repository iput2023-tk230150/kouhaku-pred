"""
紅白予測システム パイプライン制御スクリプト
==========================================
Step1-7を順次実行し、データ収集からモデル学習・予測まで行う

使い方:
    python main.py                    # 全ステップ実行
    python main.py --steps 1 2        # Step1,2のみ実行
    python main.py --start 3 --end 5  # Step3〜5を実行
    python main.py --start 4          # Step4以降を実行
    python main.py --end 3            # Step1〜3を実行
    python main.py --config custom.toml  # カスタム設定ファイル
"""

import sys
import argparse
from pathlib import Path
from typing import Any

from core.pipeline import load_config
from collectors.step1_get_song_list import Step1Pipeline
from collectors.step2_get_weekly_data import Step2Pipeline
from collectors.step3_get_kouhaku_artists import Step3Pipeline
from processing.step4_create_learning_data import Step4Pipeline
from modeling.step5_train_model import Step5Pipeline
from modeling.step6_shap_analysis import Step6Pipeline
from prediction.step7_predict_2025 import Step7Pipeline


# パイプライン定義
PIPELINES = {
    1: ("Step 1: 曲リスト取得", Step1Pipeline),
    2: ("Step 2: 週次データ取得", Step2Pipeline),
    3: ("Step 3: 紅白出場者リスト取得", Step3Pipeline),
    4: ("Step 4: 学習データ作成", Step4Pipeline),
    5: ("Step 5: モデル学習", Step5Pipeline),
    6: ("Step 6: SHAP分析", Step6Pipeline),
    7: ("Step 7: 2025年予測", Step7Pipeline),
}


def parse_args():
    """コマンドライン引数のパース"""
    parser = argparse.ArgumentParser(
        description="紅白予測システム データ収集パイプライン",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--steps", type=int, nargs="+", help="実行するステップ番号（例: --steps 1 2 3）"
    )

    parser.add_argument(
        "--start", type=int, help="開始ステップ番号（例: --start 3）"
    )

    parser.add_argument(
        "--end", type=int, help="終了ステップ番号（例: --end 5）"
    )

    parser.add_argument("--config", type=str, help="カスタム設定ファイルのパス")

    parser.add_argument(
        "--skip-dependency-check", action="store_true", help="依存チェックをスキップ"
    )

    return parser.parse_args()


def get_steps_to_execute(args) -> list[int]:
    """実行するステップのリストを取得"""
    if args.steps:
        return sorted(args.steps)

    # 範囲指定（--start / --end）
    start = args.start or min(PIPELINES.keys())
    end = args.end or max(PIPELINES.keys())
    return list(range(start, end + 1))


def run_pipeline(
    config: dict[str, Any], data_dir: Path, skip_dependency_check: bool = False
):
    """パイプラインを実行"""
    args = parse_args()
    steps_to_execute = get_steps_to_execute(args)

    print("=" * 70)
    print("紅白予測システム データ収集パイプライン")
    print("=" * 70)
    print(f"\n実行ステップ: {steps_to_execute}")
    print(f"データディレクトリ: {data_dir}")
    print(f"設定ファイル: {args.config if args.config else 'config.toml (デフォルト)'}")
    print()

    results = {}

    for step_num in steps_to_execute:
        if step_num not in PIPELINES:
            print(f"\n警告: Step {step_num} は存在しません。スキップします。")
            continue

        step_name, pipeline_class = PIPELINES[step_num]

        print("=" * 70)
        print(f"{step_name}")
        print("=" * 70)

        # パイプラインインスタンス作成
        pipeline = pipeline_class(config, data_dir)

        # 依存チェック
        if not skip_dependency_check:
            ok, missing = pipeline.check_dependencies()
            if not ok:
                print(f"\nエラー: Step {step_num} の依存ファイルが見つかりません:")
                for f in missing:
                    print(f"  - {f}")
                print("\n前のステップを先に実行してください。")
                results[step_num] = False
                break

        # 実行
        try:
            success = pipeline.execute()
            results[step_num] = success

            if not success:
                print(f"\nエラー: Step {step_num} が失敗しました。")
                break

            # 出力ファイル検証
            ok, missing = pipeline.validate_outputs()
            if not ok:
                print(f"\n警告: Step {step_num} の出力ファイルが見つかりません:")
                for f in missing:
                    print(f"  - {f}")

            print(f"\nStep {step_num} 完了")

        except Exception as e:
            print(f"\nエラー: Step {step_num} で例外が発生しました")
            print(f"  {type(e).__name__}: {e}")
            results[step_num] = False
            break

        print()

    # 最終サマリー
    print("=" * 70)
    print("実行結果サマリー")
    print("=" * 70)

    for step_num in steps_to_execute:
        if step_num in results:
            status = "成功" if results[step_num] else "失敗"
            step_name = PIPELINES[step_num][0]
            print(f"  Step {step_num} ({step_name}): {status}")
        else:
            print(f"  Step {step_num}: 未実行")

    all_success = all(results.get(s, False) for s in steps_to_execute)

    if all_success:
        print("\n全ステップが正常に完了しました。")
        return 0
    else:
        print("\nいくつかのステップが失敗しました。")
        return 1


def main():
    """メインエントリーポイント"""
    args = parse_args()

    # 設定ファイル読み込み
    try:
        if args.config:
            config_path = Path(args.config)
            if not config_path.is_absolute():
                config_path = Path.cwd() / config_path
            config = load_config(config_path)
        else:
            config = load_config()
    except FileNotFoundError as e:
        print(f"エラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"設定ファイル読み込みエラー: {e}")
        sys.exit(1)

    # データディレクトリ（プロジェクトルート直下）
    data_dir = Path(__file__).parent / config["paths"]["data_dir"]

    # パイプライン実行
    exit_code = run_pipeline(config, data_dir, args.skip_dependency_check)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
