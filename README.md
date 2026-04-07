# company-onepager

一个面向 OpenClaw / AgentSkills 的上市公司 one-pager skill。

目标是让代理在收到类似下面的请求时，自动解析公司、抓取对应市场的数据，并生成**最终版风格**的一页式投研摘要，而不是模板化的数据拼接。

## 适用场景

支持这类自然语言触发：

- `nvidia one pager`
- `腾讯 one pager`
- `贵州茅台 one pager`
- `给我苹果公司的一页纸`
- `做一下特斯拉 company brief`

## 当前能力

- 自动识别公司名或 ticker
- 自动判断市场
  - A股
  - 港股
  - 美股
- 自动抓取对应数据源
- 输出统一六段式报告：
  - 公司
  - 业务
  - 财务摘要
  - 亮点
  - 风险
  - 一句话结论

## 设计原则

这个 skill 当前重点是三件事：

1. **像最终报告**
   - 避免“可以先看”“适合继续研究”这类过程化措辞
   - 输出更像可以直接交付的一页纸摘要

2. **统一框架**
   - A股、港股、美股尽量使用同一套分析骨架
   - 重点看业务、增长、利润率、现金流、杠杆、估值

3. **偏低频信息**
   - 优先使用更适合投研判断的低频数据
   - 比如收入、利润、现金流、总市值、PE、PB、PS
   - 不强调开盘价、日内波动、盘口类高频字段

## 数据来源

### A股
- AKShare `stock_financial_abstract_ths`
- AKShare `stock_zygc_em`
- AKShare `stock_individual_info_em`
- AKShare `stock_individual_basic_info_xq`
- 腾讯行情字段（用于估值补充）

### 港股
- AKShare `stock_financial_hk_report_em`
- AKShare `stock_hk_company_profile_em`
- AKShare `stock_individual_basic_info_hk_xq`
- 腾讯行情字段（用于市值/估值补充）

### 美股
- SEC `company_tickers.json`
- SEC `companyfacts`
- SEC `submissions`
- AKShare `stock_individual_basic_info_us_xq`
- 新浪美股估值字段

## 输出风格

当前版本会尽量做到：

- `业务` 不只报行业标签，而是描述公司怎么赚钱、业务结构和商业模式
- `财务摘要` 统一落在增长、利润率、现金流、杠杆、估值上
- `亮点` 和 `风险` 更接近投资逻辑，而不是空泛模板句
- `一句话结论` 给出压缩后的投研判断

## 使用方式

主入口：

```bash
python3 skills/company-onepager/scripts/run_onepager.py "nvidia one pager"
```

也可以直接传公司名或 ticker：

```bash
python3 skills/company-onepager/scripts/run_onepager.py "腾讯"
python3 skills/company-onepager/scripts/run_onepager.py "600519"
python3 skills/company-onepager/scripts/run_onepager.py "AAPL"
```

## 仓库结构

```text
company-onepager/
├── SKILL.md
├── README.md
├── references/
│   ├── data-sources.md
│   └── report-framework.md
└── scripts/
    ├── common.py
    ├── run_onepager.py
    ├── cn_onepager.py
    ├── hk_onepager.py
    ├── us_onepager.py
    └── render_onepager.py
```

## 现阶段已知限制

- 个别公司的业务描述仍受公开资料质量影响
- 不同市场的数据口径并不完全一致，尤其是港股字段映射
- 某些估值或资本开支字段属于近似值，需要谨慎解读
- 这仍然是 one-pager，不是完整深度研报

## 后续可继续增强的方向

- 接入官网 / IR / 年报正文抓取，进一步增强业务理解
- 补充分部、地区、客户结构等更深层业务拆解
- 增加催化剂、跟踪指标、估值对比等更像正式投研框架的模块

## 免责声明

仅供信息整理与研究参考，不构成任何投资建议。
