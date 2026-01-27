# kworb.net

## 概要

kworb.netはSpotifyのチャートデータを集計・公開しているサイトです。
本プロジェクトでは、日本のSpotifyチャートデータを取得するために使用しています。

- **対象Step**: Step 1（曲リスト取得）、Step 2（週次データ取得）
- **取得内容**: 日本チャートの曲情報、週次ランキング・ストリーム数

## データソース

| 項目 | 内容 |
|------|------|
| サイト | [kworb.net](https://kworb.net/) |
| 曲リストURL | https://kworb.net/spotify/country/jp_daily_totals.html |
| 週次データURL | https://kworb.net/spotify/track/{track_id}.html |
| ライセンス | サイトFAQにて非商用利用を許可 |

## Step 1: 曲リスト取得

### 処理内容

1. kworb.netの日本チャートページにアクセス
2. テーブルをパースしてTrack ID、Artist IDを抽出
3. 曲の詳細情報（ピークランク、ストリーミング数等）を収集

### 使用ライブラリ

- `requests`: HTTPリクエスト
- `beautifulsoup4`: HTMLパース

### 出力ファイル

**ファイル**: `data/raw/spotify/jp_songs_list.csv`

| カラム | 説明 |
|--------|------|
| track_id | SpotifyのトラックID |
| artist_id | SpotifyのアーティストID |
| artist | アーティスト名 |
| title | 曲名 |
| days | チャートイン日数 |
| t10 | Top10入り日数 |
| peak | 最高順位 |
| pk_streams | ピーク時ストリーム数 |
| total | 累計ストリーム数 |

## Step 2: 週次データ取得

### 処理内容

1. Step 1で取得した各曲について、個別ページにアクセス
2. Weekly JPテーブルから週次ランキングとストリーム数を抽出
3. 日付に基づいて審査年度を計算
4. 年別・アーティスト別の統計を集計

### 依存ファイル

- `data/raw/spotify/jp_songs_list.csv`（Step 1の出力）

### 出力ファイル

**ファイル1**: `data/raw/spotify/jp_weekly_data.csv`

| カラム | 説明 |
|--------|------|
| date | 日付 |
| year | 審査年度 |
| jp_rank | 日本チャート順位 |
| jp_streams | ストリーム数 |
| track_id | トラックID |
| artist | アーティスト名 |
| title | 曲名 |

**ファイル2**: `data/raw/spotify/jp_yearly_stats.csv`

| カラム | 説明 |
|--------|------|
| artist | アーティスト名 |
| year | 審査年度 |
| weeks_on_chart | チャートイン週数 |
| total_streams | 累計ストリーム数 |
| best_rank | 最高順位 |
| avg_rank | 平均順位 |
| top10_weeks | Top10入り週数 |
| top1_weeks | 1位獲得週数 |

## 設定項目

`config.toml`で以下の設定が可能です。

```toml
[data_collection]
top_n_songs = 500  # Step 2で取得する曲数（Noneで全曲）

[network]
request_timeout = 30  # タイムアウト（秒）
request_interval = 1  # リクエスト間隔（秒）
```

## 注意点・制限事項

### 実行時間

- Step 1: 数分程度
- Step 2: 6000曲全取得で**数時間**かかる
- テスト時は`top_n_songs = 100`程度を推奨

### リクエスト制限

- 高負荷回避のため、リクエスト間隔を1秒以上に設定
- サーバーへの負荷軽減にご協力ください

### その他

- HTMLテーブル構造の変更により、パースが失敗する可能性あり
- 差分取得機能あり（既存データの再取得を回避）
- エンコーディング: UTF-8 BOM付き（utf-8-sig）

## 審査年度の計算

11月第4週木曜日を境界として年度を区切ります（ビルボードジャパン準拠）。

例:
- 2025年紅白 → 2024年11月28日（木）〜 2025年11月26日（水）
- 2024年紅白 → 2023年11月23日（木）〜 2024年11月27日（水）
