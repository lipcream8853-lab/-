import os, sys, tempfile
os.environ["NAKATSU_DB"] = os.path.join(tempfile.mkdtemp(), "t.db")
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from datetime import date
import app as A, billing


def test_period():
    assert billing.period_for(2026, 2, 0) == (date(2026, 2, 1), date(2026, 2, 28))
    assert billing.period_for(2026, 3, 20) == (date(2026, 2, 21), date(2026, 3, 20))


def test_tax_rounding():
    sub, tax = billing.tax_summary([(3, 333, 8), (1, 100, 10)])
    assert sub == {8: 999, 10: 100} and tax == {8: 79, 10: 10}


def test_full_flow():
    c = A.app.test_client()
    c.post("/partners", data=dict(code="001", name="花Aフラワー", kana="", zip="", address="中津", tel="", closing_day="0", note=""))
    c.post("/items", data=dict(code="10", name="バラ", unit="束", default_price="1000", tax_rate="8"))
    data = dict(slip_date="2026-10-05", partner_id="1", note="", item_id=["1", ""], item_name=["バラ", "資材"],
                qty=["3", "2"], unit=["束", "個"], unit_price=["1000", "500"], tax_rate=["8", "10"])
    r = c.post("/slips/new", data=data)
    assert r.status_code == 302
    assert "買 上 伝 票" in c.get("/slips/1").text
    c.post("/invoices", data=dict(year="2026", month="10", issue_date="2026-10-31"))
    inv = c.get("/invoices/1").text
    assert "3,000" in inv and "1,000" in inv and "4,340" in inv  # 3000+240+1000+100
    assert "未請求" not in c.get("/slips?from=2026-10-01&to=2026-10-31").text
    c.post("/invoices/1", data=dict(payment="4340"))
    assert c.post("/slips/1/delete", follow_redirects=True).status_code == 200  # 請求済は削除不可
    assert "バラ" in c.get("/reports/export.csv?ym=2026-10").text
    assert c.get("/reports?ym=2026-10").status_code == 200
    c.post("/invoices/1/cancel")
    assert "未請求" in c.get("/slips?from=2026-10-01&to=2026-10-31").text
