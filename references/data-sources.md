# Data Sources

## A-shares

### Resolution
- Sina suggest API: `https://suggest3.sinajs.cn/suggest/type=&key=<query>`

### Financial data
- AKShare `stock_financial_abstract_ths`
- AKShare `stock_zygc_em`

### Market data
- Sina quote API: `https://hq.sinajs.cn/list=sh<code>` or `sz<code>`
- Tencent quote API: `https://qt.gtimg.cn/q=sh<code>` or `sz<code>`

## HK-listed

### Resolution
- Sina suggest API: `https://suggest3.sinajs.cn/suggest/type=&key=<query>`

### Financial data
- AKShare `stock_financial_hk_report_em`

### Market data
- Sina quote API: `https://hq.sinajs.cn/list=hk00700`
- Tencent quote API: `https://qt.gtimg.cn/q=hk00700`

## US-listed

### Resolution
- SEC `company_tickers.json`
- Sina suggest API: `https://suggest3.sinajs.cn/suggest/type=&key=<query>` for Chinese-name lookups like 英伟达 / 苹果

### Financial data
- SEC `companyfacts`
- SEC `submissions`

### Market data
- Sina US quote API: `https://hq.sinajs.cn/list=gb_<ticker>`

## Notes
- Eastmoney spot-list endpoints are currently unreliable in this environment due to network/proxy path issues.
- Prefer resilient source mixing over single-source dependence.
- When a metric is materially unstable across concepts, prefer leaving it blank or warning instead of forcing a value.
