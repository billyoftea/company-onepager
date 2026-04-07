# Data Sources

## A-shares

### Resolution
- Sina suggest API: `https://suggest3.sinajs.cn/suggest/type=&key=<query>`

### Financial data
- AKShare `stock_financial_abstract_ths`
- AKShare `stock_zygc_em`

### Company profile
- AKShare `stock_individual_basic_info_xq`
- AKShare `stock_individual_info_em`

### Market data
- Tencent quote API: `https://qt.gtimg.cn/q=sh<code>` or `sz<code>` for PE/PB
- Prefer low-frequency fields such as market cap and valuation over intraday price fields

## HK-listed

### Resolution
- Sina suggest API: `https://suggest3.sinajs.cn/suggest/type=&key=<query>`

### Financial data
- AKShare `stock_financial_hk_report_em`

### Company profile
- AKShare `stock_hk_company_profile_em`
- AKShare `stock_individual_basic_info_hk_xq`

### Market data
- Tencent quote API: `https://qt.gtimg.cn/q=hk00700` for market cap / PE / PB
- Prefer low-frequency fields such as market cap and valuation over intraday price fields

## US-listed

### Resolution
- SEC `company_tickers.json`
- Sina suggest API: `https://suggest3.sinajs.cn/suggest/type=&key=<query>` for Chinese-name lookups like 英伟达 / 苹果

### Financial data
- SEC `companyfacts`
- SEC `submissions`

### Company profile
- AKShare `stock_individual_basic_info_us_xq`

### Market data
- Sina US quote API: `https://hq.sinajs.cn/list=gb_<ticker>` for market cap / PE
- Prefer low-frequency fields such as market cap and valuation over intraday price fields

## Notes
- Eastmoney spot-list endpoints are currently unreliable in this environment due to network/proxy path issues.
- Prefer resilient source mixing over single-source dependence.
- When a metric is materially unstable across concepts, prefer leaving it blank or warning instead of forcing a value.
- For final one-pagers, use business-profile sources plus financial statements together, rather than relying on industry labels alone.
