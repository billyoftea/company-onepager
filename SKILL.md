---
name: company-onepager
description: Generate a structured, investment-research-style listed-company one-pager from a natural-language company name or ticker. Use when the user says things like "NVIDIA one pager", "做一下腾讯 one pager", "给我苹果公司的一页纸", "company brief", "stock snapshot", "business summary", "financial summary", or asks for highlights, risks, quality, growth, balance-sheet strength, or a concise investment view on an A-share, HK-listed, or US-listed company. Resolve the company automatically, fetch market-appropriate data, deepen the business description, and return a final-report-style six-section one-pager in Chinese.
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
5. Make the output read like a finished equity-research one-pager, not a scratchpad or analyst note to self.
6. Use the same high-level framework across A-shares, HK-listed names, and US-listed names.
7. In `业务`, explain what the company does, where revenue comes from, and what kind of business model or industry position it has.
8. In `财务摘要`, prioritize low-frequency, decision-useful data such as growth, margins, leverage, cash-flow quality, market cap, and valuation multiples.
9. Do not emphasize high-frequency trading fields such as latest price, open price, intraday range, or same-day move unless the user explicitly asks.
10. In `亮点` and `风险`, prefer thesis-like interpretation over generic boilerplate.
11. Never require the user to provide a ticker when a company name can be resolved with reasonable confidence.
12. If a data source fails, use the next fallback or state the missing field plainly instead of hallucinating.
13. Treat output as informational only, not investment advice.

## Workflow

- Pass the full relevant user request into `scripts/run_onepager.py`.
- Let the script strip phrases like `one pager` or `做一下` and resolve the company automatically.
- Inspect the output for obvious data issues.
- Convert raw data into a final-report-style summary with concrete interpretation.
- Keep the report declarative. Avoid meta phrases like `可以先看`, `可进一步结合`, or `适合继续研究` inside the report body.
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
- References:
  - `references/data-sources.md`
  - `references/report-framework.md`
