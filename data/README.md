# データディレクトリ

このディレクトリには、データ収集パイプラインで生成されるCSVファイルが保存されます。

## 📁 ファイル一覧

| ファイル名 | 説明 | サイズ目安 | 生成元 |
|-----------|------|-----------|--------|
| `jp_songs_list.csv` | 日本の楽曲リスト（Track ID含む） | ~6000曲 | Step 1 |
| `jp_weekly_data.csv` | 週次チャートデータ（全曲×全週） | ~数十万行 | Step 2 |
| `jp_yearly_stats.csv` | 年次集計データ（アーティスト×年） | ~数千行 | Step 2 |
| `kouhaku_artists.csv` | 紅白出場者リスト（年別） | ~200-300行 | Step 3 |
| `learning_data.csv` | 最終学習データ | ~数千行 | Step 4 |
| `artist_name_mapping.csv` | 表記揺れ対応表 | ~100-200行 | kouhaku-mapper |
| `artist_name_mapping_draft.csv` | 手動確認用候補 | 可変 | kouhaku-mapper |
| `unmatched_artists.csv` | マッチしなかったアーティスト | 可変 | kouhaku-mapper |

## 🔄 データフロー

```
Step 1 → jp_songs_list.csv
   ↓
Step 2 → jp_weekly_data.csv + jp_yearly_stats.csv
   ↓                                ↓
Step 3 → kouhaku_artists.csv       ↓
   ↓                                ↓
   └────────→ Step 4 ←──────────────┘
                ↓
         learning_data.csv
```

## ⚠️ 注意事項

### Gitでの管理

- これらのCSVファイルは `.gitignore` で除外されているため、**Gitにコミットされません**
- データを再生成するには `python main.py` を実行してください
- 初回実行時はStep2で**数時間かかります**（`config.toml`の`top_n_songs`を調整可能）

### データサイズ

- `jp_weekly_data.csv`: 数十MB～100MB超（曲数×週数による）
- その他のファイル: 数MB程度

### データの永続化が必要な場合

本番環境やチーム共有が必要な場合は以下の方法を検討してください：

1. **Git LFS（Large File Storage）**を使用
2. **クラウドストレージ**（Google Drive, S3など）に保存してリンク共有
3. **データベース**（PostgreSQL, MySQLなど）に格納

## 📊 データスキーマ

### jp_songs_list.csv

| カラム | 型 | 説明 |
|-------|---|------|
| track_id | string | Spotify Track ID |
| artist_id | string | Spotify Artist ID |
| artist | string | アーティスト名 |
| title | string | 曲名 |
| days | int | チャート滞在日数 |
| t10 | int | Top10入り回数 |
| peak | int | 最高順位 |
| pk_streams | int | ピーク時ストリーミング数 |
| total | int | 累計ストリーミング数 |

### jp_yearly_stats.csv

| カラム | 型 | 説明 |
|-------|---|------|
| artist | string | アーティスト名 |
| year | int | 年 |
| weeks_on_chart | int | チャート滞在週数 |
| total_streams | int | 年間総ストリーミング数 |
| best_rank | int | 最高順位 |
| avg_rank | float | 平均順位 |
| top10_weeks | int | Top10入り週数 |
| top1_weeks | int | 1位獲得週数 |

### kouhaku_artists.csv

| カラム | 型 | 説明 |
|-------|---|------|
| year | int | 年 |
| artist | string | アーティスト名 |

### learning_data.csv

| カラム | 型 | 説明 |
|-------|---|------|
| artist | string | アーティスト名（元表記） |
| artist_normalized | string | 正規化後のアーティスト名 |
| year | int | 年 |
| weeks_on_chart | int | チャート滞在週数 |
| total_streams | int | 年間総ストリーミング数 |
| best_rank | int | 最高順位（999=データなし） |
| avg_rank | float | 平均順位 |
| top10_weeks | int | Top10入り週数 |
| top1_weeks | int | 1位獲得週数 |
| has_spotify_data | int | Spotifyデータ有無（0/1） |
| past_appearances | int | 過去の累積出場回数 |
| prev_year_appeared | int | 前年出場有無（0/1） |
| consecutive_years | int | 連続出場年数 |
| appeared | int | その年の出場有無（0/1）【目的変数】 |

## 🔧 トラブルシューティング

### データが生成されない

1. `src/config.toml` の設定を確認
2. 依存関係を確認（Step2はStep1の出力が必要）
3. ネットワーク接続を確認

### データが不完全

- Step2で中断した場合は、`jp_weekly_data.csv`を削除して再実行
- kworb.netへのリクエストが多すぎる場合は `config.toml` の `request_interval` を増やす

### 容量不足

- `top_n_songs` を小さくしてテスト実行
- 不要な古いデータを削除