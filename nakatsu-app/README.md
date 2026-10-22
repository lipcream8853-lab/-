# 中津花市場 買い上げ伝票・請求書アプリ

Python + Flask + SQLite。1台のPCで動作し、ブラウザで操作・印刷します。

## 起動
    pip install -r requirements.txt
    python app.py        # http://127.0.0.1:5000 を開く

## 機能
- マスタ: 取引先(締め日つき)・品目(税率8%/10%)
- 買い上げ伝票: 入力・修正・印刷
- 請求書: 月次締め処理(取引先ごとの締め日対応)、前回残高・入金、税率別消費税(切り捨て)、印刷、取り消し
- 集計: 日別/取引先別/品目別、CSV出力(Excel対応)
- 設定: 会社情報・インボイス登録番号、バックアップ(data/backups)

データは `data/nakatsu.db`(SQLite)。テスト: `python -m pytest tests`
