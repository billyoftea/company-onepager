import json
import re
import sys
import urllib.request

from common import fetch_json, fetch_text, resolve_company, resolve_sec_company

HEADERS = {'User-Agent': 'OpenClaw company-onepager research openclaw@example.com'}
ANNUAL_FORMS = {'10-K', '10-K/A', '20-F', '20-F/A'}
INSTANT_FORMS = ANNUAL_FORMS | {'10-Q', '10-Q/A', '6-K'}


def fetch_sec_json(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.load(response)


def fetch_sina_us_quote(ticker: str):
    symbol = f'gb_{ticker.lower()}'
    text = fetch_text(
        f'https://hq.sinajs.cn/list={symbol}',
        headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'},
        encoding='gbk',
    )
    match = re.search(r'="([^"]*)"', text)
    if not match or not match.group(1):
        return {}
    parts = match.group(1).split(',')
    if len(parts) < 8:
        return {}
    return {
        'name': parts[0],
        'price': parts[1],
        'change_pct': parts[2],
        'update_time': parts[3],
        'change': parts[4],
        'open': parts[5],
        'high': parts[6],
        'low': parts[7],
        'year_high': parts[8] if len(parts) > 8 else None,
        'year_low': parts[9] if len(parts) > 9 else None,
        'volume': parts[10] if len(parts) > 10 else None,
        'market_cap': parts[12] if len(parts) > 12 else None,
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


def select_fact(facts, taxonomy, concepts, unit='USD', annual=False):
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
    if not candidates:
        return None
    candidates.sort(key=lambda x: (str(x.get('end', '')), str(x.get('filed', '')), str(x.get('fy', ''))), reverse=True)
    return candidates[0]


def annual_value(facts, concepts):
    item = select_fact(facts, 'us-gaap', concepts, annual=True)
    return item.get('val') if item else None, item


def instant_value(facts, concepts):
    item = select_fact(facts, 'us-gaap', concepts, annual=False)
    return item.get('val') if item else None, item


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

    revenue, revenue_item = annual_value(facts, ['RevenueFromContractWithCustomerExcludingAssessedTax', 'SalesRevenueNet', 'Revenues'])
    net_income, net_income_item = annual_value(facts, 'NetIncomeLoss')
    op_cash, op_cash_item = annual_value(facts, 'NetCashProvidedByUsedInOperatingActivities')
    capex, capex_item = annual_value(
        facts,
        ['PaymentsToAcquirePropertyPlantAndEquipment', 'PropertyPlantAndEquipmentAdditions', 'CapitalExpendituresIncurredButNotYetPaid'],
    )
    assets, assets_item = instant_value(facts, 'Assets')
    liabilities, liabilities_item = instant_value(facts, 'Liabilities')
    cash, cash_item = instant_value(facts, ['CashAndCashEquivalentsAtCarryingValue', 'CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents'])

    try:
        market = fetch_sina_us_quote(sec_match['ticker'])
    except Exception as exc:
        market = {}
        warnings = [f'美股行情抓取失败: {type(exc).__name__}']
    else:
        warnings = []

    if capex_item and capex_item.get('concept') == 'CapitalExpendituresIncurredButNotYetPaid':
        warnings.append('资本开支使用近似口径，解读时请谨慎')
    if capex_item and revenue_item and capex_item.get('end') and revenue_item.get('end') and capex_item.get('end') < revenue_item.get('end'):
        capex = None
        warnings.append('资本开支口径不够稳定，已留空')

    report_period = None
    for item in (revenue_item, net_income_item, op_cash_item, assets_item):
        if item and item.get('end'):
            report_period = item['end']
            break

    out = {
        'company': sec_match['title'],
        'ticker': sec_match['ticker'],
        'cik': sec_match['cik'],
        'reportPeriod': report_period,
        'market': market,
        'profile': {
            'sicDescription': submission.get('sicDescription'),
            'website': submission.get('website'),
            'investorWebsite': submission.get('investorWebsite'),
            'state': submission.get('stateOfIncorporationDescription'),
            'fiscalYearEnd': submission.get('fiscalYearEnd'),
        },
        'financials': {
            'revenue': revenue,
            'netIncome': net_income,
            'assets': assets,
            'liabilities': liabilities,
            'cash': cash,
            'operatingCashFlow': op_cash,
            'capex': capex,
        },
        'warnings': warnings,
        'sourceNotes': ['SEC company_tickers', 'SEC companyfacts', 'SEC submissions', '新浪美股行情'],
    }
    print(json.dumps(out, ensure_ascii=False))


if __name__ == '__main__':
    main()
