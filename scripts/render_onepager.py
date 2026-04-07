import json
import re
import sys


CURRENCY_PREFIX = {
    'USD': '$',
    'HKD': 'HK$',
    'CNY': '¥',
}

BUSINESS_KEYWORDS = [
    '业务', '产品', '服务', '平台', '销售', '生产', '提供', '处理器', '芯片', '游戏', '广告', '社交',
    '云', '金融科技', '互联网', '软件', '硬件', '白酒', '数据中心', '汽车', '通信', '计算', '娱乐',
]


def clean_text(text):
    text = (text or '').replace('\u3000', ' ')
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def fmt_num(value, currency=None):
    if value in (None, '', False):
        return 'NA'
    if isinstance(value, str):
        return value
    number = float(value)
    sign = '-' if number < 0 else ''
    number = abs(number)
    prefix = CURRENCY_PREFIX.get(currency, '')
    if number >= 1e12:
        return f'{sign}{prefix}{number/1e12:.2f}T'
    if number >= 1e9:
        return f'{sign}{prefix}{number/1e9:.2f}B'
    if number >= 1e8 and currency == 'CNY':
        return f'{sign}{prefix}{number/1e8:.2f}亿'
    if number >= 1e6:
        return f'{sign}{prefix}{number/1e6:.2f}M'
    return f'{sign}{prefix}{number:.2f}'


def safe_float(value):
    if value in (None, '', False):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(',', '').replace('%', '').strip()
    text = text.replace('HK$', '').replace('$', '').replace('¥', '')
    for unit, multiple in [('万亿', 1e12), ('亿', 1e8), ('万', 1e4)]:
        if text.endswith(unit):
            try:
                return float(text[:-len(unit)]) * multiple
            except Exception:
                return None
    try:
        return float(text)
    except Exception:
        return None


def pct_text(value, digits=1):
    if value in (None, '', False):
        return 'NA'
    if isinstance(value, str) and value.strip().endswith('%'):
        return value.strip()
    number = safe_float(value)
    if number is None:
        return 'NA'
    if abs(number) <= 1:
        number *= 100
    return f'{number:.{digits}f}%'


def ratio(a, b):
    a = safe_float(a)
    b = safe_float(b)
    if a is None or b in (None, 0):
        return None
    return a / b


def as_ratio(value):
    value = safe_float(value)
    if value is None:
        return None
    if abs(value) > 1:
        return value / 100
    return value


def bullet_lines(items, fallback, limit=4):
    values = [item for item in items if item]
    if not values:
        values = [fallback]
    return '\n'.join(f'- {item}' for item in values[:limit])


def render_company_block(data, market_label, code_label):
    report_period = data.get('reportPeriod') or 'NA'
    return f"""## 公司
- 名称: {data.get('company')}
- {code_label}: {data.get('code') or data.get('ticker')}
- 市场: {market_label}
- 财报口径: {report_period}"""


def split_sentences(text):
    text = clean_text(text)
    if not text:
        return []
    sentences = re.split(r'[。！？；;]', text)
    out = []
    for sentence in sentences:
        sentence = clean_text(sentence).strip(' ,，。；;')
        if len(sentence) >= 6:
            out.append(sentence)
    return out


def pick_intro_sentences(text, limit=2):
    sentences = split_sentences(text)
    if not sentences:
        return []
    scored = []
    for idx, sentence in enumerate(sentences):
        score = 0
        for keyword in BUSINESS_KEYWORDS:
            if keyword in sentence:
                score += 1
        if idx == 0:
            score += 0.2
        scored.append((score, idx, sentence))
    ranked = sorted(scored, key=lambda item: (-item[0], item[1]))
    selected_idx = sorted([idx for _, idx, _ in ranked[:limit]])
    return [sentences[idx] for idx in selected_idx][:limit]


def unique_points(points):
    seen = []
    out = []
    for point in points:
        key = re.sub(r'\W+', '', clean_text(point))
        key = re.sub(r'^(公司主营|公司的主营业务是|集团的主要业务包括|主营业务是)', '', key)
        if not key:
            continue
        if any(key in old or old in key for old in seen):
            continue
        seen.append(key)
        out.append(point)
    return out


def normalized_main_business(text):
    text = clean_text(text).strip('。')
    if not text:
        return None
    if text.startswith(('公司主营', '集团的主要业务', '公司的主营业务', '主要业务包括')):
        return text + '。'
    return f'公司主营{text}。'


def business_points(profile, segments=None, market='CN'):
    profile = profile or {}
    points = []

    main_business = normalized_main_business(profile.get('mainBusiness'))
    if main_business:
        points.append(main_business)

    intro_sentences = pick_intro_sentences(profile.get('businessIntro'), limit=2)
    for sentence in intro_sentences:
        if not sentence.endswith('。'):
            sentence = sentence + '。'
        points.append(sentence)

    industry = clean_text(profile.get('industry'))
    if industry:
        points.append(f'公司所属行业为 {industry}。')

    segments = segments or []
    if segments:
        segment_bits = []
        for seg in segments[:3]:
            name = clean_text(seg.get('segment'))
            share = seg.get('ratio')
            if not name:
                continue
            if share is not None:
                segment_bits.append(f'{name}({share * 100:.1f}%)')
            else:
                segment_bits.append(name)
        if segment_bits:
            points.append(f"收入结构以 {'、'.join(segment_bits)} 为主。")
        top_share = segments[0].get('ratio') if segments and segments[0].get('ratio') is not None else None
        if top_share is not None and top_share >= 0.7:
            points.append(f'核心业务收入占比约 {top_share * 100:.1f}%，主业集中度较高。')

    return unique_points(points)


def normalize_cn(data):
    f = data.get('financials', {})
    ms = data.get('marketStats', {})
    revenue = safe_float(f.get('营业总收入'))
    net_income = safe_float(f.get('净利润'))
    gross_margin = as_ratio(f.get('销售毛利率'))
    net_margin = as_ratio(f.get('销售净利率'))
    leverage = as_ratio(f.get('资产负债率'))
    revenue_growth = as_ratio(f.get('营业总收入同比增长率'))
    net_income_growth = as_ratio(f.get('净利润同比增长率'))
    if net_income_growth is None:
        net_income_growth = as_ratio(f.get('扣非净利润同比增长率'))
    market_cap = safe_float(ms.get('marketCap'))
    ps = market_cap / revenue if market_cap and revenue else None
    return {
        'marketLabel': 'A股',
        'codeLabel': '代码',
        'currency': 'CNY',
        'profile': data.get('profile', {}),
        'segments': data.get('businessSegments') or [],
        'revenue': f.get('营业总收入', 'NA'),
        'revenueGrowth': revenue_growth,
        'grossMargin': gross_margin,
        'netIncome': f.get('净利润', 'NA'),
        'netIncomeGrowth': net_income_growth,
        'netMargin': net_margin,
        'operatingCashFlow': None,
        'operatingCashFlowMargin': None,
        'operatingCashFlowPerShare': f.get('每股经营现金流'),
        'leverage': leverage,
        'cashToLiabilities': None,
        'marketCap': market_cap,
        'pe': safe_float(ms.get('pe')),
        'pb': safe_float(ms.get('pb')),
        'ps': ps,
        'warnings': data.get('warnings') or [],
    }


def normalize_hk(data):
    f = data.get('financials', {})
    ms = data.get('marketStats', {})
    revenue = safe_float(f.get('revenue'))
    gross_profit = safe_float(f.get('grossProfit'))
    net_income = safe_float(f.get('netIncome'))
    liabilities = safe_float(f.get('liabilities'))
    assets = safe_float(f.get('assets'))
    cash = safe_float(f.get('cash'))
    operating_cf = safe_float(f.get('operatingCashFlow'))
    market_cap = safe_float(ms.get('marketCap'))
    return {
        'marketLabel': '港股',
        'codeLabel': '代码',
        'currency': 'HKD',
        'profile': data.get('profile', {}),
        'segments': [],
        'revenue': fmt_num(revenue, 'HKD'),
        'revenueGrowth': f.get('revenueGrowth'),
        'grossMargin': ratio(gross_profit, revenue),
        'netIncome': fmt_num(net_income, 'HKD'),
        'netIncomeGrowth': f.get('netIncomeGrowth'),
        'netMargin': ratio(net_income, revenue),
        'operatingCashFlow': fmt_num(operating_cf, 'HKD'),
        'operatingCashFlowMargin': ratio(operating_cf, revenue),
        'operatingCashFlowPerShare': None,
        'leverage': ratio(liabilities, assets),
        'cashToLiabilities': ratio(cash, liabilities),
        'marketCap': market_cap,
        'pe': safe_float(ms.get('pe')),
        'pb': safe_float(ms.get('pb')),
        'ps': market_cap / revenue if market_cap and revenue else None,
        'warnings': data.get('warnings') or [],
    }


def normalize_us(data):
    f = data.get('financials', {})
    ms = data.get('marketStats', {})
    revenue = safe_float(f.get('revenue'))
    gross_profit = safe_float(f.get('grossProfit'))
    net_income = safe_float(f.get('netIncome'))
    liabilities = safe_float(f.get('liabilities'))
    assets = safe_float(f.get('assets'))
    cash = safe_float(f.get('cash'))
    operating_cf = safe_float(f.get('operatingCashFlow'))
    market_cap = safe_float(ms.get('marketCap'))
    equity = assets - liabilities if assets is not None and liabilities is not None else None
    pb = safe_float(ms.get('pb'))
    if pb is None and equity not in (None, 0):
        pb = market_cap / equity if market_cap else None
    return {
        'marketLabel': '美股',
        'codeLabel': '代码',
        'currency': 'USD',
        'profile': data.get('profile', {}),
        'segments': [],
        'revenue': fmt_num(revenue, 'USD'),
        'revenueGrowth': f.get('revenueGrowth'),
        'grossMargin': ratio(gross_profit, revenue),
        'netIncome': fmt_num(net_income, 'USD'),
        'netIncomeGrowth': f.get('netIncomeGrowth'),
        'netMargin': ratio(net_income, revenue),
        'operatingCashFlow': fmt_num(operating_cf, 'USD'),
        'operatingCashFlowMargin': ratio(operating_cf, revenue),
        'operatingCashFlowPerShare': None,
        'leverage': ratio(liabilities, assets),
        'cashToLiabilities': ratio(cash, liabilities),
        'marketCap': market_cap,
        'pe': safe_float(ms.get('pe')),
        'pb': pb,
        'ps': market_cap / revenue if market_cap and revenue else None,
        'warnings': data.get('warnings') or [],
    }


def normalize_payload(data):
    market = data.get('marketType')
    if market == 'CN':
        return normalize_cn(data)
    if market == 'HK':
        return normalize_hk(data)
    return normalize_us(data)


def profile_text_blob(metrics):
    profile = metrics.get('profile') or {}
    return ' '.join([
        clean_text(profile.get('mainBusiness')),
        clean_text(profile.get('businessIntro')),
        clean_text(profile.get('industry')),
    ])


def generate_highlights(metrics):
    highlights = []
    profile_blob = profile_text_blob(metrics)
    if metrics.get('grossMargin') is not None and metrics['grossMargin'] >= 0.5:
        highlights.append(f"毛利率约 {pct_text(metrics['grossMargin'])}，盈利模式具备较强护城河。")
    if metrics.get('netMargin') is not None and metrics['netMargin'] >= 0.2:
        highlights.append(f"净利率约 {pct_text(metrics['netMargin'])}，盈利能力处于较高水平。")
    if metrics.get('revenueGrowth') is not None and metrics['revenueGrowth'] > 0:
        highlights.append(f"收入增速约 {pct_text(metrics['revenueGrowth'])}，业务规模仍在扩张。")
    if metrics.get('operatingCashFlowMargin') is not None and metrics['operatingCashFlowMargin'] >= 0.2:
        highlights.append(f"经营现金流率约 {pct_text(metrics['operatingCashFlowMargin'])}，利润兑现成现金的能力较强。")
    if metrics.get('leverage') is not None and metrics['leverage'] < 0.5:
        highlights.append(f"负债/资产约 {pct_text(metrics['leverage'])}，资产负债表较为稳健。")
    if metrics.get('cashToLiabilities') is not None and metrics['cashToLiabilities'] >= 0.3:
        highlights.append(f"现金/总负债约 {pct_text(metrics['cashToLiabilities'])}，流动性缓冲较足。")
    if any(keyword in profile_blob for keyword in ['白酒', '茅台', '酒']):
        highlights.append('品牌力、渠道控制力和高端产品结构共同支撑了较强的盈利能力。')
    if any(keyword in profile_blob for keyword in ['社交', '游戏', '广告', '云计算', '金融科技', '互联网']):
        highlights.append('平台流量与多元业务矩阵之间存在较强的交叉变现能力。')
    if any(keyword in profile_blob for keyword in ['GPU', 'Tegra', '芯片', '处理器', '半导体', '加速计算']):
        highlights.append('芯片、软件和平台生态的协同，有助于增强客户黏性和产品壁垒。')
    return unique_points(highlights)


def generate_risks(metrics):
    risks = []
    profile_blob = profile_text_blob(metrics)
    revenue_growth = metrics.get('revenueGrowth')
    if revenue_growth is not None and revenue_growth < 0:
        risks.append(f"收入增速约 {pct_text(revenue_growth)}，增长动能偏弱。")
    net_income_growth = metrics.get('netIncomeGrowth')
    if net_income_growth is not None and net_income_growth < 0:
        risks.append(f"净利润增速约 {pct_text(net_income_growth)}，利润端承压。")
    if metrics.get('leverage') is not None and metrics['leverage'] >= 0.7:
        risks.append(f"负债/资产约 {pct_text(metrics['leverage'])}，杠杆偏高。")
    segments = metrics.get('segments') or []
    if segments:
        top_share = segments[0].get('ratio') if segments[0].get('ratio') is not None else None
        if top_share is not None and top_share >= 0.7:
            risks.append(f"核心业务收入占比约 {pct_text(top_share)}，主业集中度较高。")
    if metrics.get('pe') is not None and metrics['pe'] >= 30:
        risks.append(f"市盈率约 {metrics['pe']:.1f} 倍，市场预期已经较高。")
    if metrics.get('pb') is not None and metrics['pb'] >= 5:
        risks.append(f"市净率约 {metrics['pb']:.1f} 倍，估值溢价处于较高水平。")
    if any(keyword in profile_blob for keyword in ['白酒', '茅台', '酒']):
        risks.append('高端消费景气、渠道库存和价格体系变化，会直接影响收入与利润弹性。')
    if any(keyword in profile_blob for keyword in ['社交', '游戏', '广告', '云计算', '金融科技', '互联网']):
        risks.append('监管环境、广告景气和重点业务竞争强度变化，会影响平台型业务的利润率。')
    if any(keyword in profile_blob for keyword in ['GPU', 'Tegra', '芯片', '处理器', '半导体', '加速计算']):
        risks.append('客户资本开支周期、产品迭代节奏和行业景气变化，会放大业绩波动。')
    for warning in metrics.get('warnings') or []:
        risks.append(warning)
    return unique_points(risks)


def conclusion_text(company, metrics):
    company = clean_text(company)
    tags = []
    cautions = []
    if metrics.get('netMargin') is not None:
        if metrics['netMargin'] >= 0.2:
            tags.append('高盈利')
        elif metrics['netMargin'] < 0.1:
            cautions.append('利润率偏薄')
    if metrics.get('revenueGrowth') is not None:
        rg = metrics['revenueGrowth']
        if rg >= 0.1:
            tags.append('增长较快')
        elif rg < 0:
            cautions.append('增长承压')
    if metrics.get('leverage') is not None:
        if metrics['leverage'] < 0.5:
            tags.append('低杠杆')
        elif metrics['leverage'] >= 0.7:
            cautions.append('杠杆偏高')
    if metrics.get('operatingCashFlowMargin') is not None and metrics['operatingCashFlowMargin'] >= 0.2:
        tags.append('现金流质量较好')
    segments = metrics.get('segments') or []
    if segments:
        top_share = segments[0].get('ratio') if segments[0].get('ratio') is not None else None
        if top_share is not None and top_share >= 0.7:
            cautions.append('主业集中度高')
    if metrics.get('pe') is not None and metrics['pe'] >= 30:
        cautions.append('估值偏高')
    if not tags and not cautions:
        return f'{company}的基本面和估值画像整体中性。'
    if tags and cautions:
        return f"{company}呈现出{'、'.join(tags)}的特征，但同时存在{'、'.join(cautions)}的约束。"
    if tags:
        return f"{company}呈现出{'、'.join(tags)}的特征。"
    return f"{company}当前主要面临{'、'.join(cautions)}的问题。"


def render_report(data):
    metrics = normalize_payload(data)
    metrics['segments'] = data.get('businessSegments') or []
    company_block = render_company_block(data, metrics['marketLabel'], metrics['codeLabel'])
    business = business_points(metrics['profile'], metrics.get('segments'), data.get('marketType'))
    highlights = generate_highlights(metrics)
    risks = generate_risks(metrics)
    conclusion = conclusion_text(data.get('company'), metrics)

    return f"""{company_block}

## 业务
{bullet_lines(business, '业务描述暂缺。')}

## 财务摘要
- 收入: {metrics.get('revenue', 'NA')}
- 收入增速: {pct_text(metrics.get('revenueGrowth'))}
- 毛利率: {pct_text(metrics.get('grossMargin'))}
- 净利润: {metrics.get('netIncome', 'NA')}
- 净利润增速: {pct_text(metrics.get('netIncomeGrowth'))}
- 净利率: {pct_text(metrics.get('netMargin'))}
- 经营现金流: {metrics.get('operatingCashFlow') or 'NA'}
- 经营现金流率: {pct_text(metrics.get('operatingCashFlowMargin'))}
- 每股经营现金流: {metrics.get('operatingCashFlowPerShare') or 'NA'}
- 负债/资产: {pct_text(metrics.get('leverage'))}
- 现金/总负债: {pct_text(metrics.get('cashToLiabilities'))}
- 总市值: {fmt_num(metrics.get('marketCap'), metrics.get('currency'))}
- 市盈率: {f"{metrics['pe']:.1f}x" if metrics.get('pe') is not None else 'NA'}
- 市净率: {f"{metrics['pb']:.1f}x" if metrics.get('pb') is not None else 'NA'}
- 市销率: {f"{metrics['ps']:.1f}x" if metrics.get('ps') is not None else 'NA'}

## 亮点
{bullet_lines(highlights, '当前亮点不集中，整体表现偏均衡。')}

## 风险
{bullet_lines(risks, '当前主要风险在于增长、利润率和估值能否持续匹配。')}

## 一句话结论
- {conclusion}"""


def main():
    payload = json.loads(sys.stdin.read())
    print(render_report(payload))


if __name__ == '__main__':
    main()
