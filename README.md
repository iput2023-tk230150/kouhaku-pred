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
cd kouhaku-predictor

# パッケージをインストール
cd src
uv pip install -e .
```

### データ収集

```bash
# 全ステップ実行（Step1～4）
python main.py

# または個別実行
step1  # 曲リスト取得
step2  # 週次データ取得（数時間かかります）
step3  # 紅白出場者リスト取得
step4  # 学習データ作成
```

詳細な使い方は [src/README.md](src/README.md) を参照してください。

## 📁 プロジェクト構成

```
kouhaku-predictor/
├── src/                  # メインのPythonパッケージ
│   ├── kouhaku/         # コアモジュール（正規化、マッピング、パイプライン）
│   ├── scripts/         # データ収集スクリプト（Step1-4）
│   ├── ref/             # 補助ツール
│   ├── main.py          # パイプライン制御
│   └── config.toml      # 設定ファイル
├── data/                # 収集データ（.gitignoreで除外）
├── notebooks/           # 分析用Jupyter notebook
├── models/              # 学習済みモデル
└── docs/                # 追加ドキュメント
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
学習データ (data/learning_data.csv)
```

## 🛠️ 設定のカスタマイズ

`src/config.toml` で以下を調整できます：

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

- [ ] Step 5: モデル学習（LightGBM/XGBoost）
- [ ] Step 6: Feature Importance分析
- [ ] Step 7: 2025年予測
- [ ] 時系列クロスバリデーション
- [ ] SHAP値による解釈可能性分析

## ⚠️ 注意事項

### データ収集について

- kworb.netのデータ使用は同サイトのFAQで許可されています
- 適切なリクエスト間隔（デフォルト2秒）を設定しています
- 学術研究・個人利用目的での使用を想定しています

### 制限事項

- Spotifyデータがない演歌・伝統音楽アーティストは特徴量が0になります
- CDセールス、TV出演、NHKへの貢献度などのデータは含まれていません
- 名前の表記揺れにより一部のアーティストがマッチしない可能性があります

## 📝 ライセンス

MIT License - 詳細は [LICENSE](LICENSE) を参照

## 🤝 貢献

Issue、Pull Requestを歓迎します。

- バグ報告
- 新機能の提案
- ドキュメントの改善
- コードの最適化

## 📚 参考資料

- [CLAUDE.md](CLAUDE.md): Claude Code用のプロジェクトガイド
- [src/README.md](src/README.md): 詳細な使用方法
- [data/README.md](data/README.md): データファイルの説明

## 👤 作者

- GitHub: [@yourusername](https://github.com/yourusername)

## 🙏 謝辞

- [kworb.net](https://kworb.net/spotify/): Spotifyチャートデータの提供
- [Wikipedia](https://ja.wikipedia.org/): 紅白歌合戦の情報源