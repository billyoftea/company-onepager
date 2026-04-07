---
name: company-onepager
description: Generate a structured, investment-research-style listed-company one-pager from a natural-language company name or ticker. Use when the user says things like "NVIDIA one pager", "做一下腾讯 one pager", "给我苹果公司的一页纸", "company brief", "stock snapshot", "business summary", "financial summary", or asks for highlights, risks, quality, growth, balance-sheet strength, or a concise investment view on an A-share, HK-listed, or US-listed company. Resolve the company automatically, fetch market-appropriate data, and return a six-section one-pager in concise analyst-style Chinese.
---

# Company One-Pager

1. Treat short requests like `公司名 + one pager` as a direct trigger. Do not ask follow-up questions unless the company is materially ambiguous.
2. Run `scripts/run_onepager.py "<full user request or company/ticker>"` as the main entry point.
3. Let the script normalize the request, extract the company identifier, then auto-route by market:
   - A-shares -> AKShare financials + Sina/Tencent market data
   - HK-listed -> AKShare HK financial reports + Sina/Tencent market data
   - US-listed -> SEC mapping + SEC companyfacts
4. Return exactly these sections in order:
   - 公司
   - 业务
   - 财务摘要
   - 亮点
   - 风险
   - 一句话结论
5. Make the output feel like a concise first-pass equity research note, not a raw data dump.
6. In `业务`, explain how the company makes money, using segments, industry labels, or business concentration when available.
7. In `财务摘要`, include interpreted metrics such as margins, leverage, cash-flow quality, valuation proxies, or price-position context when available.
8. In `亮点` and `风险`, prefer thesis-like interpretation over generic boilerplate.
9. Never require the user to provide a ticker when a company name can be resolved with reasonable confidence.
10. If a data source fails, use the next fallback or state the missing field plainly instead of hallucinating.
11. Treat output as informational only, not investment advice.

## Workflow

- Pass the full relevant user request into `scripts/run_onepager.py`.
- Let the script strip phrases like `one pager` or `做一下` and resolve the company automatically.
- Inspect the output for obvious data issues.
- Convert raw data into an analyst-style summary with concrete interpretation.
- If a field is missing or unstable, state that plainly instead of hallucinating.
- Return the final one-pager in Chinese.

## Resources

- Entry point: `scripts/run_onepager.py`
- Resolver/shared helpers: `scripts/common.py`
- Market-specific fetchers:
  - `scripts/cn_onepager.py`
  - `scripts/hk_onepager.py`
  - `scripts/us_onepager.py`
- Renderer: `scripts/render_onepager.py`
- Reference: `references/data-sources.md`
