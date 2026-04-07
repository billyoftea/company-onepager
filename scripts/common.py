import functools
import json
import re
import urllib.parse
import urllib.request

HEADERS = {
    'User-Agent': 'OpenClaw company-onepager research openclaw@example.com',
    'Accept': 'application/json,text/plain,*/*',
}

LISTED_MARKET_TYPES = {
    '11': 'CN',
    '31': 'HK',
    '41': 'US',
}

COMMON_ALIASES = {
    '茅台': {'marketType': 'CN', 'code': '600519', 'symbol': 'sh600519', 'company': '贵州茅台'},
    '贵州茅台': {'marketType': 'CN', 'code': '600519', 'symbol': 'sh600519', 'company': '贵州茅台'},
    '腾讯': {'marketType': 'HK', 'code': '00700', 'symbol': 'hk00700', 'company': '腾讯控股'},
    '腾讯控股': {'marketType': 'HK', 'code': '00700', 'symbol': 'hk00700', 'company': '腾讯控股'},
    'tencent': {'marketType': 'HK', 'code': '00700', 'symbol': 'hk00700', 'company': '腾讯控股'},
    'apple': {'marketType': 'US', 'ticker': 'AAPL', 'symbol': 'gb_aapl', 'company': 'Apple Inc.'},
    '苹果': {'marketType': 'US', 'ticker': 'AAPL', 'symbol': 'gb_aapl', 'company': 'Apple Inc.'},
    '苹果公司': {'marketType': 'US', 'ticker': 'AAPL', 'symbol': 'gb_aapl', 'company': 'Apple Inc.'},
    'nvidia': {'marketType': 'US', 'ticker': 'NVDA', 'symbol': 'gb_nvda', 'company': 'NVIDIA CORP'},
    '英伟达': {'marketType': 'US', 'ticker': 'NVDA', 'symbol': 'gb_nvda', 'company': 'NVIDIA CORP'},
    'alphabet': {'marketType': 'US', 'ticker': 'GOOGL', 'symbol': 'gb_googl', 'company': 'Alphabet Inc.'},
    'google': {'marketType': 'US', 'ticker': 'GOOGL', 'symbol': 'gb_googl', 'company': 'Alphabet Inc.'},
    'tesla': {'marketType': 'US', 'ticker': 'TSLA', 'symbol': 'gb_tsla', 'company': 'Tesla, Inc.'},
    '微软': {'marketType': 'US', 'ticker': 'MSFT', 'symbol': 'gb_msft', 'company': 'Microsoft Corporation'},
    'microsoft': {'marketType': 'US', 'ticker': 'MSFT', 'symbol': 'gb_msft', 'company': 'Microsoft Corporation'},
}

EQUITY_PENALTY_TERMS = (
    'adr', 'etf', 'etn', 'fund', '基金', '指数', '债券', '债', '期权', '牛', '熊', '认购', '认沽', '窝轮', '涡轮',
)


def fetch_text(url, headers=None, timeout=20, encoding='utf-8'):
    req = urllib.request.Request(url, headers={**HEADERS, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read()
    return data.decode(encoding, 'ignore')


def fetch_json(url, headers=None, timeout=20):
    return json.loads(fetch_text(url, headers=headers, timeout=timeout))


def contains_chinese(text):
    return bool(re.search(r'[\u4e00-\u9fff]', text or ''))


def normalize_spaces(text):
    return re.sub(r'\s+', ' ', (text or '').strip())


def compact_text(text):
    text = (text or '').lower().strip()
    text = re.sub(r'[\s\-_,.:;!？?，。()（）\[\]{}]+', '', text)
    return text


def normalize_query(raw):
    text = normalize_spaces(raw)
    substitutions = [
        (r'(?i)\bone\s*-?\s*pager\b', ' '),
        (r'(?i)\bonepager\b', ' '),
        (r'一页纸|一页报|一页简介|一页概览|公司简报|公司概览|股票快照|公司速览', ' '),
        (r'(?i)\bcompany\s+brief\b', ' '),
        (r'(?i)\bstock\s+snapshot\b', ' '),
        (r'(?i)\bbusiness\s+summary\b', ' '),
        (r'(?i)\bfinancial\s+summary\b', ' '),
        (r'(?i)\bone\s+page(r)?\b', ' '),
    ]
    for pattern, replacement in substitutions:
        text = re.sub(pattern, replacement, text)

    while True:
        new_text = re.sub(
            r'^(请|帮我|帮忙|麻烦|想让你|你帮我|给我|来个|做个|做一下|做一份|写个|写一份|生成|输出|分析|分析下|分析一下|研究|看下|看一下)\s*',
            '',
            text,
            flags=re.IGNORECASE,
        )
        if new_text == text:
            break
        text = new_text.strip()

    text = re.sub(r'\s*(吧|呢|谢谢)$', '', text)
    text = normalize_spaces(text)
    return text.strip(' /')


@functools.lru_cache(maxsize=1)
def sec_company_mapping():
    data = fetch_json('https://www.sec.gov/files/company_tickers.json', headers={'User-Agent': HEADERS['User-Agent']})
    rows = []
    for row in data.values():
        rows.append({
            'ticker': row['ticker'],
            'cik': row['cik_str'],
            'title': row['title'],
        })
    return rows


def resolve_sec_company(query):
    q = normalize_query(query)
    q_compact = compact_text(q)
    exact_ticker = None
    exact_title = None
    fuzzy = []
    for row in sec_company_mapping():
        ticker = row['ticker']
        title = row['title']
        title_compact = compact_text(title)
        ticker_compact = compact_text(ticker)
        if q_compact == ticker_compact:
            exact_ticker = row
            break
        if q_compact == title_compact:
            exact_title = row
        elif q_compact and (q_compact in title_compact or title_compact in q_compact):
            fuzzy.append((abs(len(title_compact) - len(q_compact)), row))
    if exact_ticker:
        return exact_ticker
    if exact_title:
        return exact_title
    if fuzzy:
        fuzzy.sort(key=lambda item: item[0])
        return fuzzy[0][1]
    return None


def parse_sina_suggest(query):
    url = f'https://suggest3.sinajs.cn/suggest/type=&key={urllib.parse.quote(query)}'
    text = fetch_text(
        url,
        headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'},
        encoding='gbk',
    )
    match = re.search(r'="([^"]*)"', text)
    if not match or not match.group(1):
        return []
    entries = []
    for item in match.group(1).split(';'):
        parts = item.split(',')
        if len(parts) < 5:
            continue
        entries.append({
            'rawName': parts[0].strip(),
            'kind': parts[1].strip(),
            'code': parts[2].strip(),
            'symbol': parts[3].strip(),
            'name': (parts[4] or parts[0]).strip(),
            'extra': [p.strip() for p in parts[5:]],
        })
    return entries


def _candidate_score(query, candidate, preferred_markets=None):
    q = compact_text(query)
    name = compact_text(candidate.get('name'))
    raw_name = compact_text(candidate.get('rawName'))
    code = compact_text(candidate.get('code'))
    symbol = compact_text(candidate.get('symbol'))
    score = 0

    if q and q in {code, symbol}:
        score += 140
    if q and q in {name, raw_name}:
        score += 120
    if q and name and q in name:
        score += 70
    if q and raw_name and q in raw_name:
        score += 55
    if q and name and name in q:
        score += 35

    market = LISTED_MARKET_TYPES.get(candidate.get('kind'))
    if market:
        score += {'CN': 12, 'HK': 10, 'US': 8}[market]
    if preferred_markets and market in preferred_markets:
        score += 25

    lowered_name = (candidate.get('name') or '').lower()
    lowered_raw = (candidate.get('rawName') or '').lower()
    for term in EQUITY_PENALTY_TERMS:
        if term in lowered_name or term in lowered_raw:
            score -= 60

    if candidate.get('kind') == '41' and 'adr' in '|'.join(candidate.get('extra', [])).lower():
        score -= 70

    return score


def _build_listing_candidate(candidate):
    market = LISTED_MARKET_TYPES[candidate['kind']]
    if market == 'CN':
        return {
            'marketType': 'CN',
            'code': candidate['code'],
            'symbol': candidate['symbol'].lower() or cn_exchange_symbol(candidate['code']),
            'company': candidate['name'] or candidate['rawName'],
            'resolutionSource': 'sina-suggest',
        }
    if market == 'HK':
        code = candidate['code'].zfill(5)
        return {
            'marketType': 'HK',
            'code': code,
            'symbol': f'hk{code}',
            'company': candidate['name'] or candidate['rawName'],
            'resolutionSource': 'sina-suggest',
        }
    ticker = candidate['code'].upper()
    return {
        'marketType': 'US',
        'ticker': ticker,
        'symbol': f'gb_{ticker.lower()}',
        'company': candidate['name'] or candidate['rawName'],
        'resolutionSource': 'sina-suggest',
    }


def cn_exchange_symbol(code):
    code = str(code).strip()
    if code.startswith(('6', '9')):
        return f'sh{code}'
    if code.startswith(('4', '8')):
        return f'bj{code}'
    return f'sz{code}'


def resolve_company(query):
    normalized = normalize_query(query)
    if not normalized:
        raise RuntimeError('Missing company name or ticker')

    alias = COMMON_ALIASES.get(normalized) or COMMON_ALIASES.get(normalized.lower())
    if alias:
        return {**alias, 'query': normalized, 'resolutionSource': 'alias'}

    lowered = normalized.lower()
    if re.fullmatch(r'hk\d{5}', lowered):
        code = lowered[2:]
        return {'marketType': 'HK', 'code': code, 'symbol': f'hk{code}', 'company': code, 'query': normalized, 'resolutionSource': 'pattern'}
    if re.fullmatch(r'\d{6}', normalized):
        return {'marketType': 'CN', 'code': normalized, 'symbol': cn_exchange_symbol(normalized), 'company': normalized, 'query': normalized, 'resolutionSource': 'pattern'}
    if re.fullmatch(r'\d{5}', normalized):
        code = normalized.zfill(5)
        return {'marketType': 'HK', 'code': code, 'symbol': f'hk{code}', 'company': code, 'query': normalized, 'resolutionSource': 'pattern'}

    sec_match = None
    explicit_us_like = bool(re.fullmatch(r'[A-Za-z.]{1,5}', normalized)) or (not contains_chinese(normalized) and ' ' in normalized)
    if explicit_us_like:
        sec_match = resolve_sec_company(normalized)
        if sec_match and (compact_text(normalized) in {compact_text(sec_match['ticker']), compact_text(sec_match['title'])} or re.fullmatch(r'[A-Za-z.]{1,5}', normalized)):
            return {
                'marketType': 'US',
                'ticker': sec_match['ticker'],
                'symbol': f"gb_{sec_match['ticker'].lower()}",
                'company': sec_match['title'],
                'cik': sec_match['cik'],
                'query': normalized,
                'resolutionSource': 'sec',
            }

    candidates = [c for c in parse_sina_suggest(normalized) if c.get('kind') in LISTED_MARKET_TYPES]
    if contains_chinese(normalized) and not re.search(r'美股|adr', query, re.IGNORECASE):
        local_candidates = [c for c in candidates if c['kind'] in {'11', '31'}]
        if local_candidates:
            candidates = local_candidates

    if candidates:
        preferred = None
        if contains_chinese(normalized):
            preferred = {'CN', 'HK'}
        best = max(candidates, key=lambda c: _candidate_score(normalized, c, preferred_markets=preferred))
        resolved = _build_listing_candidate(best)
        resolved['query'] = normalized
        return resolved

    if sec_match is None:
        sec_match = resolve_sec_company(normalized)
    if sec_match:
        return {
            'marketType': 'US',
            'ticker': sec_match['ticker'],
            'symbol': f"gb_{sec_match['ticker'].lower()}",
            'company': sec_match['title'],
            'cik': sec_match['cik'],
            'query': normalized,
            'resolutionSource': 'sec',
        }

    raise RuntimeError(f'Unable to resolve company: {query}')
