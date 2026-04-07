import json
import re
import sys
import urllib.request

import akshare as ak
import pandas as pd

from common import clean_text, cn_exchange_symbol, dataframe_kv, first_non_empty, resolve_company, to_float


def fetch_tencent_quote(symbol: str):
    url = f'https://qt.gtimg.cn/q={symbol}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        text = response.read().decode('gbk', 'ignore')
    match = re.search(r'="([^"]+)"', text)
    if not match:
        return {}
    parts = match.group(1).split('~')
    if len(parts) < 47:
        return {}
    return {
        'name': parts[1],
        'code': parts[2],
        'pe': to_float(parts[39]),
        'marketCap': to_float(parts[44]) * 1e8 if to_float(parts[44]) is not None else None,
        'floatMarketCap': to_float(parts[45]) * 1e8 if to_float(parts[45]) is not None else None,
        'pb': to_float(parts[46]),
    }


def latest_business_segments(df):
    if df.empty:
        return []
    report_col = '报告日期' if '报告日期' in df.columns else None
    if report_col:
        latest_date = df[report_col].max()
        df = df[df[report_col] == latest_date].copy()
    df = df[df['分类类型'] == '按产品分类'].copy()
    if df.empty:
        return []
    df = df.sort_values(by='主营收入', ascending=False, na_position='last')
    rows = []
    for _, row in df.head(3).iterrows():
        rows.append({
            'segment': str(row.get('主营构成')),
            'revenue': None if pd.isna(row.get('主营收入')) else float(row.get('主营收入')),
            'ratio': None if pd.isna(row.get('收入比例')) else float(row.get('收入比例')),
            'margin': None if pd.isna(row.get('毛利率')) else float(row.get('毛利率')),
        })
    return rows


def main():
    raw = sys.argv[1].strip()
    resolved = json.loads(sys.argv[2]) if len(sys.argv) > 2 else resolve_company(raw)
    code = resolved.get('code') or raw
    symbol = resolved.get('symbol') or cn_exchange_symbol(code)

    warnings = []

    try:
        fin_df = ak.stock_financial_abstract_ths(symbol=code)
        latest_fin = fin_df.iloc[-1].to_dict() if not fin_df.empty else {}
    except Exception:
        latest_fin = {}
        warnings.append('部分财务摘要字段缺失')

    try:
        zygc_df = ak.stock_zygc_em(symbol=symbol.upper())
        business_segments = latest_business_segments(zygc_df)
    except Exception:
        business_segments = []
        warnings.append('主营构成未完整获取')

    try:
        basic_info = dataframe_kv(ak.stock_individual_info_em(symbol=code))
    except Exception:
        basic_info = {}

    try:
        xq_profile = dataframe_kv(ak.stock_individual_basic_info_xq(symbol=symbol.upper()))
    except Exception:
        xq_profile = {}
        warnings.append('业务介绍来源较少')

    try:
        quote = fetch_tencent_quote(symbol)
    except Exception:
        quote = {}
        warnings.append('估值字段存在缺失')

    out = {
        'company': first_non_empty(clean_text(basic_info.get('股票简称')), clean_text(xq_profile.get('org_short_name_cn')), resolved.get('company'), raw),
        'code': code,
        'symbol': symbol,
        'reportPeriod': latest_fin.get('报告期'),
        'profile': {
            'industry': clean_text(first_non_empty(basic_info.get('行业'), xq_profile.get('industry'))),
            'mainBusiness': clean_text(xq_profile.get('main_operation_business')),
            'businessIntro': clean_text(first_non_empty(xq_profile.get('org_cn_introduction'), xq_profile.get('operating_scope'))),
            'website': clean_text(xq_profile.get('org_website')),
            'employees': to_float(xq_profile.get('staff_num')),
        },
        'financials': latest_fin,
        'businessSegments': business_segments,
        'marketStats': {
            'currency': 'CNY',
            'marketCap': first_non_empty(to_float(basic_info.get('总市值')), quote.get('marketCap')),
            'floatMarketCap': first_non_empty(to_float(basic_info.get('流通市值')), quote.get('floatMarketCap')),
            'pe': quote.get('pe'),
            'pb': quote.get('pb'),
        },
        'warnings': warnings,
        'sourceNotes': ['AKShare 同花顺财务摘要', 'AKShare 东财主营构成', 'AKShare A股基础资料', 'AKShare 雪球公司画像', '腾讯行情估值字段'],
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
