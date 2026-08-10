# 京东 + 淘宝/天猫价格监控

> 一个用 Python 和 GitHub Actions 定时记录京东、淘宝/天猫商品价格的小工具。  
> 商品通过 YAML 配置，价格状态和历史直接保存在仓库中。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![Price Monitor](https://github.com/geeker-cheng/jd-taobao-price-monitor/actions/workflows/price-monitor.yml/badge.svg)](https://github.com/geeker-cheng/jd-taobao-price-monitor/actions/workflows/price-monitor.yml)
[![Platforms](https://img.shields.io/badge/Platforms-JD%20%7C%20Taobao%2FTmall-orange.svg)](#支持平台)

---

## 项目简介

项目目前支持京东和淘宝/天猫。京东使用 Maishou 获取价格，淘宝/天猫使用好单库 OpenAPI。

采价前会检查商品标题、店铺和已有映射，避免把相似商品的价格写进目标商品历史。京东在映射确认后可以记录精确 SKU 价格；淘宝/天猫目前只能确认到商品页级价格。

运行结果保存在仓库内的 JSON 文件中，由 GitHub Actions 定时更新。价格提醒功能目前没有启用。

---

## 主要功能

- 京东、淘宝/天猫定时采价
- 商品标题、店铺、规格和京东自营校验
- 京东已验证商品支持 `EXACT_SKU_PRICE`
- 淘宝/天猫使用 `PRODUCT_PAGE_PRICE`
- 保存最新价格、价格变化历史和数据源健康状态
- 相同价格不会重复写入历史
- 一个平台失败不会影响另一个平台继续运行
- GitHub Actions 自动执行并提交状态文件
- Secret 脱敏和提交前安全扫描
- 新增商品主要通过 `products.yaml` 配置

---

## 支持平台

| 平台 | 数据源 | 价格级别 | 状态 |
|---|---|---|---|
| 京东 | Maishou | 已验证映射可达 `EXACT_SKU_PRICE` | 已接入 |
| 淘宝 / 天猫 | 好单库 | `PRODUCT_PAGE_PRICE` | 已接入 |
| 拼多多 | — | — | 暂不支持 |

### 价格级别

| 类型 | 含义 |
|---|---|
| `EXACT_SKU_PRICE` | 数据源商品与目标 SKU 的对应关系已经确认 |
| `PRODUCT_PAGE_PRICE` | 商品页和店铺已确认，但无法证明价格对应指定规格 |
| `UNVERIFIED` | 商品身份或映射不足，不作为有效价格使用 |

数据源价格不一定等于最终结算价。PLUS、88VIP、首购、金币、优惠券、跨店满减、地区补贴等需要以实际下单页面为准。

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/geeker-cheng/jd-taobao-price-monitor.git
cd jd-taobao-price-monitor
```

### 2. 安装依赖

推荐 Python 3.11 或更高版本：

```bash
python -m pip install -r requirements.txt
```

### 3. 配置凭据

淘宝 / 天猫需要好单库 API Key：

```text
HAODANKU_API_KEY
```

本地运行时通过环境变量提供；GitHub Actions 中添加到：

```text
Settings → Secrets and variables → Actions → Repository secrets
```

京东 Maishou 可使用：

```text
MAISHOU_INVITE_CODE
```

仓库带有公开默认值 `6110440`。该值来自公开第三方集成，可能具有第三方推广或归因属性，不属于本项目维护者，也不代表官方背书。若使用自己的邀请码，请通过环境变量或 GitHub Secret 覆盖。

### 4. 校验配置

```bash
python -m price_monitor.cli validate
```

### 5. 运行测试

```bash
python -m unittest discover -s tests -v
```

### 6. 执行一次采价

```bash
python -m price_monitor.cli run
```

### 7. 检查公开状态文件

```bash
python -m price_monitor.cli scan-state
```

检测到未脱敏敏感内容时会返回非零退出码。

---

## 系统架构

```text
config/products.yaml
        ↓
商品配置
        ↓
数据源
JD → Maishou
Taobao/Tmall → Haodanku
        ↓
商品 / 店铺 / 映射校验
        ↓
统一 Quote 数据
        ↓
MonitorEngine
        ↓
状态 / 历史 / 数据源健康
        ↓
安全扫描
        ↓
GitHub Actions 提交状态
```

核心代码：

| 文件 | 作用 |
|---|---|
| `price_monitor/config.py` | 读取和校验商品配置 |
| `price_monitor/sources/maishou.py` | 京东数据源 |
| `price_monitor/sources/haodanku.py` | 淘宝/天猫数据源 |
| `price_monitor/matching.py` | 商品和店铺匹配 |
| `price_monitor/models.py` | 统一价格数据模型 |
| `price_monitor/engine.py` | 一次完整采价流程 |
| `price_monitor/state.py` | JSON 状态与历史保存 |
| `price_monitor/security.py` | Secret 脱敏和扫描 |

---

## 运行流程

每次正式运行：

```text
定时 / 手动触发
        ↓
配置校验 + 单元测试
        ↓
读取所有 MONITORING 商品
        ↓
分别调用京东 / 淘宝数据源
        ↓
校验商品和店铺
        ↓
生成统一价格记录
        ↓
更新最新状态和数据源健康
        ↓
价格变化时追加历史
        ↓
scan-state
        ↓
有文件变化 → commit / push
无变化     → 结束
```

京东和淘宝分别执行，一个平台返回 `SOURCE_ERROR` 时不会阻止另一个平台继续采价。

---

## 定时任务

生产 Workflow：

```text
.github/workflows/price-monitor.yml
```

当前按 UTC+8 每天运行 4 次：

| 时间 | GitHub cron (UTC) |
|---|---|
| 10:15 | 02:15 |
| 14:15 | 06:15 |
| 18:15 | 10:15 |
| 22:15 | 14:15 |

```yaml
15 2,6,10,14 * * *
```

也可以手动运行：

- `run_live=false`：只做配置校验和测试
- `run_live=true`：完成测试、采价、安全扫描和状态持久化

Workflow 设置了：

```text
timeout-minutes: 5
concurrency: price-monitor-production
```

没有普通 `push` 触发，因此机器人提交状态文件后不会再次触发自身。

---

## 商品配置

商品定义在：

```text
config/products.yaml
```

新增商品可以参考：

```text
config/products.example.yaml
```

商品生命周期：

```text
NEW → VERIFIED → MONITORING
```

另外还有：

```text
PAUSED
INVALID
```

只有 `MONITORING` 商品会参与正式采价。

京东商品需要尽量确认公开 JD SKU 与 Maishou 稳定身份之间的对应关系。淘宝/天猫如果数据源无法确认指定 SKU，则保持 `PRODUCT_PAGE_PRICE`。

详细流程见 [docs/PRODUCT_ONBOARDING.md](docs/PRODUCT_ONBOARDING.md)。

---

## 当前示例：CUKTECH AD653C

仓库目前监控 CUKTECH AD653C 65W 充电器，用于实际验证整个流程。

京东公开 SKU：

```text
100068768088
```

已确认的 Maishou 稳定身份：

```text
3nmugCitgMCAZO0wcs
```

后者是 Maishou 侧 ID，不是京东 SKU。完整 `goodsId` 的前缀曾在不同运行中变化，因此系统锁定 `jdGoodsIdB`，并继续校验商品标题、店铺和自营身份。

映射过程见 [docs/JD_MAPPING.md](docs/JD_MAPPING.md)。

淘宝/天猫当前限定 `CUKTECH酷态科旗舰店`，保存为 `PRODUCT_PAGE_PRICE`。

---

## 状态文件

```text
data/
├── price_status.json
├── price_history.json
├── source_health.json
└── alert_state.json
```

| 文件 | 用途 |
|---|---|
| `price_status.json` | 每个商品最新采价结果和时间 |
| `price_history.json` | 有效价格变化历史 |
| `source_health.json` | 数据源最近成功、失败和连续失败次数 |
| `alert_state.json` | 提醒功能预留，当前不使用 |

`history_limit` 表示每个商品最多保存多少条价格变化记录，不是保存天数。

损坏的状态 JSON 不会被静默覆盖，系统会直接报错退出。

---

## 安全

仓库设计为长期公开使用。

状态提交前有三层处理：

1. 数据源异常信息进入状态前先脱敏
2. 写入 `data/*.json` 前再次递归清洗
3. `git commit` 前执行 `python -m price_monitor.cli scan-state`

重点保护：

```text
HAODANKU_API_KEY
私有 MAISHOU_INVITE_CODE
apikey / api_key
token / access_token
authorization / Bearer
secret
password / passwd
inviteCode
```

更多说明见 [docs/PUBLIC_REPOSITORY_SECURITY.md](docs/PUBLIC_REPOSITORY_SECURITY.md)。

---

## 常用命令

| 命令 | 说明 |
|---|---|
| `python -m price_monitor.cli validate` | 校验商品配置 |
| `python -m price_monitor.cli run` | 执行一次采价 |
| `python -m price_monitor.cli scan-state` | 扫描公开状态文件 |
| `python -m unittest discover -s tests -v` | 运行测试 |

---

## 项目结构

```text
jd-taobao-price-monitor/
├── .github/
│   └── workflows/
│       └── price-monitor.yml
├── config/
│   ├── products.yaml
│   └── products.example.yaml
├── data/
│   ├── price_status.json
│   ├── price_history.json
│   ├── source_health.json
│   └── alert_state.json
├── docs/
│   ├── CURRENT_SCOPE.md
│   ├── JD_MAPPING.md
│   ├── PRODUCT_ONBOARDING.md
│   └── PUBLIC_REPOSITORY_SECURITY.md
├── price_monitor/
│   ├── cli.py
│   ├── config.py
│   ├── engine.py
│   ├── matching.py
│   ├── models.py
│   ├── state.py
│   ├── security.py
│   └── sources/
│       ├── base.py
│       ├── maishou.py
│       └── haodanku.py
├── tests/
├── RESULTS.md
├── STAGE2.md
├── STAGE3.md
├── requirements.txt
├── LICENSE
└── README.md
```

---

## 当前限制

目前没有实现：

- 目标价提醒和降价提醒
- ChatGPT / 邮件 / Webhook 通知
- Web UI
- REST API
- 自动下单
- 拼多多正式监控

`alert` 配置、`AlertEvent` 和 `alert_state.json` 只作为以后扩展的接口保留。

---

## 第三方接口

Maishou 当前使用的是应用侧接口，接口路径、字段和鉴权方式可能变化，本项目无法保证长期兼容。

好单库 API Key 需要使用者自行申请并遵守其服务条款。

本项目不会调用 Maishou 的购买或推广链接转换接口，也不会执行自动购物。

### 维护状态说明

仓库作者本人也长期使用这套工具进行商品监控。如果仓库近期仍有正常的采价记录和维护活动，可以把它作为当前接口与运行流程仍可用的一个参考；在作者仍持续使用期间，发现接口失效或采价流程异常后也会尽快修复。

Maishou、好单库等均属于第三方服务，接口仍可能随时调整。如果仓库已经长时间没有维护或没有新的运行记录，请不要默认这些接口仍然有效，建议先查看最近的 GitHub Actions 运行结果，或手动执行一次采价进行确认。

---

## 相关文档

- [当前开发范围](docs/CURRENT_SCOPE.md)
- [商品新增流程](docs/PRODUCT_ONBOARDING.md)
- [京东 AD653C 映射调查](docs/JD_MAPPING.md)
- [公开仓库安全设计](docs/PUBLIC_REPOSITORY_SECURITY.md)
- [Maishou 调研结果](RESULTS.md)
- [好单库接口验证](STAGE3.md)

---

## 致谢

项目早期调研参考了 [Kumagt/price-monitor](https://github.com/Kumagt/price-monitor) 的开源实现和数据源思路。

---

## 免责声明

本项目用于技术研究、个人价格记录和开源学习。第三方接口返回的商品信息、库存、优惠和价格可能存在延迟或误差，实际购买价格以电商平台结算页面为准。

使用者应自行遵守相关平台、数据服务商及所在地适用的服务条款和法律法规。

---

## License

本项目采用 [MIT License](LICENSE) 开源。

```text
Copyright (c) 2026 geeker-cheng
```
