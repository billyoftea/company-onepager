import json
import re
import sys
import urllib.request

import akshare as ak
import pandas as pd

from common import cn_exchange_symbol, resolve_company


def fetch_sina_quote(symbol: str):
    url = f'https://hq.sinajs.cn/list={symbol}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'})
    with urllib.request.urlopen(req, timeout=20) as response:
        text = response.read().decode('gbk', 'ignore')
    match = re.search(r'="([^"]+)"', text)
    if not match:
        return None
    parts = match.group(1).split(',')
    if len(parts) < 10:
        return None
    return {
        'name': parts[0],
        'open': parts[1],
        'prev_close': parts[2],
        'price': parts[3],
        'high': parts[4],
        'low': parts[5],
        'volume': parts[8],
        'amount': parts[9],
    }


def fetch_tencent_quote(symbol: str):
    url = f'https://qt.gtimg.cn/q={symbol}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=20) as response:
        text = response.read().decode('gbk', 'ignore')
    match = re.search(r'="([^"]+)"', text)
    if not match:
        return None
    parts = match.group(1).split('~')
    if len(parts) < 10:
        return None
    return {
        'name': parts[1],
        'code': parts[2],
        'price': parts[3],
        'prev_close': parts[4],
        'open': parts[5],
        'volume_lots': parts[6],
        'high': parts[33] if len(parts) > 33 else None,
        'low': parts[34] if len(parts) > 34 else None,
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
    except Exception as exc:
        latest_fin = {}
        warnings.append(f'财务摘要抓取失败: {type(exc).__name__}')

    try:
        zygc_df = ak.stock_zygc_em(symbol=symbol.upper())
        business_segments = latest_business_segments(zygc_df)
    except Exception as exc:
        business_segments = []
        warnings.append(f'主营构成抓取失败: {type(exc).__name__}')

    try:
        market = fetch_sina_quote(symbol) or fetch_tencent_quote(symbol) or {}
    except Exception as exc:
        market = {}
        warnings.append(f'行情抓取失败: {type(exc).__name__}')

    out = {
        'company': market.get('name') or resolved.get('company') or raw,
        'code': code,
        'symbol': symbol,
        'market': market,
        'reportPeriod': latest_fin.get('报告期'),
        'financials': latest_fin,
        'businessSegments': business_segments,
        'warnings': warnings,
        'sourceNotes': ['AKShare 同花顺财务摘要', 'AKShare 东财主营构成', '新浪/腾讯行情'],
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
