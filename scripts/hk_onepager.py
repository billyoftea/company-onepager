import json
import re
import sys
import urllib.request

import akshare as ak
import pandas as pd

from common import resolve_company


def fetch_sina_quote(code: str):
    url = f'https://hq.sinajs.cn/list=hk{code}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'})
    with urllib.request.urlopen(req, timeout=20) as response:
        text = response.read().decode('gbk', 'ignore')
    match = re.search(r'="([^"]+)"', text)
    if not match:
        return None
    parts = match.group(1).split(',')
    if len(parts) < 14:
        return None
    return {
        'eng_name': parts[0],
        'name': parts[1],
        'open': parts[2],
        'prev_close': parts[3],
        'high': parts[4],
        'low': parts[5],
        'price': parts[6],
        'change': parts[7],
        'change_pct': parts[8],
        'amount': parts[11],
        'volume': parts[12],
    }


def fetch_tencent_quote(code: str):
    url = f'https://qt.gtimg.cn/q=hk{code}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        text = response.read().decode('gbk', 'ignore')
    match = re.search(r'="([^"]+)"', text)
    if not match:
        return None
    parts = match.group(1).split('~')
    if len(parts) < 38:
        return None
    return {
        'name': parts[1],
        'code': parts[2],
        'price': parts[3],
        'prev_close': parts[4],
        'open': parts[5],
        'volume': parts[6],
        'change': parts[31],
        'change_pct': parts[32],
        'high': parts[33],
        'low': parts[34],
        'amount': parts[37],
    }


def latest_by_date(df):
    if df.empty:
        return df
    for column in ('STD_REPORT_DATE', 'REPORT_DATE'):
        if column in df.columns:
            return df[df[column] == df[column].max()].copy()
    return df


def pick_amount(df, item_names):
    if df.empty:
        return None
    item_columns = [c for c in ('STD_ITEM_NAME', 'ITEM_NAME') if c in df.columns]
    value_columns = [c for c in ('AMOUNT', 'VALUE') if c in df.columns]
    if not item_columns or not value_columns:
        return None
    item_col = item_columns[0]
    value_col = value_columns[0]
    for name in item_names:
        rows = df[df[item_col] == name]
        if not rows.empty:
            value = rows.iloc[0][value_col]
            try:
                return float(value)
            except Exception:
                return None
    return None


def main():
    raw = sys.argv[1].strip()
    resolved = json.loads(sys.argv[2]) if len(sys.argv) > 2 else resolve_company(raw)
    code = (resolved.get('code') or raw).zfill(5)

    warnings = []
    bs = pd.DataFrame()
    income_df = pd.DataFrame()
    cf = pd.DataFrame()

    try:
        bs = latest_by_date(ak.stock_financial_hk_report_em(stock=code, symbol='资产负债表', indicator='年度'))
        income_df = latest_by_date(ak.stock_financial_hk_report_em(stock=code, symbol='利润表', indicator='年度'))
        cf = latest_by_date(ak.stock_financial_hk_report_em(stock=code, symbol='现金流量表', indicator='年度'))
    except Exception as exc:
        warnings.append(f'港股财报抓取失败: {type(exc).__name__}')

    try:
        market = fetch_sina_quote(code) or fetch_tencent_quote(code) or {}
    except Exception as exc:
        market = {}
        warnings.append(f'行情抓取失败: {type(exc).__name__}')

    report_period = None
    for df in (income_df, bs, cf):
        for column in ('STD_REPORT_DATE', 'REPORT_DATE'):
            if column in df.columns and not df.empty:
                report_period = str(df.iloc[0][column])
                break
        if report_period:
            break

    out = {
        'company': market.get('name') or resolved.get('company') or raw,
        'code': code,
        'symbol': f'hk{code}',
        'market': market,
        'reportPeriod': report_period,
        'financials': {
            'revenue': pick_amount(income_df, ['营业额', '营运收入', '收入']),
            'grossProfit': pick_amount(income_df, ['毛利']),
            'netIncome': pick_amount(income_df, ['本期溢利', '股东应占溢利', '年度溢利']),
            'assets': pick_amount(bs, ['总资产']),
            'liabilities': pick_amount(bs, ['总负债']),
            'cash': pick_amount(bs, ['现金及现金等价物', '现金及等同现金项目']),
            'operatingCashFlow': pick_amount(cf, ['经营业务现金净额']),
        },
        'warnings': warnings,
        'sourceNotes': ['AKShare 港股财报', '新浪/腾讯港股行情'],
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
