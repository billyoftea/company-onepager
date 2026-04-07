import json
import re
import sys
import urllib.request

import akshare as ak
import pandas as pd

from common import clean_text, dataframe_kv, first_non_empty, resolve_company, to_float


def fetch_tencent_quote(code: str):
    url = f'https://qt.gtimg.cn/q=hk{code}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        text = response.read().decode('gbk', 'ignore')
    match = re.search(r'="([^"]+)"', text)
    if not match:
        return {}
    parts = match.group(1).split('~')
    if len(parts) < 59:
        return {}
    market_cap = to_float(parts[44])
    float_market_cap = to_float(parts[45])
    return {
        'name': parts[1],
        'code': parts[2],
        'marketCap': market_cap * 1e8 if market_cap is not None else None,
        'floatMarketCap': float_market_cap * 1e8 if float_market_cap is not None else None,
        'pe': first_non_empty(to_float(parts[57]), to_float(parts[39])),
        'pb': to_float(parts[58]),
    }


def report_dates(df):
    if df.empty:
        return None, []
    for column in ('STD_REPORT_DATE', 'REPORT_DATE'):
        if column in df.columns:
            values = [x for x in df[column].dropna().tolist()]
            values = sorted(set(values), reverse=True)
            return column, values
    return None, []


def item_and_value_columns(df):
    item_columns = [c for c in ('STD_ITEM_NAME', 'ITEM_NAME') if c in df.columns]
    value_columns = [c for c in ('AMOUNT', 'VALUE') if c in df.columns]
    if not item_columns or not value_columns:
        return None, None
    return item_columns[0], value_columns[0]


def pick_amount(df, item_names, target_date=None):
    if df.empty:
        return None
    item_col, value_col = item_and_value_columns(df)
    if not item_col or not value_col:
        return None
    work = df
    date_col, _ = report_dates(df)
    if target_date is not None and date_col:
        work = work[work[date_col] == target_date]
    for name in item_names:
        rows = work[work[item_col] == name]
        if not rows.empty:
            value = rows.iloc[0][value_col]
            try:
                return float(value)
            except Exception:
                return None
    return None


def growth(latest, previous):
    if latest in (None, '') or previous in (None, '', 0):
        return None
    try:
        latest = float(latest)
        previous = float(previous)
    except Exception:
        return None
    if previous == 0:
        return None
    return latest / previous - 1


def main():
    raw = sys.argv[1].strip()
    resolved = json.loads(sys.argv[2]) if len(sys.argv) > 2 else resolve_company(raw)
    code = (resolved.get('code') or raw).zfill(5)

    warnings = []
    bs = pd.DataFrame()
    income_df = pd.DataFrame()
    cf = pd.DataFrame()

    try:
        bs = ak.stock_financial_hk_report_em(stock=code, symbol='资产负债表', indicator='年度')
        income_df = ak.stock_financial_hk_report_em(stock=code, symbol='利润表', indicator='年度')
        cf = ak.stock_financial_hk_report_em(stock=code, symbol='现金流量表', indicator='年度')
    except Exception:
        warnings.append('港股财务字段存在缺失')

    try:
        company_profile_df = ak.stock_hk_company_profile_em(symbol=code)
        company_profile = company_profile_df.iloc[0].to_dict() if not company_profile_df.empty else {}
    except Exception:
        company_profile = {}
        warnings.append('业务介绍来源较少')

    try:
        xq_profile = dataframe_kv(ak.stock_individual_basic_info_hk_xq(symbol=code))
    except Exception:
        xq_profile = {}

    try:
        quote = fetch_tencent_quote(code)
    except Exception:
        quote = {}
        warnings.append('估值字段存在缺失')

    income_date_col, income_dates = report_dates(income_df)
    bs_date_col, bs_dates = report_dates(bs)
    cf_date_col, cf_dates = report_dates(cf)

    latest_income_date = income_dates[0] if income_dates else None
    prev_income_date = income_dates[1] if len(income_dates) > 1 else None
    latest_bs_date = bs_dates[0] if bs_dates else None
    latest_cf_date = cf_dates[0] if cf_dates else None

    latest_revenue = pick_amount(income_df, ['营业额', '营运收入', '收入'], latest_income_date)
    prev_revenue = pick_amount(income_df, ['营业额', '营运收入', '收入'], prev_income_date)
    latest_net_income = pick_amount(income_df, ['本期溢利', '股东应占溢利', '年度溢利'], latest_income_date)
    prev_net_income = pick_amount(income_df, ['本期溢利', '股东应占溢利', '年度溢利'], prev_income_date)
    latest_gross_profit = pick_amount(income_df, ['毛利'], latest_income_date)

    out = {
        'company': first_non_empty(clean_text(company_profile.get('公司名称')), clean_text(xq_profile.get('comcnname')), resolved.get('company'), raw),
        'code': code,
        'symbol': f'hk{code}',
        'reportPeriod': str(first_non_empty(latest_income_date, latest_bs_date, latest_cf_date)) if first_non_empty(latest_income_date, latest_bs_date, latest_cf_date) is not None else None,
        'profile': {
            'industry': clean_text(company_profile.get('所属行业')),
            'mainBusiness': clean_text(first_non_empty(xq_profile.get('mbu'), company_profile.get('公司介绍'))),
            'businessIntro': clean_text(first_non_empty(company_profile.get('公司介绍'), xq_profile.get('comintr'))),
            'website': clean_text(first_non_empty(company_profile.get('公司网址'), xq_profile.get('web_site'))),
            'employees': to_float(first_non_empty(company_profile.get('员工人数'), xq_profile.get('staff_num'))),
        },
        'financials': {
            'revenue': latest_revenue,
            'revenueGrowth': growth(latest_revenue, prev_revenue),
            'grossProfit': latest_gross_profit,
            'netIncome': latest_net_income,
            'netIncomeGrowth': growth(latest_net_income, prev_net_income),
            'assets': pick_amount(bs, ['总资产'], latest_bs_date),
            'liabilities': pick_amount(bs, ['总负债'], latest_bs_date),
            'cash': pick_amount(bs, ['现金及现金等价物', '现金及等同现金项目'], latest_bs_date),
            'operatingCashFlow': pick_amount(cf, ['经营业务现金净额'], latest_cf_date),
        },
        'marketStats': {
            'currency': 'HKD',
            'marketCap': quote.get('marketCap'),
            'floatMarketCap': quote.get('floatMarketCap'),
            'pe': quote.get('pe'),
            'pb': quote.get('pb'),
        },
        'warnings': warnings,
        'sourceNotes': ['AKShare 港股财报', 'AKShare 港股公司画像', 'AKShare 雪球公司画像', '腾讯港股估值字段'],
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
