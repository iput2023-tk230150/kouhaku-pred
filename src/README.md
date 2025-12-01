# NHK紅白歌合戦 出演者予測システム

NHK紅白歌合戦の出場者を予測するための機械学習システム

## インストール

```bash
cd src
uv pip install -e .
```

## 使い方

### パイプライン実行

kworb.netからSpotifyチャートデータと、WikipediaからNHK紅白歌合戦の出場者データを取得します。

```bash
# 全ステップ実行（Step1～4）
python main.py
# または
kouhaku

# 特定のステップのみ実行
python main.py --steps 1 2

# Step2以降を実行
python main.py --from 2
```

### 個別ステップ実行

```bash
# Step 1: 曲リスト取得
step1

# Step 2: 週次データ取得（注: 全データで数時間かかります）
step2

# Step 3: 紅白出場者リスト取得
step3

# Step 4: 学習データ作成
step4
```

## データフロー

```
Step 1 → data/jp_songs_list.csv
  ↓
Step 2 → data/jp_weekly_data.csv, data/jp_yearly_stats.csv
  ↓
Step 3 → data/kouhaku_artists.csv
  ↓
Step 4 → data/learning_data.csv (最終学習データ)
```

## 設定ファイル

`config.toml` で以下の設定をカスタマイズできます：

- **target_years**: データ収集対象年
- **top_n_songs**: Step2の取得曲数制限（テスト用）
- **spotify_defaults**: Spotifyデータ欠損時のデフォルト値

## 補助ツール

### アーティスト名マッピング作成

紅白とSpotifyのアーティスト名の表記揺れを解決するための対応表を作成します。

```bash
kouhaku-mapper
```

手動で修正が必要な場合は、`manual_mapping.csv`を編集してから再実行してください。

### kworb.net構造デバッグ

kworb.netのページ構造を確認するためのデバッグツールです。

```bash
debug-kworb [URL]
```

URLを省略した場合は、デフォルトのテストURLが使用されます。

## ディレクトリ構成

```
src/
├── kouhaku/              # コアパッケージ
│   ├── normalizer.py     # アーティスト名正規化
│   ├── mapper.py         # マッピング処理
│   └── pipeline.py       # パイプライン基底クラス
├── scripts/              # データ収集スクリプト
│   ├── step1_get_song_list.py
│   ├── step2_get_weekly_data.py
│   ├── step3_get_kouhaku_artists.py
│   └── step4_create_learning_data.py
├── ref/                  # 補助ツール
│   ├── create_mapping.py # アーティスト名マッピング作成
│   └── debug_kworb.py    # デバッグツール
├── main.py               # パイプライン制御スクリプト
├── config.toml           # 設定ファイル
└── pyproject.toml        # パッケージ定義
```

## トラブルシューティング

### Step2でタイムアウトが発生する

`config.toml`の`top_n_songs`を100程度に設定してテストしてください。

### アーティスト名がマッチしない

1. `kouhaku-mapper`を実行
2. `artist_name_mapping_draft.csv`を確認
3. 必要に応じて`manual_mapping.csv`を作成・編集
4. 再度`kouhaku-mapper`を実行

### データが見つからない

依存関係を確認してください：
- Step2はStep1の出力が必要
- Step4はStep2とStep3の出力が必要