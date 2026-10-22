"""請求・税計算ロジック(インボイス方式: 税率ごとに合計して端数切り捨て)。"""
import calendar
from datetime import date, timedelta


def line_amount(qty, unit_price):
    return int(qty) * int(unit_price)


def tax_summary(lines):
    """lines: (qty, unit_price, tax_rate) の列 -> 税率別小計・消費税。"""
    sub = {8: 0, 10: 0}
    for qty, price, rate in lines:
        sub[10 if int(rate) == 10 else 8] += line_amount(qty, price)
    tax = {r: sub[r] * r // 100 for r in sub}  # 切り捨て
    return sub, tax


def invoice_total(sub, tax, prev_balance, payment):
    return sub[8] + sub[10] + tax[8] + tax[10] + prev_balance - payment


def period_for(year, month, closing_day):
    """締め日から請求対象期間を求める。closing_day=0 は月末締め。"""
    last = calendar.monthrange(year, month)[1]
    if closing_day == 0 or closing_day >= last:
        return date(year, month, 1), date(year, month, last)
    end = date(year, month, closing_day)
    prev_end = (date(year, month, 1) - timedelta(days=1))
    prev_end = date(prev_end.year, prev_end.month, min(closing_day, prev_end.day))
    return prev_end + timedelta(days=1), end
