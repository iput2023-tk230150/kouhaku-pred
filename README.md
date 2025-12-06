# NHK紅白歌合戦 出演者予測システム

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

NHK紅白歌合戦の出場者選考において、どの指標（ストリーミング数、過去出場履歴など）が最も重要視されているのかを定量的に明らかにする機械学習プロジェクト。

## 🎯 プロジェクト目的

- **選考基準の定量分析**: どの指標が出場判断に影響しているか
- **Feature Importance分析**: 「何が重視されているか」を数値で明らかにする
- **時代の変遷の証明**: CD全盛期→ストリーミング時代への移行を定量的に示す

## 📊 データソース

- **Spotifyチャートデータ**: [kworb.net](https://kworb.net/spotify/) (2016-2024年)
  - 日本国内の週次チャートランキング
  - ストリーミング数、チャート滞在週数など
- **紅白歌合戦出場者**: Wikipedia MediaWiki API
  - 過去の出場履歴
  - 出場回数、連続出場年数など

## 🚀 クイックスタート

### 必要要件

- Python 3.12以上
- uv (Pythonパッケージマネージャー)

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/kouhaku-predictor.git
cd kouhaku-predictor/kouhaku-pred

# パッケージをインストール
uv pip install -e .
```

### パイプライン実行

```bash
cd kouhaku-pred

# 全ステップ実行（Step1〜7）
uv run python main.py

# 個別実行
uv run python -m collectors.step1_get_song_list    # 曲リスト取得
uv run python -m collectors.step2_get_weekly_data  # 週次データ取得（数時間かかります）
uv run python -m collectors.step3_get_kouhaku_artists  # 紅白出場者リスト取得
uv run python -m processing.step4_create_learning_data # 学習データ作成
uv run python -m modeling.step5_train_model        # モデル学習
uv run python -m modeling.step6_shap_analysis      # SHAP分析
uv run python -m prediction.step7_predict_2025     # 2025年予測
```

## 📁 プロジェクト構成

```
kouhaku-pred/
├── main.py              # パイプライン制御
├── config.toml          # 設定ファイル
├── pyproject.toml       # プロジェクト設定
│
├── core/                # パイプライン基底クラス
├── collectors/          # データ収集（Step 1-3）
├── processing/          # データ加工（Step 4）
├── modeling/            # モデル学習・分析（Step 5-6）
├── prediction/          # 最終予測（Step 7）
├── utils/               # 正規化・マッピングユーティリティ
├── tools/               # デバッグ・補助ツール
│
├── models/              # 学習済みモデル（model.pkl）
├── tmp/                 # ツール出力用一時ファイル
│
└── data/                # 収集データ（.gitignoreで除外）
    ├── raw/             # Step 1-3の出力（スクレイピングデータ）
    ├── processed/       # Step 4の出力（learning_data.csv）
    └── analysis/        # Step 5-7の分析結果（CSV, PNG）
```

## 🔄 データパイプライン

```
Step 1: 曲リスト取得 (kworb.net)
   ↓
Step 2: 週次チャートデータ取得
   ↓
Step 3: 紅白出場者リスト取得 (Wikipedia)
   ↓
Step 4: 学習データ作成
   ↓
Step 5: モデル学習 (LightGBM)
   ↓
Step 6: SHAP分析
   ↓
Step 7: 2025年予測
   ↓
予測結果 (data/analysis/predictions_2025.csv)
```

## 🛠️ 設定のカスタマイズ

`config.toml` で以下を調整できます：

- **target_years**: データ収集対象年
- **top_n_songs**: Step2の取得曲数制限（テスト時は100推奨、本番はNone）
- **spotify_defaults**: データ欠損時のデフォルト値
- **network**: タイムアウト、リクエスト間隔など

## 📊 学習データの構造

| カテゴリ | 特徴量 |
|---------|--------|
| **Spotify特徴量** | weeks_on_chart, total_streams, best_rank, avg_rank, top10_weeks, top1_weeks |
| **紅白履歴特徴量** | past_appearances, prev_year_appeared, consecutive_years |
| **目的変数** | appeared (0/1) |

## 🤖 今後の実装（TODO）

- [x] Step 5: モデル学習（LightGBM）
- [x] Step 6: SHAP分析
- [x] Step 7: 2025年予測

## ⚠️ 注意事項

### データ収集について

- kworb.netのデータ使用は同サイトのFAQで許可されています
- 適切なリクエスト間隔（デフォルト1秒）を設定しています
- 学術研究・個人利用目的での使用を想定しています

### 制限事項

- Spotifyデータがない演歌・伝統音楽アーティストは特徴量が0になります
- CDセールス、TV出演、NHKへの貢献度などのデータは含まれていません
- 名前の表記揺れにより一部のアーティストがマッチしない可能性があります

## 📝 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照

## 🙏 謝辞

- [kworb.net](https://kworb.net/spotify/): Spotifyチャートデータの提供
- [Wikipedia](https://ja.wikipedia.org/): 紅白歌合戦の情報源