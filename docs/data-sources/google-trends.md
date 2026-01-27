# Google Trends

## 概要

pytrendsライブラリを使用して、アーティストの検索トレンドデータを取得します。

- **対象Step**: Step 4（Googleトレンド取得）
- **取得内容**: アーティスト名の検索関心度（Interest Over Time）

## データソース

| 項目 | 内容 |
|------|------|
| サービス | Google Trends |
| ライブラリ | pytrends（非公式Python API） |
| 地域 | JP（日本） |
| 基準キーワード | 「音楽」との相対比較 |

## 処理内容

1. Step 2（Spotify統計）とStep 3（紅白出場者）を統合したアーティストリストを作成
2. 各アーティストについて、審査年度の期間でトレンドデータを取得
3. 基準キーワード「音楽」と比較して相対検索量を計算
4. 平均・ピーク・変動性などの統計値を算出

### 審査年度の期間

11月第4週木曜日〜翌年11月第3週水曜日

例: 2025年紅白 → 2024年11月28日〜2025年11月26日

## 依存ファイル

- `data/raw/kouhaku/kouhaku_artists.csv`（Step 3の出力）
- `data/raw/spotify/jp_yearly_stats.csv`（Step 2の出力）
- `data/processed/mapping/final_mapping.csv`（オプション、アーティスト名マッピング）

## 使用ライブラリ

- `pytrends`: Google Trends API

## 出力ファイル

**ファイル**: `data/raw/google_trends/artist_trends.csv`

| カラム | 説明 |
|--------|------|
| artist | アーティスト名 |
| year | 審査年度 |
| trend_avg_interest | 平均関心度 |
| trend_peak_interest | ピーク関心度 |
| trend_volatility | 関心度の変動性（標準偏差） |
| trend_relative_interest | 基準キーワード比の相対値 |
| has_trends_data | 取得成功フラグ（0/1） |

## 設定項目

`config.toml`で以下の設定が可能です。

```toml
[google_trends]
enabled = true              # 取得を有効化（必須）
geo = "JP"                 # 地域（日本）
request_interval = 10      # リクエスト間隔（秒）
max_retries = 3            # リトライ回数
checkpoint_interval = 20   # 中間保存間隔（件数）
```

## 注意点・制限事項

### 有効化が必要

`config.toml`で`enabled = true`に設定しないと実行されません。

### レート制限

- Google Trendsは厳しいレート制限あり
- リクエスト間隔を10秒以上に設定推奨
- 指数バックオフリトライを実装済み

### 取得失敗時の挙動

- 取得失敗したアーティストは`has_trends_data = 0`でレコード作成
- 学習データ作成時にフラグで判別可能

### 中間保存

- 20件ごとにチェックポイント保存
- 長時間の取得でも途中経過を保持

### 今年度データ

- 今年度データは毎回更新（期間が完了していないため）

### 失敗データの再取得

```bash
# 失敗データのみ再取得
uv run python -m src.collectors.step4_get_google_trends --retry-failed
```

### その他

- 旧字体→新字体変換対応（`utils/normalizer.py`使用）
- エンコーディング: UTF-8 BOM付き（utf-8-sig）
- 未来期間（開始日が今日より後）はスキップ
