import json
import sys


def fmt_num(value, usd=False):
    if value in (None, '', False):
        return 'NA'
    if isinstance(value, str):
        return value
    number = float(value)
    sign = '-' if number < 0 else ''
    number = abs(number)
    prefix = '$' if usd else ''
    if number >= 1e12:
        return f'{sign}{prefix}{number/1e12:.2f}T'
    if number >= 1e9:
        return f'{sign}{prefix}{number/1e9:.2f}B'
    if number >= 1e8 and not usd:
        return f'{sign}{number/1e8:.2f}亿'
    if number >= 1e6:
        return f'{sign}{prefix}{number/1e6:.2f}M'
    return f'{sign}{prefix}{number:.2f}'


def safe_float(value):
    if value in (None, '', False):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(',', '').replace('%', '').strip()
    try:
        return float(text)
    except Exception:
        return None


def ratio(a, b):
    a = safe_float(a)
    b = safe_float(b)
    if a is None or b in (None, 0):
        return None
    return a / b


def pct_text(value, digits=1):
    if value is None:
        return 'NA'
    return f'{value * 100:.{digits}f}%'


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


def first_available(*values):
    for value in values:
        if value not in (None, '', False):
            return value
    return None


def top_segments_text(segments):
    parts = []
    for seg in segments[:3]:
        name = seg.get('segment')
        share = seg.get('ratio')
        if not name:
            continue
        if share is not None:
            parts.append(f"{name}({share * 100:.1f}%)")
        else:
            parts.append(name)
    return '、'.join(parts)


def price_position_text(price, low, high):
    price = safe_float(price)
    low = safe_float(low)
    high = safe_float(high)
    if None in (price, low, high) or high <= low:
        return None
    pos = (price - low) / (high - low)
    return pct_text(pos)


def summarize_cn_conclusion(company, growth, roe, debt_ratio):
    tags = []
    if growth is not None:
        if growth >= 0.1:
            tags.append('增长较快')
        elif growth > 0:
            tags.append('仍在增长')
        else:
            tags.append('增长承压')
    if roe is not None:
        if roe >= 15:
            tags.append('回报率高')
        elif roe >= 8:
            tags.append('回报率尚可')
    if debt_ratio is not None:
        if debt_ratio < 30:
            tags.append('杠杆低')
        elif debt_ratio > 70:
            tags.append('杠杆偏高')
    if not tags:
        return f'{company} 目前已可自动生成 one-pager，适合做首轮研究。'
    return f"{company} 当前呈现出{'、'.join(tags)}的特征，适合先列入研究清单，再结合公告做深挖。"


def summarize_hk_conclusion(company, margin, leverage, ocf_margin):
    tags = []
    if margin is not None:
        if margin >= 0.2:
            tags.append('盈利能力强')
        elif margin >= 0.1:
            tags.append('盈利能力尚可')
        else:
            tags.append('利润率偏薄')
    if leverage is not None:
        if leverage < 0.5:
            tags.append('杠杆可控')
        elif leverage > 0.7:
            tags.append('杠杆偏高')
    if ocf_margin is not None and ocf_margin > 0.2:
        tags.append('现金流质量不错')
    if not tags:
        return f'{company} 已可自动生成港股 one-pager，适合做基本面快速筛选。'
    return f"{company} 当前整体呈现{'、'.join(tags)}的画像，比较适合做首轮投研判断。"


def summarize_us_conclusion(company, margin, leverage, approx_pe, price_pos):
    tags = []
    if margin is not None:
        if margin >= 0.2:
            tags.append('高盈利')
        elif margin < 0.1:
            tags.append('盈利偏薄')
    if leverage is not None:
        if leverage < 0.5:
            tags.append('低杠杆')
        elif leverage > 0.7:
            tags.append('高杠杆')
    if approx_pe is not None:
        if approx_pe >= 30:
            tags.append('估值不低')
        elif approx_pe <= 15:
            tags.append('估值压力不大')
    if price_pos is not None and price_pos >= 0.8:
        tags.append('股价接近区间高位')
    if not tags:
        return f'{company} 已可自动拉取 SEC 财务和行情生成 one-pager，适合做首轮研究。'
    return f"{company} 当前更像一只{'、'.join(tags)}的标的，适合在基本面判断后再结合估值与预期做取舍。"


def render_cn(data):
    f = data.get('financials', {})
    market = data.get('market', {})
    segments = data.get('businessSegments') or []

    revenue_growth = safe_float(f.get('营业总收入同比增长率'))
    profit_growth = safe_float(first_available(f.get('净利润同比增长率'), f.get('扣非净利润同比增长率')))
    gross_margin = safe_float(f.get('销售毛利率'))
    net_margin = safe_float(f.get('销售净利率'))
    roe = safe_float(f.get('净资产收益率'))
    debt_ratio = safe_float(f.get('资产负债率'))
    ocf_per_share = safe_float(f.get('每股经营现金流'))
    top_share = segments[0].get('ratio') if segments else None
    segment_text = top_segments_text(segments)

    business = []
    if segment_text:
        business.append(f'主营收入主要由 {segment_text} 驱动，能较快看出公司靠什么赚钱。')
    business.append('A 股版 one-pager 更强调增长、盈利、回报率和资产负债表的组合质量。')
    if top_share is not None and top_share >= 0.7:
        business.append(f'头部业务收入占比约 {top_share * 100:.1f}%，主业集中度较高。')

    highlights = []
    if gross_margin is not None and gross_margin >= 50:
        highlights.append(f'销售毛利率约 {gross_margin:.2f}%，通常意味着产品、品牌或渠道具备较强议价能力。')
    if roe is not None and roe >= 15:
        highlights.append(f'净资产收益率约 {roe:.2f}%，资本回报表现亮眼。')
    if revenue_growth is not None and revenue_growth > 0:
        highlights.append(f'营业总收入同比增长 {revenue_growth:.2f}%，收入端仍在扩张。')
    if net_margin is not None and net_margin >= 20:
        highlights.append(f'销售净利率约 {net_margin:.2f}%，利润转化能力较强。')
    if ocf_per_share is not None and ocf_per_share > 0:
        highlights.append(f'每股经营现金流为 {ocf_per_share:.2f}，主营业务具备现金回流能力。')

    risks = []
    if debt_ratio is not None and debt_ratio >= 60:
        risks.append(f'资产负债率约 {debt_ratio:.2f}%，杠杆偏高，需要继续盯债务和偿付结构。')
    if revenue_growth is not None and revenue_growth < 0:
        risks.append(f'营业总收入同比增长 {revenue_growth:.2f}%，增长动能偏弱。')
    if profit_growth is not None and profit_growth < 0:
        risks.append(f'净利润同比增长 {profit_growth:.2f}%，利润端有压力。')
    if top_share is not None and top_share >= 0.7:
        risks.append('业务集中度较高，单一核心品类或单一主线景气度波动会放大业绩波动。')
    if data.get('warnings'):
        risks.append('部分字段抓取受公开接口稳定性影响，重要结论前应与公司公告交叉核验。')
    if not risks:
        risks.append('公开聚合源和正式公告之间可能存在细微口径差，正式下结论前仍建议复核。')

    conclusion = summarize_cn_conclusion(data.get('company'), None if revenue_growth is None else revenue_growth / 100, roe, debt_ratio)

    return f"""{render_company_block(data, 'A股', '代码')}

## 业务
{bullet_lines(business, '业务描述待补充。')}

## 财务摘要
- 营业总收入: {f.get('营业总收入', 'NA')}
- 营业总收入同比: {f.get('营业总收入同比增长率', 'NA')}
- 净利润: {f.get('净利润', 'NA')}
- 净利润同比: {first_available(f.get('净利润同比增长率'), f.get('扣非净利润同比增长率'), 'NA')}
- 销售毛利率: {f.get('销售毛利率', 'NA')}
- 销售净利率: {f.get('销售净利率', 'NA')}
- 净资产收益率: {f.get('净资产收益率', 'NA')}
- 资产负债率: {f.get('资产负债率', 'NA')}
- 每股经营现金流: {f.get('每股经营现金流', 'NA')}
- 最新价: {market.get('price', 'NA')}
- 开盘/昨收: {market.get('open', 'NA')} / {market.get('prev_close', 'NA')}
- 日内区间: {market.get('low', 'NA')} - {market.get('high', 'NA')}

## 亮点
{bullet_lines(highlights, 'A 股财务与行情数据链路已接通，可以直接做第一轮筛选。')}

## 风险
{bullet_lines(risks, '需结合公司公告继续核验。')}

## 一句话结论
- {conclusion}"""


def render_hk(data):
    f = data.get('financials', {})
    market = data.get('market', {})
    margin = ratio(f.get('netIncome'), f.get('revenue'))
    leverage = ratio(f.get('liabilities'), f.get('assets'))
    ocf_margin = ratio(f.get('operatingCashFlow'), f.get('revenue'))

    business = [
        '港股版 one-pager 更适合先看盈利能力、杠杆水平和现金流，再结合股价反馈判断市场预期。',
    ]
    if margin is not None and leverage is not None:
        business.append(f'从财务画像看，当前净利率约 {margin * 100:.1f}%，负债占总资产比例约 {leverage * 100:.1f}%。')
    if ocf_margin is not None:
        business.append(f'经营现金流收入比约 {ocf_margin * 100:.1f}%，能帮助判断利润的含金量。')

    highlights = []
    if margin is not None and margin >= 0.2:
        highlights.append(f'净利率约 {margin * 100:.1f}%，盈利质量偏强。')
    if leverage is not None and leverage < 0.6:
        highlights.append(f'负债占总资产比例约 {leverage * 100:.1f}%，资产负债表压力不大。')
    if ocf_margin is not None and ocf_margin > 0.2:
        highlights.append(f'经营现金流收入比约 {ocf_margin * 100:.1f}%，现金流表现不错。')
    if safe_float(market.get('change_pct')) is not None:
        highlights.append(f"最新行情涨跌幅 {market.get('change_pct')}%，可以把市场反馈和财务画像放在一起看。")

    risks = []
    if leverage is not None and leverage >= 0.7:
        risks.append(f'负债占总资产比例约 {leverage * 100:.1f}%，杠杆偏高，需要关注再融资和偿债能力。')
    if margin is not None and margin < 0.1:
        risks.append(f'净利率约 {margin * 100:.1f}%，利润安全垫偏薄。')
    if ocf_margin is not None and ocf_margin < 0.1:
        risks.append(f'经营现金流收入比约 {ocf_margin * 100:.1f}%，利润兑现成现金的能力偏弱。')
    if data.get('warnings'):
        risks.append('公开网页行情和聚合财报字段偶尔会抖，关键字段最好二次校验。')
    if not risks:
        risks.append('港股字段映射仍需结合原始财报科目名做交叉确认。')

    conclusion = summarize_hk_conclusion(data.get('company'), margin, leverage, ocf_margin)

    return f"""{render_company_block(data, '港股', '代码')}

## 业务
{bullet_lines(business, '业务描述待补充。')}

## 财务摘要
- 收入: {fmt_num(f.get('revenue'))}
- 毛利: {fmt_num(f.get('grossProfit'))}
- 净利润: {fmt_num(f.get('netIncome'))}
- 净利率: {pct_text(margin)}
- 总资产: {fmt_num(f.get('assets'))}
- 总负债: {fmt_num(f.get('liabilities'))}
- 负债/资产: {pct_text(leverage)}
- 现金: {fmt_num(f.get('cash'))}
- 经营现金流: {fmt_num(f.get('operatingCashFlow'))}
- 经营现金流/收入: {pct_text(ocf_margin)}
- 最新价: {market.get('price', 'NA')}
- 开盘/昨收: {market.get('open', 'NA')} / {market.get('prev_close', 'NA')}
- 日内区间: {market.get('low', 'NA')} - {market.get('high', 'NA')}
- 涨跌幅: {market.get('change_pct', 'NA')}

## 亮点
{bullet_lines(highlights, '港股财报与行情抓取已接通，可以先做首轮研究。')}

## 风险
{bullet_lines(risks, '需结合公告继续做交叉核验。')}

## 一句话结论
- {conclusion}"""


def render_us(data):
    f = data.get('financials', {})
    market = data.get('market', {})
    profile = data.get('profile', {})

    margin = ratio(f.get('netIncome'), f.get('revenue'))
    leverage = ratio(f.get('liabilities'), f.get('assets'))
    ocf_margin = ratio(f.get('operatingCashFlow'), f.get('revenue'))
    cash_ratio = ratio(f.get('cash'), f.get('liabilities'))
    fcf = None
    if safe_float(f.get('operatingCashFlow')) is not None and safe_float(f.get('capex')) is not None:
        fcf = safe_float(f.get('operatingCashFlow')) - safe_float(f.get('capex'))

    market_cap = safe_float(market.get('market_cap'))
    net_income = safe_float(f.get('netIncome'))
    approx_pe = None
    if market_cap and net_income and net_income > 0:
        approx_pe = market_cap / net_income
    price_pos = None
    price_val = safe_float(market.get('price'))
    low_52 = safe_float(market.get('year_low'))
    high_52 = safe_float(market.get('year_high'))
    if None not in (price_val, low_52, high_52) and high_52 > low_52:
        price_pos = (price_val - low_52) / (high_52 - low_52)

    business = []
    if profile.get('sicDescription'):
        business.append(f"公司所属行业为 {profile.get('sicDescription')}，可以先把它放进对应产业链框架里理解。")
    if margin is not None and ocf_margin is not None:
        business.append(f'从财务侧看，当前净利率约 {margin * 100:.1f}%，经营现金流率约 {ocf_margin * 100:.1f}%。')
    if profile.get('website'):
        business.append(f"如需继续深挖产品和客户结构，可进一步抓取官网 {profile.get('website')} 与 IR 页面。")

    highlights = []
    if margin is not None and margin >= 0.2:
        highlights.append(f'净利率约 {margin * 100:.1f}%，盈利能力很强。')
    if leverage is not None and leverage < 0.5:
        highlights.append(f'负债占总资产比例约 {leverage * 100:.1f}%，资产负债表偏稳健。')
    if ocf_margin is not None and ocf_margin > 0.2:
        highlights.append(f'经营现金流率约 {ocf_margin * 100:.1f}%，利润现金化能力不错。')
    if fcf is not None and fcf > 0:
        highlights.append(f'粗略自由现金流约 {fmt_num(fcf, usd=True)}，说明业务不只是账面利润好看。')
    if approx_pe is not None:
        highlights.append(f'按当前市值粗略估算，市盈率约 {approx_pe:.1f} 倍，可直接纳入估值讨论。')

    risks = []
    if leverage is not None and leverage >= 0.7:
        risks.append(f'负债占总资产比例约 {leverage * 100:.1f}%，资本结构压力偏大。')
    if margin is not None and margin < 0.1:
        risks.append(f'净利率约 {margin * 100:.1f}%，盈利安全垫不厚。')
    if approx_pe is not None and approx_pe >= 30:
        risks.append(f'粗略市盈率约 {approx_pe:.1f} 倍，说明市场预期已经不低。')
    if price_pos is not None and price_pos >= 0.8:
        risks.append(f'股价位于近 52 周区间的 {pct_text(price_pos)} 位置，预期如果降温，回撤可能放大。')
    if cash_ratio is not None and cash_ratio < 0.2:
        risks.append(f'现金/负债比约 {cash_ratio * 100:.1f}%，流动性缓冲不算厚。')
    if data.get('warnings'):
        risks.extend(data.get('warnings'))
    if not risks:
        risks.append('SEC 字段虽然权威，但不同公司披露口径仍可能有概念差异，正式结论前仍应复核。')

    conclusion = summarize_us_conclusion(data.get('company'), margin, leverage, approx_pe, price_pos)

    return f"""{render_company_block(data, '美股', '代码')}

## 业务
{bullet_lines(business, '业务描述待补充。')}

## 财务摘要
- 收入: {fmt_num(f.get('revenue'), usd=True)}
- 净利润: {fmt_num(f.get('netIncome'), usd=True)}
- 净利率: {pct_text(margin)}
- 总资产: {fmt_num(f.get('assets'), usd=True)}
- 总负债: {fmt_num(f.get('liabilities'), usd=True)}
- 负债/资产: {pct_text(leverage)}
- 现金: {fmt_num(f.get('cash'), usd=True)}
- 现金/负债: {pct_text(cash_ratio)}
- 经营现金流: {fmt_num(f.get('operatingCashFlow'), usd=True)}
- 经营现金流/收入: {pct_text(ocf_margin)}
- 资本开支: {fmt_num(f.get('capex'), usd=True)}
- 粗略自由现金流: {fmt_num(fcf, usd=True)}
- 粗略市盈率: {f'{approx_pe:.1f}x' if approx_pe is not None else 'NA'}
- 最新价: {market.get('price', 'NA')}
- 开盘价: {market.get('open', 'NA')}
- 日内区间: {market.get('low', 'NA')} - {market.get('high', 'NA')}
- 52周区间位置: {pct_text(price_pos)}
- 涨跌幅: {market.get('change_pct', 'NA')}

## 亮点
{bullet_lines(highlights, '已接入 SEC 财务披露和美股行情，可以直接进入基本面首轮判断。')}

## 风险
{bullet_lines(risks, '需结合 10-K/10-Q 原文继续核验。')}

## 一句话结论
- {conclusion}"""


def main():
    payload = json.loads(sys.stdin.read())
    market = payload.get('marketType')
    if market == 'CN':
        print(render_cn(payload))
    elif market == 'HK':
        print(render_hk(payload))
    else:
        print(render_us(payload))


if __name__ == '__main__':
    main()
