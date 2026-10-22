"""中津花市場 買い上げ伝票・請求書アプリ (Flask + SQLite)。"""
import csv
import io
from datetime import date

from flask import (Flask, Response, abort, flash, redirect, render_template,
                   request, url_for)

import billing
import db

app = Flask(__name__)
app.secret_key = "nakatsu-local"  # ローカル運用のためflash用のみ
app.jinja_env.filters["yen"] = lambda v: f"{int(v):,}"


def q(sql, args=(), one=False):
    with db.connect() as c:
        cur = c.execute(sql, args)
        rows = cur.fetchall()
    return (rows[0] if rows else None) if one else rows


def next_no(conn, table, col):
    return (conn.execute(f"SELECT COALESCE(MAX({col}),0)+1 FROM {table}").fetchone()[0])


def company():
    return {r["key"]: r["value"] for r in q("SELECT * FROM settings")}


@app.route("/")
def index():
    today = date.today().isoformat()
    stats = q("SELECT COUNT(*) n FROM slips WHERE slip_date=?", (today,), one=True)
    unbilled = q("SELECT COUNT(*) n FROM slips WHERE invoice_id IS NULL", one=True)
    return render_template("index.html", today=today, n_today=stats["n"],
                           n_unbilled=unbilled["n"])


# ---- マスタ ----------------------------------------------------------
@app.route("/partners", methods=["GET", "POST"])
def partners():
    if request.method == "POST":
        f = request.form
        with db.connect() as c:
            try:
                if f.get("id"):
                    c.execute(
                        "UPDATE partners SET code=?,name=?,kana=?,zip=?,address=?,tel=?,"
                        "closing_day=?,note=? WHERE id=?",
                        (f["code"], f["name"], f["kana"], f["zip"], f["address"],
                         f["tel"], int(f["closing_day"]), f["note"], f["id"]))
                else:
                    c.execute(
                        "INSERT INTO partners(code,name,kana,zip,address,tel,closing_day,note)"
                        " VALUES (?,?,?,?,?,?,?,?)",
                        (f["code"], f["name"], f["kana"], f["zip"], f["address"],
                         f["tel"], int(f["closing_day"]), f["note"]))
            except Exception as e:
                flash(f"保存できません(コード重複など): {e}")
        return redirect(url_for("partners"))
    edit = q("SELECT * FROM partners WHERE id=?", (request.args.get("edit"),), one=True) \
        if request.args.get("edit") else None
    return render_template("partners.html", rows=q("SELECT * FROM partners WHERE active=1 ORDER BY code"), edit=edit)


@app.post("/partners/<int:pid>/delete")
def partner_delete(pid):
    with db.connect() as c:
        c.execute("UPDATE partners SET active=0 WHERE id=?", (pid,))
    return redirect(url_for("partners"))


@app.route("/items", methods=["GET", "POST"])
def items():
    if request.method == "POST":
        f = request.form
        with db.connect() as c:
            try:
                if f.get("id"):
                    c.execute("UPDATE items SET code=?,name=?,unit=?,default_price=?,tax_rate=? WHERE id=?",
                              (f["code"], f["name"], f["unit"], int(f["default_price"] or 0), int(f["tax_rate"]), f["id"]))
                else:
                    c.execute("INSERT INTO items(code,name,unit,default_price,tax_rate) VALUES (?,?,?,?,?)",
                              (f["code"], f["name"], f["unit"], int(f["default_price"] or 0), int(f["tax_rate"])))
            except Exception as e:
                flash(f"保存できません(コード重複など): {e}")
        return redirect(url_for("items"))
    edit = q("SELECT * FROM items WHERE id=?", (request.args.get("edit"),), one=True) \
        if request.args.get("edit") else None
    return render_template("items.html", rows=q("SELECT * FROM items WHERE active=1 ORDER BY code"), edit=edit)


@app.post("/items/<int:iid>/delete")
def item_delete(iid):
    with db.connect() as c:
        c.execute("UPDATE items SET active=0 WHERE id=?", (iid,))
    return redirect(url_for("items"))


# ---- 買い上げ伝票 ----------------------------------------------------
def slip_totals(slip_id):
    lines = q("SELECT * FROM slip_lines WHERE slip_id=?", (slip_id,))
    sub, tax = billing.tax_summary([(l["qty"], l["unit_price"], l["tax_rate"]) for l in lines])
    return lines, sub, tax


@app.route("/slips")
def slips():
    start = request.args.get("from") or date.today().replace(day=1).isoformat()
    end = request.args.get("to") or date.today().isoformat()
    rows = q("""SELECT s.*, p.name pname,
                COALESCE((SELECT SUM(qty*unit_price) FROM slip_lines WHERE slip_id=s.id),0) amount
                FROM slips s JOIN partners p ON p.id=s.partner_id
                WHERE slip_date BETWEEN ? AND ? ORDER BY slip_date DESC, slip_no DESC""", (start, end))
    return render_template("slips.html", rows=rows, start=start, end=end)


@app.route("/slips/new", methods=["GET", "POST"])
@app.route("/slips/<int:sid>/edit", methods=["GET", "POST"])
def slip_edit(sid=None):
    slip = q("SELECT * FROM slips WHERE id=?", (sid,), one=True) if sid else None
    if sid and not slip:
        abort(404)
    if slip and slip["invoice_id"]:
        flash("請求済みの伝票は編集できません。")
        return redirect(url_for("slip_view", sid=sid))
    if request.method == "POST":
        f = request.form
        names, qtys = f.getlist("item_name"), f.getlist("qty")
        prices, rates, units, iids = f.getlist("unit_price"), f.getlist("tax_rate"), f.getlist("unit"), f.getlist("item_id")
        lines = [(iids[i] or None, names[i], int(qtys[i]), units[i], int(prices[i]), int(rates[i]))
                 for i in range(len(names)) if names[i].strip() and qtys[i] and prices[i]]
        if not lines:
            flash("明細を1行以上入力してください。")
            return redirect(request.url)
        with db.connect() as c:
            if sid:
                c.execute("UPDATE slips SET slip_date=?,partner_id=?,note=? WHERE id=?",
                          (f["slip_date"], f["partner_id"], f["note"], sid))
                c.execute("DELETE FROM slip_lines WHERE slip_id=?", (sid,))
            else:
                no = next_no(c, "slips", "slip_no")
                cur = c.execute("INSERT INTO slips(slip_no,slip_date,partner_id,note) VALUES (?,?,?,?)",
                                (no, f["slip_date"], f["partner_id"], f["note"]))
                sid = cur.lastrowid
            c.executemany(
                "INSERT INTO slip_lines(slip_id,item_id,item_name,qty,unit,unit_price,tax_rate) VALUES (?,?,?,?,?,?,?)",
                [(sid, *l) for l in lines])
        return redirect(url_for("slip_view", sid=sid))
    lines = q("SELECT * FROM slip_lines WHERE slip_id=?", (sid,)) if sid else []
    return render_template("slip_form.html", slip=slip, lines=lines, today=date.today().isoformat(),
                           partners=q("SELECT * FROM partners WHERE active=1 ORDER BY code"),
                           items=q("SELECT * FROM items WHERE active=1 ORDER BY code"))


@app.route("/slips/<int:sid>")
def slip_view(sid):
    slip = q("SELECT s.*, p.name pname, p.address paddr FROM slips s JOIN partners p ON p.id=s.partner_id WHERE s.id=?",
             (sid,), one=True)
    if not slip:
        abort(404)
    lines, sub, tax = slip_totals(sid)
    return render_template("slip_view.html", slip=slip, lines=lines, sub=sub, tax=tax,
                           total=billing.invoice_total(sub, tax, 0, 0), co=company())


@app.post("/slips/<int:sid>/delete")
def slip_delete(sid):
    slip = q("SELECT * FROM slips WHERE id=?", (sid,), one=True)
    if slip and slip["invoice_id"]:
        flash("請求済みの伝票は削除できません。")
        return redirect(url_for("slip_view", sid=sid))
    with db.connect() as c:
        c.execute("DELETE FROM slips WHERE id=?", (sid,))
    return redirect(url_for("slips"))


# ---- 請求書(締め処理) ------------------------------------------------
def build_invoice(conn, partner, d_from, d_to, issue):
    sl = conn.execute(
        "SELECT id FROM slips WHERE partner_id=? AND invoice_id IS NULL AND slip_date BETWEEN ? AND ?",
        (partner["id"], d_from, d_to)).fetchall()
    if not sl:
        return None
    ids = [r["id"] for r in sl]
    marks = ",".join("?" * len(ids))
    lines = conn.execute(f"SELECT qty,unit_price,tax_rate FROM slip_lines WHERE slip_id IN ({marks})", ids).fetchall()
    sub, tax = billing.tax_summary([(l[0], l[1], l[2]) for l in lines])
    prev = conn.execute("SELECT total FROM invoices WHERE partner_id=? ORDER BY invoice_no DESC LIMIT 1",
                        (partner["id"],)).fetchone()
    prev_balance = prev["total"] if prev else 0
    no = next_no(conn, "invoices", "invoice_no")
    cur = conn.execute(
        "INSERT INTO invoices(invoice_no,partner_id,period_from,period_to,issue_date,prev_balance,payment,"
        "subtotal8,subtotal10,tax8,tax10,total) VALUES (?,?,?,?,?,?,0,?,?,?,?,?)",
        (no, partner["id"], d_from, d_to, issue, prev_balance, sub[8], sub[10], tax[8], tax[10],
         billing.invoice_total(sub, tax, prev_balance, 0)))
    conn.execute(f"UPDATE slips SET invoice_id=? WHERE id IN ({marks})", [cur.lastrowid, *ids])
    return cur.lastrowid


@app.route("/invoices", methods=["GET", "POST"])
def invoices():
    if request.method == "POST":  # 締め処理
        y, m = int(request.form["year"]), int(request.form["month"])
        issue = request.form.get("issue_date") or date.today().isoformat()
        made = 0
        with db.connect() as c:
            for p in c.execute("SELECT * FROM partners WHERE active=1").fetchall():
                a, b = billing.period_for(y, m, p["closing_day"])
                if build_invoice(c, p, a.isoformat(), b.isoformat(), issue):
                    made += 1
        flash(f"{y}年{m}月分の請求書を {made} 件作成しました。")
        return redirect(url_for("invoices"))
    rows = q("""SELECT i.*, p.name pname FROM invoices i JOIN partners p ON p.id=i.partner_id
                ORDER BY invoice_no DESC LIMIT 200""")
    t = date.today()
    return render_template("invoices.html", rows=rows, year=t.year, month=t.month, today=t.isoformat())


@app.route("/invoices/<int:iid>", methods=["GET", "POST"])
def invoice_view(iid):
    inv = q("SELECT i.*, p.name pname, p.address paddr, p.zip pzip FROM invoices i JOIN partners p ON p.id=i.partner_id WHERE i.id=?",
            (iid,), one=True)
    if not inv:
        abort(404)
    if request.method == "POST":  # 入金額の登録
        pay = int(request.form.get("payment") or 0)
        sub = {8: inv["subtotal8"], 10: inv["subtotal10"]}
        tax = {8: inv["tax8"], 10: inv["tax10"]}
        with db.connect() as c:
            c.execute("UPDATE invoices SET payment=?, total=? WHERE id=?",
                      (pay, billing.invoice_total(sub, tax, inv["prev_balance"], pay), iid))
        return redirect(url_for("invoice_view", iid=iid))
    slips_ = q("SELECT s.*, (SELECT SUM(qty*unit_price) FROM slip_lines WHERE slip_id=s.id) amount "
               "FROM slips s WHERE invoice_id=? ORDER BY slip_date, slip_no", (iid,))
    detail = q("""SELECT s.slip_date, s.slip_no, l.* FROM slip_lines l JOIN slips s ON s.id=l.slip_id
                  WHERE s.invoice_id=? ORDER BY s.slip_date, s.slip_no, l.id""", (iid,))
    return render_template("invoice_view.html", inv=inv, slips=slips_, detail=detail, co=company())


@app.post("/invoices/<int:iid>/cancel")
def invoice_cancel(iid):
    """最新の請求書のみ取り消し可能(伝票は未請求に戻る)。"""
    inv = q("SELECT * FROM invoices WHERE id=?", (iid,), one=True)
    latest = q("SELECT MAX(invoice_no) m FROM invoices WHERE partner_id=?", (inv["partner_id"],), one=True)["m"]
    if inv["invoice_no"] != latest:
        flash("その取引先の最新の請求書のみ取り消せます。")
        return redirect(url_for("invoice_view", iid=iid))
    with db.connect() as c:
        c.execute("UPDATE slips SET invoice_id=NULL WHERE invoice_id=?", (iid,))
        c.execute("DELETE FROM invoices WHERE id=?", (iid,))
    return redirect(url_for("invoices"))


# ---- 集計・帳票 -------------------------------------------------------
@app.route("/reports")
def reports():
    t = date.today()
    ym = request.args.get("ym") or f"{t.year}-{t.month:02d}"
    by_day = q("""SELECT s.slip_date d, COUNT(DISTINCT s.id) n, SUM(l.qty*l.unit_price) amount
                  FROM slips s JOIN slip_lines l ON l.slip_id=s.id
                  WHERE substr(s.slip_date,1,7)=? GROUP BY s.slip_date ORDER BY s.slip_date""", (ym,))
    by_partner = q("""SELECT p.name, SUM(l.qty*l.unit_price) amount FROM slips s
                      JOIN partners p ON p.id=s.partner_id JOIN slip_lines l ON l.slip_id=s.id
                      WHERE substr(s.slip_date,1,7)=? GROUP BY p.id ORDER BY amount DESC""", (ym,))
    by_item = q("""SELECT l.item_name name, SUM(l.qty) qty, SUM(l.qty*l.unit_price) amount FROM slips s
                   JOIN slip_lines l ON l.slip_id=s.id WHERE substr(s.slip_date,1,7)=?
                   GROUP BY l.item_name ORDER BY amount DESC""", (ym,))
    return render_template("reports.html", ym=ym, by_day=by_day, by_partner=by_partner, by_item=by_item,
                           total=sum(r["amount"] for r in by_day))


@app.route("/reports/export.csv")
def export_csv():
    ym = request.args.get("ym") or date.today().strftime("%Y-%m")
    rows = q("""SELECT s.slip_date, s.slip_no, p.code, p.name, l.item_name, l.qty, l.unit, l.unit_price,
                l.qty*l.unit_price amount, l.tax_rate
                FROM slips s JOIN partners p ON p.id=s.partner_id JOIN slip_lines l ON l.slip_id=s.id
                WHERE substr(s.slip_date,1,7)=? ORDER BY s.slip_date, s.slip_no, l.id""", (ym,))
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["日付", "伝票No", "取引先コード", "取引先名", "品名", "数量", "単位", "単価", "金額", "税率"])
    w.writerows([tuple(r) for r in rows])
    # Excelで文字化けしないようBOM付きUTF-8
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=kaiage_{ym}.csv"})


# ---- 設定・バックアップ ----------------------------------------------
@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        with db.connect() as c:
            for k in ("company_name", "company_address", "company_tel", "registration_no"):
                c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES (?,?)", (k, request.form.get(k, "")))
        flash("保存しました。")
        return redirect(url_for("settings"))
    return render_template("settings.html", co=company())


@app.post("/backup")
def backup():
    flash(f"バックアップを作成しました: {db.backup()}")
    return redirect(url_for("settings"))


db.init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
