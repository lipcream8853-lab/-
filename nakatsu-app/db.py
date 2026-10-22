"""SQLite 接続とスキーマ定義。金額はすべて整数(円)で扱う。"""
import os
import shutil
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get(
    "NAKATSU_DB", os.path.join(os.path.dirname(__file__), "data", "nakatsu.db")
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS partners (          -- 取引先(買い手)
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    kana TEXT DEFAULT '',
    zip TEXT DEFAULT '',
    address TEXT DEFAULT '',
    tel TEXT DEFAULT '',
    closing_day INTEGER NOT NULL DEFAULT 0,    -- 締め日 0=月末, 1-28=日
    note TEXT DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS items (             -- 品目
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '束',
    default_price INTEGER NOT NULL DEFAULT 0,
    tax_rate INTEGER NOT NULL DEFAULT 8,       -- 生花は軽減税率8%
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS slips (             -- 買い上げ伝票
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slip_no INTEGER UNIQUE,
    slip_date TEXT NOT NULL,
    partner_id INTEGER NOT NULL REFERENCES partners(id),
    note TEXT DEFAULT '',
    invoice_id INTEGER REFERENCES invoices(id)
);
CREATE TABLE IF NOT EXISTS slip_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slip_id INTEGER NOT NULL REFERENCES slips(id) ON DELETE CASCADE,
    item_id INTEGER REFERENCES items(id),
    item_name TEXT NOT NULL,
    qty INTEGER NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    unit_price INTEGER NOT NULL,
    tax_rate INTEGER NOT NULL DEFAULT 8
);
CREATE TABLE IF NOT EXISTS invoices (          -- 請求書
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no INTEGER UNIQUE,
    partner_id INTEGER NOT NULL REFERENCES partners(id),
    period_from TEXT NOT NULL,
    period_to TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    prev_balance INTEGER NOT NULL DEFAULT 0,   -- 前回請求残高
    payment INTEGER NOT NULL DEFAULT 0,        -- 今回入金
    subtotal8 INTEGER NOT NULL DEFAULT 0,
    subtotal10 INTEGER NOT NULL DEFAULT 0,
    tax8 INTEGER NOT NULL DEFAULT 0,
    tax10 INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0           -- 今回請求額
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY, value TEXT NOT NULL
);
"""


def connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as c:
        c.executescript(SCHEMA)
        c.execute(
            "INSERT OR IGNORE INTO settings(key,value) VALUES "
            "('company_name','中津花市場'),('company_address',''),"
            "('company_tel',''),('registration_no','')"
        )


def backup():
    """DBファイルをbackupsフォルダへ日時付きでコピーする。"""
    d = os.path.join(os.path.dirname(DB_PATH), "backups")
    os.makedirs(d, exist_ok=True)
    dst = os.path.join(d, datetime.now().strftime("nakatsu_%Y%m%d_%H%M%S.db"))
    src = sqlite3.connect(DB_PATH)
    out = sqlite3.connect(dst)
    src.backup(out)
    out.close()
    src.close()
    return dst
