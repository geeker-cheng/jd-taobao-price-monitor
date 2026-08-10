# 京东 + 淘宝/天猫价格监控

> 基于 Python 与 GitHub Actions 的配置驱动型电商价格采集与历史记录系统。  
> 当前支持京东、淘宝/天猫，重点解决商品身份校验、价格可信度、长期状态持久化与公开仓库安全问题。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Price Monitor](https://github.com/geeker-cheng/maishou-api-smoke-test/actions/workflows/price-monitor.yml/badge.svg)](https://github.com/geeker-cheng/maishou-api-smoke-test/actions/workflows/price-monitor.yml)
[![Platforms](https://img.shields.io/badge/Platforms-JD%20%7C%20Taobao%2FTmall-orange.svg)](#支持平台与数据源)

---

## 项目简介

本项目不是“搜索结果里挑最低价”的简单爬虫，而是一个以**商品身份正确性优先**的价格采集系统。

核心原则：

- 商品找不到或映射无法确认时，宁可记录错误状态，也不自动替换成相似商品；
- 京东在映射得到验证后可记录为 `EXACT_SKU_PRICE`；
- 淘宝/天猫在当前数据源无法证明具体规格时，只记录为 `PRODUCT_PAGE_PRICE`；
- 单个平台失败不会阻塞其他平台；
- 价格大幅变化本身不会被当作异常，只要商品身份和数据源校验通过就正常记录；
- GitHub 仓库本身保存轻量状态与历史，不依赖长期运行服务器或数据库；
- 仓库按长期公开使用设计，敏感信息在运行、落盘和提交前均有保护。

当前阶段**只负责可靠采价、历史记录和运行健康状态**。目标价提醒、显著降价提醒、ChatGPT / 邮件 / Webhook 通知均未启用。

---

## 主要特性

- ✅ 京东：Maishou 搜索 / 详情接口，支持已验证稳定映射
- ✅ 淘宝 / 天猫：好单库 OpenAPI 商品搜索与详情
- ✅ 商品标题、店铺、规格族与排除项校验
- ✅ 京东自营校验
- ✅ `EXACT_SKU_PRICE` / `PRODUCT_PAGE_PRICE` / `UNVERIFIED` 价格可信度
- ✅ 最新状态、价格变化历史、数据源健康状态持久化
- ✅ 相同逻辑价格不重复写入历史
- ✅ 单数据源故障隔离
- ✅ 状态 JSON 损坏时 fail closed，避免覆盖历史
- ✅ GitHub Actions 定时运行、并发保护、5 分钟硬超时
- ✅ 状态变化自动提交回 `main`
- ✅ Secret 运行期脱敏、落盘二次脱敏、提交前安全扫描
- ✅ 配置驱动新增商品，通常无需修改 Python

---

## 支持平台与数据源

| 平台 | 数据源 | 当前价格可信度 | 状态 |
|---|---|---|---|
| 京东 | Maishou | 已验证映射可达 `EXACT_SKU_PRICE` | ✅ 已接入 |
| 淘宝 / 天猫 | 好单库 | `PRODUCT_PAGE_PRICE` | ✅ 已接入 |
| 拼多多 | — | — | ❌ 当前不支持 |

### 价格可信度

| 类型 | 含义 |
|---|---|
| `EXACT_SKU_PRICE` | 数据源实体与目标 SKU 的映射已经明确验证 |
| `PRODUCT_PAGE_PRICE` | 商品页和店铺已确认，但数据源无法证明当前价格对应指定规格 |
| `UNVERIFIED` | 商品身份或映射证据不足，不作为正式有效价格使用 |

> 数据源返回的价格不等同于用户一定可以获得的最终结算价。PLUS、88VIP、首购、金币、优惠券、跨店满减、地区补贴等账号或活动相关优惠可能需要在实际下单页面确认。

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/geeker-cheng/maishou-api-smoke-test.git
cd maishou-api-smoke-test
```

### 2. 安装依赖

推荐 Python 3.11 或更高版本：

```bash
python -m pip install -r requirements.txt
```

### 3. 配置凭据

淘宝 / 天猫数据源需要：

```text
HAODANKU_API_KEY
```

本地运行可以通过环境变量提供；GitHub Actions 中请在：

```text
Settings → Secrets and variables → Actions → Repository secrets
```

创建同名 Secret。

京东 Maishou 支持：

```text
MAISHOU_INVITE_CODE
```

仓库当前带有公开默认值 `6110440`，用于复现实验和公开项目使用。该邀请码来自公开第三方集成，可能具有第三方推广 / 归因属性，不属于本项目维护者，也不代表任何官方背书。若使用自己的邀请码，请通过环境变量或 GitHub Secret 覆盖，不要提交到仓库。

### 4. 校验商品配置

```bash
python -m price_monitor.cli validate
```

### 5. 运行测试

```bash
python -m unittest discover -s tests -v
```

### 6. 执行一次真实采价

确保所需环境变量已经配置后：

```bash
python -m price_monitor.cli run
```

### 7. 扫描公开状态文件

```bash
python -m price_monitor.cli scan-state
```

如果检测到未脱敏敏感内容，命令会以非零状态退出。

---

## 系统架构

```text
config/products.yaml
        ↓
商品配置 / 生命周期
        ↓
┌─────────────────────────────┐
│ 数据源适配层                │
│ JD → Maishou                │
│ Taobao/Tmall → Haodanku     │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 商品验证层                  │
│ 标题 / 店铺 / SKU / 自营    │
│ 稳定映射 / 错误规格排除     │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 统一 Quote 数据模型         │
│ status / price / confidence │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ MonitorEngine               │
│ 遍历所有 MONITORING 商品    │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 状态与历史                  │
│ latest / history / health   │
└──────────────┬──────────────┘
               ↓
┌─────────────────────────────┐
│ 安全层                      │
│ 脱敏 → 落盘 → commit 前扫描 │
└──────────────┬──────────────┘
               ↓
        GitHub Actions
        定时运行 + Git 持久化
```

---

## 运行流程

每次 GitHub Actions 执行：

```text
定时 / 手动触发
        ↓
Checkout 仓库
        ↓
安装 Python 与依赖
        ↓
校验 products.yaml
        ↓
运行全部单元测试
        ↓
采集所有 MONITORING 商品
        ↓
验证商品 / 店铺 / 映射
        ↓
统一为 Quote
        ↓
运行期敏感信息脱敏
        ↓
更新最新状态与数据源健康
        ↓
价格发生逻辑变化时追加历史
        ↓
写入 data/*.json 前再次脱敏
        ↓
scan-state 安全扫描
        ↓
有状态变化 → commit / push 到 main
无变化       → 直接结束
        ↓
上传 3 天保留的状态 Artifact
```

京东、淘宝两个平台彼此隔离：一个平台返回 `SOURCE_ERROR` 不会阻止另一个平台继续完成采价。

---

## 定时任务

生产 Workflow：

```text
.github/workflows/price-monitor.yml
```

当前每天按 UTC+8 运行：

| 时间 | GitHub cron (UTC) |
|---|---|
| 10:15 | 02:15 |
| 14:15 | 06:15 |
| 18:15 | 10:15 |
| 22:15 | 14:15 |

对应配置：

```yaml
15 2,6,10,14 * * *
```

同时保留手动 `workflow_dispatch`：

- `run_live=false`：只做配置校验和测试；
- `run_live=true`：校验、测试、真实采价、安全扫描并持久化状态。

Workflow 还包含：

```text
timeout-minutes: 5
concurrency: price-monitor-production
```

且没有普通 `push` 触发，因此机器人提交 `data/*.json` 后不会递归启动下一次运行。

---

## 商品配置与生命周期

商品统一配置在：

```text
config/products.yaml
```

新增商品建议从：

```text
config/products.example.yaml
```

复制模板。

生命周期：

```text
NEW
 ↓
确认商品链接 / SKU / 型号 / 规格
 ↓
验证店铺与数据源映射
 ↓
VERIFIED
 ↓
人工确认
 ↓
MONITORING
```

其他状态：

```text
PAUSED
INVALID
```

只有 `MONITORING` 商品会参与正式采集。

京东新商品原则上需要确认公开 JD SKU 与 Maishou 稳定身份的对应关系；淘宝 / 天猫在当前数据源无法证明具体 SKU 时必须保持 `PRODUCT_PAGE_PRICE`，不能强行升级为精确规格价格。

详细说明见 [docs/PRODUCT_ONBOARDING.md](docs/PRODUCT_ONBOARDING.md)。

---

## 当前示例：CUKTECH AD653C

当前仓库中的实际监控商品用于验证整套架构。

京东公开 SKU：

```text
100068768088
```

经过独立证据验证的 Maishou 稳定身份：

```text
3nmugCitgMCAZO0wcs
```

这里的 `3nmugCitgMCAZO0wcs` 是 Maishou 侧身份，不是京东公开 SKU。完整 Maishou `goodsId` 的前缀在不同运行中出现过变化，因此系统锁定的是经验证的 `jdGoodsIdB`，并在每次运行继续检查标题、店铺和京东自营身份。

映射调查过程见 [docs/JD_MAPPING.md](docs/JD_MAPPING.md)。

淘宝 / 天猫目标限定为 `CUKTECH酷态科旗舰店`，当前仍按 `PRODUCT_PAGE_PRICE` 保存。

---

## 状态文件

运行状态直接保存在仓库：

```text
data/
├── price_status.json
├── price_history.json
├── source_health.json
└── alert_state.json
```

| 文件 | 用途 |
|---|---|
| `price_status.json` | 每个商品最新采价结果、最后检查/成功时间、数据新鲜度 |
| `price_history.json` | 有效价格变化历史；相同逻辑价格不会重复追加 |
| `source_health.json` | 数据源最近成功/失败、错误信息、连续失败次数 |
| `alert_state.json` | 未来提醒系统的预留接口，当前不参与业务 |

`history_limit` 表示**每个商品最多保存多少条价格变化样本**，不是天数。

如果状态 JSON 已损坏，系统会直接失败而不是自动覆盖旧文件。

---

## 安全设计

本仓库按长期公开使用设计。

### 三层防护

1. **运行期脱敏**：数据源异常进入 stdout、Quote 或健康状态前先处理；
2. **持久化边界脱敏**：写 `data/*.json` 前递归再次清洗；
3. **提交前硬扫描**：执行 `python -m price_monitor.cli scan-state`，发现未脱敏内容则阻止 commit。

目前会重点处理：

```text
HAODANKU_API_KEY
MAISHOU_INVITE_CODE（自定义私有值）
apikey / api_key
token / access_token
authorization / Bearer
secret
password / passwd
inviteCode
```

GitHub Actions 自带的日志 Secret masking 只作为额外保护，不能替代上述公开文件安全机制。

更多说明见 [docs/PUBLIC_REPOSITORY_SECURITY.md](docs/PUBLIC_REPOSITORY_SECURITY.md)。

---

## 命令

| 命令 | 说明 |
|---|---|
| `python -m price_monitor.cli validate` | 校验 `products.yaml` |
| `python -m price_monitor.cli run` | 执行一次所有 `MONITORING` 商品采价 |
| `python -m price_monitor.cli scan-state` | 检查公开状态 JSON 是否含未脱敏敏感信息 |
| `python -m unittest discover -s tests -v` | 运行完整单元测试 |

---

## 项目结构

```text
maishou-api-smoke-test/
├── .github/
│   └── workflows/
│       └── price-monitor.yml       # 定时 / 手动 GitHub Actions
├── config/
│   ├── products.yaml               # 正式商品配置
│   └── products.example.yaml       # 新商品模板
├── data/
│   ├── price_status.json           # 最新价格状态
│   ├── price_history.json          # 价格变化历史
│   ├── source_health.json          # 数据源健康状态
│   └── alert_state.json            # 提醒接口预留状态
├── docs/
│   ├── CURRENT_SCOPE.md            # 当前开发范围
│   ├── JD_MAPPING.md               # 京东 SKU 映射证据
│   ├── PRODUCT_ONBOARDING.md       # 新增商品流程
│   └── PUBLIC_REPOSITORY_SECURITY.md # 公开仓库安全边界
├── price_monitor/
│   ├── cli.py                      # CLI 入口
│   ├── config.py                   # 配置读取与验证
│   ├── engine.py                   # 核心调度引擎
│   ├── matching.py                 # 商品 / 店铺匹配
│   ├── models.py                   # Quote 等统一模型
│   ├── state.py                    # JSON 状态与历史持久化
│   ├── security.py                 # Secret 脱敏与扫描
│   └── sources/
│       ├── base.py                 # 数据源接口
│       ├── maishou.py              # 京东数据源
│       └── haodanku.py             # 淘宝 / 天猫数据源
├── tests/                          # 单元测试
├── RESULTS.md                      # 早期 Maishou 调研记录
├── STAGE2.md                       # 历史阶段记录
├── STAGE3.md                       # 好单库验证记录
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 当前范围与限制

当前已经实现：

- 京东 / 淘宝天猫采价；
- 商品身份与店铺校验；
- 价格可信度分级；
- 历史与健康状态持久化；
- GitHub Actions 定时运行；
- 公开仓库 Secret 防护。

当前**没有实现**：

- 目标价提醒；
- 显著降价提醒；
- ChatGPT / 邮件 / Webhook 通知；
- Web UI；
- REST API；
- 自动下单；
- 拼多多正式监控。

`alert` 配置、`AlertEvent` 和 `alert_state.json` 仅作为未来扩展接口保留，当前必须保持禁用。

---

## 第三方接口说明

本项目使用的 Maishou 接口表现为应用侧接口，并非本项目能够保证长期兼容的稳定开发者 API；接口路径、字段、鉴权方式或可访问性都可能发生变化。

好单库 API 需要使用者自行获得合法 API Key，并遵守其服务条款和平台规则。

本项目不会调用 Maishou 的购买 / 推广链接转换接口，也不会自动执行购物操作。

---

## 开发与测试

修改代码或商品配置后建议执行：

```bash
python -m price_monitor.cli validate
python -m unittest discover -s tests -v
python -m price_monitor.cli scan-state
```

GitHub Actions 在每次真实采价前自动运行配置校验和测试，并在状态提交前执行安全扫描。

---

## 相关文档

- [当前开发范围](docs/CURRENT_SCOPE.md)
- [商品新增流程](docs/PRODUCT_ONBOARDING.md)
- [京东 AD653C 映射调查](docs/JD_MAPPING.md)
- [公开仓库安全设计](docs/PUBLIC_REPOSITORY_SECURITY.md)
- [Maishou 调研结果](RESULTS.md)
- [好单库真实接口验证](STAGE3.md)

---

## 致谢

项目早期调研参考了 [Kumagt/price-monitor](https://github.com/Kumagt/price-monitor) 的开源实现、数据源思路与 README 组织方式。

本项目已经根据自身目标重新设计为配置驱动、GitHub Actions 持久化、严格商品映射与公开仓库安全架构。上述引用不代表原项目作者、Maishou、好单库、京东、淘宝或天猫对本项目提供官方支持或背书。

---

## 免责声明

本项目仅用于技术研究、个人价格记录和开源学习。第三方接口返回的商品信息、库存、优惠与价格可能存在延迟或误差，实际购买价格请以电商平台结算页面为准。

使用者应自行遵守相关电商平台、数据服务商及所在地适用的服务条款和法律法规。

---

## License

本项目采用 [MIT License](LICENSE) 开源。

```text
Copyright (c) 2026 geeker-cheng
```
