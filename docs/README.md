# データ取得ドキュメント

本ドキュメントでは、紅白歌合戦出場予測モデルで使用するデータの取得方法をまとめています。

## データ収集パイプライン概要

```
Step 1 (kworb.net 曲リスト)
    ↓
Step 2 (kworb.net 週次データ) ──→ jp_yearly_stats.csv
    ↓                                  |
Step 3 (Wikipedia 紅白出場者) ←─────────┘
    ↓
Step 4 (Google Trends)
```

## データソース一覧

| Step | データソース | 取得内容 | ドキュメント |
|------|-------------|---------|-------------|
| 1, 2 | kworb.net | Spotifyチャートデータ | [kworb.md](data-sources/kworb.md) |
| 3 | Wikipedia | 紅白歌合戦出場者 | [wikipedia.md](data-sources/wikipedia.md) |
| 4 | Google Trends | 検索トレンド | [google-trends.md](data-sources/google-trends.md) |

## 実行順序

データ収集は以下の順序で実行する必要があります。

```bash
cd kouhaku-pred

# Step 1: 曲リスト取得
uv run python -m src.collectors.step1_get_song_list

# Step 2: 週次データ取得（数時間かかる）
uv run python -m src.collectors.step2_get_weekly_data

# Step 3: 紅白出場者取得
uv run python -m src.collectors.step3_get_kouhaku_artists

# Step 4: Googleトレンド取得
uv run python -m src.collectors.step4_get_google_trends
```

## 出力ファイル

| ファイル | パス | 作成Step |
|---------|------|---------|
| jp_songs_list.csv | data/raw/spotify/ | Step 1 |
| jp_weekly_data.csv | data/raw/spotify/ | Step 2 |
| jp_yearly_stats.csv | data/raw/spotify/ | Step 2 |
| kouhaku_artists.csv | data/raw/kouhaku/ | Step 3 |
| artist_trends.csv | data/raw/google_trends/ | Step 4 |
