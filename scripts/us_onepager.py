import json
import re
import sys
import urllib.request

import akshare as ak

from common import clean_text, dataframe_kv, first_non_empty, resolve_company, resolve_sec_company, to_float

HEADERS = {'User-Agent': 'OpenClaw company-onepager research openclaw@example.com'}
ANNUAL_FORMS = {'10-K', '10-K/A', '20-F', '20-F/A'}
INSTANT_FORMS = ANNUAL_FORMS | {'10-Q', '10-Q/A', '6-K'}


def fetch_sec_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def fetch_sina_us_quote(ticker: str):
    url = f'https://hq.sinajs.cn/list=gb_{ticker.lower()}'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'})
    with urllib.request.urlopen(req, timeout=20) as response:
        text = response.read().decode('gbk', 'ignore')
    match = re.search(r'="([^"]*)"', text)
    if not match or not match.group(1):
        return {}
    parts = match.group(1).split(',')
    if len(parts) < 15:
        return {}
    return {
        'name': parts[0],
        'marketCap': to_float(parts[12]),
        'pe': to_float(parts[14]),
    }


def duration_days(item):
    start = item.get('start')
    end = item.get('end')
    if not start or not end:
        return None
    try:
        from datetime import date

        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
        return (end_date - start_date).days
    except Exception:
        return None


def select_facts(facts, taxonomy, concepts, unit='USD', annual=False):
    if isinstance(concepts, str):
        concepts = [concepts]
    candidates = []
    for concept in concepts:
        series = facts.get('facts', {}).get(taxonomy, {}).get(concept, {}).get('units', {}).get(unit, [])
        for item in series:
            if not item or item.get('val') is None:
                continue
            form = item.get('form')
            if annual:
                if form not in ANNUAL_FORMS:
                    continue
                days = duration_days(item)
                if item.get('fp') != 'FY' and (days is None or not 300 <= days <= 380):
                    continue
            else:
                if form not in INSTANT_FORMS:
                    continue
            candidates.append({**item, 'concept': concept})
    candidates.sort(key=lambda x: (str(x.get('end', '')), str(x.get('filed', '')), str(x.get('fy', ''))), reverse=True)
    return candidates


def top_unique_facts(facts, taxonomy, concepts, unit='USD', annual=False, limit=2):
    results = []
    seen = set()
    for item in select_facts(facts, taxonomy, concepts, unit=unit, annual=annual):
        key = (item.get('end'), item.get('concept'))
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
        if len(results) >= limit:
            break
    return results


def latest_and_previous_value(facts, concepts):
    items = top_unique_facts(facts, 'us-gaap', concepts, annual=True, limit=2)
    latest = items[0].get('val') if len(items) >= 1 else None
    previous = items[1].get('val') if len(items) >= 2 else None
    latest_item = items[0] if items else None
    return latest, previous, latest_item


def latest_instant_value(facts, concepts):
    items = top_unique_facts(facts, 'us-gaap', concepts, annual=False, limit=1)
    latest = items[0].get('val') if items else None
    latest_item = items[0] if items else None
    return latest, latest_item


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
    ticker = (resolved.get('ticker') or raw).upper()

    sec_match = resolve_sec_company(ticker) or resolve_sec_company(resolved.get('company') or raw)
    if not sec_match:
        raise RuntimeError(f'Unable to resolve US company: {raw}')

    cik = str(sec_match['cik']).zfill(10)
    facts = fetch_sec_json(f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json')
    submission = fetch_sec_json(f'https://data.sec.gov/submissions/CIK{cik}.json')

    warnings = []

    revenue, prev_revenue, revenue_item = latest_and_previous_value(facts, ['RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'Revenues'])
    net_income, prev_net_income, net_income_item = latest_and_previous_value(facts, 'NetIncomeLoss')
    gross_profit, _, _ = latest_and_previous_value(facts, 'GrossProfit')
    op_cash, _, op_cash_item = latest_and_previous_value(facts, 'NetCashProvidedByUsedInOperatingActivities')
    capex, _, capex_item = latest_and_previous_value(
        facts,
        ['PaymentsToAcquirePropertyPlantAndEquipment', 'PropertyPlantAndEquipmentAdditions', 'CapitalExpendituresIncurredButNotYetPaid'],
    )
    assets, assets_item = latest_instant_value(facts, 'Assets')
    liabilities, liabilities_item = latest_instant_value(facts, 'Liabilities')
    cash, cash_item = latest_instant_value(facts, ['CashAndCashEquivalentsAtCarryingValue', 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'])

    if capex_item and capex_item.get('concept') == 'CapitalExpendituresIncurredButNotYetPaid':
        warnings.append('资本开支使用近似口径，解读时请谨慎')
    if capex_item and revenue_item and capex_item.get('end') and revenue_item.get('end') and capex_item.get('end') < revenue_item.get('end'):
        capex = None
        warnings.append('资本开支口径不够稳定，已留空')

    try:
        xq_profile = dataframe_kv(ak.stock_individual_basic_info_us_xq(symbol=sec_match['ticker']))
    except Exception:
        xq_profile = {}
        warnings.append('业务介绍来源较少')

    try:
        quote = fetch_sina_us_quote(sec_match['ticker'])
    except Exception:
        quote = {}
        warnings.append('估值字段存在缺失')

    report_period = None
    for item in (revenue_item, net_income_item, op_cash_item, assets_item, liabilities_item, cash_item):
        if item and item.get('end'):
            report_period = item['end']
            break

    out = {
        'company': first_non_empty(clean_text(xq_profile.get('org_name_cn')), sec_match['title']),
        'ticker': sec_match['ticker'],
        'cik': sec_match['cik'],
        'reportPeriod': report_period,
        'profile': {
            'industry': clean_text(submission.get('sicDescription')),
            'mainBusiness': clean_text(xq_profile.get('main_operation_business')),
            'businessIntro': clean_text(first_non_empty(xq_profile.get('org_cn_introduction'), xq_profile.get('operating_scope'))),
            'website': clean_text(first_non_empty(xq_profile.get('org_website'), submission.get('website'))),
            'employees': to_float(xq_profile.get('staff_num')),
        },
        'financials': {
            'revenue': revenue,
            'revenueGrowth': growth(revenue, prev_revenue),
            'grossProfit': gross_profit,
            'netIncome': net_income,
            'netIncomeGrowth': growth(net_income, prev_net_income),
            'assets': assets,
            'liabilities': liabilities,
            'cash': cash,
            'operatingCashFlow': op_cash,
            'capex': capex,
        },
        'marketStats': {
            'currency': 'USD',
            'marketCap': quote.get('marketCap'),
            'pe': quote.get('pe'),
        },
        'warnings': warnings,
        'sourceNotes': ['SEC company_tickers', 'SEC companyfacts', 'SEC submissions', 'AKShare 雪球公司画像', '新浪美股估值字段'],
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
