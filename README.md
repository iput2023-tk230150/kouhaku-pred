# NHK紅白歌合戦 出演者予測システム

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)

NHK紅白歌合戦の出場者選考において、最も重要視されているのかを指標を定量的に明らかにするプロジェクト。

## プロジェクト目的

- **選考基準の定量分析**: どの指標が出場判断に影響しているか

## データソース

- **Spotifyチャートデータ**: [kworb.net](https://kworb.net/spotify/) (2016-2025年)
  - 日本国内の週次チャートランキング
  - ストリーミング数、チャート滞在週数など
- **紅白歌合戦出場者**: Wikipedia MediaWiki API
  - 過去の出場履歴
  - 出場回数、連続出場年数など
- **Googleトレンドデータ**: [pytrends](https://github.com/GeneralMills/pytrends)
  - 日本国内のアーティスト検索トレンド
  - 平均関心度、ピーク関心度、関心度の変動性

## クイックスタート

### 必要要件

- Python 3.12以上
- uv (Pythonパッケージマネージャー)

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/kouhaku-predictor.git
cd kouhaku-predictor/kouhaku-pred

# パッケージをインストール
uv sync
```

### パイプライン実行

```bash
cd kouhaku-pred

# 全ステップ実行（Step1〜8）
uv run python -m src.main

# ステップ１～４実行
uv run python -m src.main -s 1 -e 4

# ステップ５以降実行
uv run python -m src.main -5

# 週次データ取得の曲数設定
uv run python -m src.main -n 500

# 個別実行
uv run python -m src.collectors.step1_get_song_list    # 曲リスト取得
uv run python -m src.collectors.step2_get_weekly_data  # 週次データ取得（数時間かかります）
uv run python -m src.collectors.step3_get_kouhaku_artists  # 紅白出場者リスト取得
uv run python -m src.collectors.step4_get_google_trends    # Googleトレンド取得
uv run python -m src.processing.step5_create_learning_data # 学習データ作成
uv run python -m src.modeling.step6_train_model        # モデル学習
uv run python -m src.modeling.step7_shap_analysis      # SHAP分析
uv run python -m src.prediction.step8_predict_2025     # 2025年予測
```

## プロジェクト構成

```
kouhaku-pred/
├── src/                     # ソースコード
│   ├── main.py              # パイプライン制御
│   ├── core/                # パイプライン基底クラス
│   ├── collectors/          # データ収集（Step 1-4）
│   ├── processing/          # データ加工（Step 5）
│   ├── modeling/            # モデル学習・分析（Step 6-7）
│   └── prediction/          # 最終予測（Step 8）
│
├── utils/                   # 正規化・マッピングユーティリティ
├── models/                  # 学習済みモデル（model.pkl）
├── tmp/                     # ツール出力用一時ファイル
├── config.toml              # 設定ファイル
├── pyproject.toml           # プロジェクト設定
│
└── data/                    # 収集データ（.gitignoreで除外）
    ├── raw/                 # Step 1-4の出力
    │   ├── spotify/         # jp_songs_list.csv, jp_weekly_data.csv, jp_yearly_stats.csv
    │   ├── kouhaku/         # kouhaku_artists.csv
    │   └── google_trends/   # artist_trends.csv
    ├── processed/           # Step 5の出力（learning_data.csv）
    └── analysis/            # Step 6-8の分析結果（CSV, PNG）
```

## データパイプライン

```
Step 1: 曲リスト取得 (kworb.net)
   ↓
Step 2: 週次チャートデータ取得
   ↓
Step 3: 紅白出場者リスト取得 (Wikipedia)
   ↓
Step 4: Googleトレンド取得 (pytrends)
   ↓
Step 5: 学習データ作成
   ↓
Step 6: モデル学習 (LightGBM)
   ↓
Step 7: SHAP分析
   ↓
Step 8: 2025年予測
   ↓
予測結果 (data/analysis/predictions_2025.csv)
```

## 設定のカスタマイズ

`config.toml` で以下を調整できます：

- **target_years**: データ収集対象年
- **top_n_songs**: Step2の取得曲数制限（テスト時は100推奨、本番はNone）
- **spotify_defaults**: データ欠損時のデフォルト値
- **network**: タイムアウト、リクエスト間隔など

## 学習データの構造

| カテゴリ | 特徴量 |
|---------|--------|
| **Spotify特徴量** | weeks_on_chart, total_streams, best_rank, avg_rank, top10_weeks, top1_weeks |
| **Googleトレンド特徴量** | trend_avg_interest, trend_peak_interest, trend_volatility |
| **紅白履歴特徴量** | past_appearances, prev_year_appeared, consecutive_years |
| **目的変数** | appeared (0/1) |

## 注意事項

### データ収集について

- kworb.netのデータ使用は同サイトのFAQで許可されています
- 適切なリクエスト間隔（デフォルト1秒）を設定しています
- 学術研究・個人利用目的での使用を想定しています