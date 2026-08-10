# AD653C Stage 2 — Exact Product & Source Probe

测试日期：2026-08-10

目标商品：CUKTECH / 酷态科 65W 2C1A 氮化镓充电器 AD653C，灰色单体版（老款方形）

## 1. 京东商品唯一化

公开搜索结果中，多条独立历史价格记录均明确将 `酷态科 65W 2C1A 氮化镓充电器 AD653C` 指向京东商品：

- 京东 SKU：`100068768088`
- 商品页形式：`https://item.jd.com/100068768088.html`

因此后续京东监控应使用该 SKU 作为唯一商品标识，而不再依赖模糊关键词搜索后取第一条。

## 2. GitHub-hosted Actions 直接采集测试

Workflow run：`31374474224`

### 京东公开价格端点

测试：

`GET https://p.3.cn/prices/mgets?skuIds=J_100068768088`

结果：GitHub hosted runner 连接超时（6 秒 connect timeout），未取得价格。

结论：当前不能把该端点作为 GitHub-hosted Actions 的稳定正式数据源。

### 京东商品页

测试：

`GET https://item.jd.com/100068768088.html`

结果：请求被重定向到京东风控验证页：

`cfe.m.jd.com/privatedomain/risk_handler/...`

返回页面标题为“京东验证”，未返回 AD653C 商品正文。

结论：普通 `requests` 从 GitHub hosted runner 直接抓京东商品页不可行。

### 什么值得买公开页

分别测试了 AD653C 的天猫与拼多多公开价格页面。

结果：两页对 GitHub hosted runner 均返回 HTTP `202` 且正文为空，无法解析商品、价格或外链。

结论：SMZDM 可以用于人工/搜索引擎交叉验证，但不适合作为 GitHub-hosted Actions 的普通 HTTP 抓取源。

## 3. 当前数据源结论

| 平台 | 当前可用源 | 状态 |
|---|---|---|
| 京东 | Maishou v1 搜索 + v3 详情 | 可用；正式监控固定 SKU `100068768088` 后再做映射 |
| 淘宝/天猫 | Maishou | 不可用（持续 500/超时） |
| 拼多多 | Maishou | 不可用（搜索可见，详情 422） |
| 京东网页/公开 p.3.cn | GitHub runner 直接抓取 | 不可用/不稳定 |
| SMZDM 页面 | GitHub runner 直接抓取 | 不可用（202 空正文） |

## 4. 下一候选：好单库开放平台

官方公开说明显示：

- 商品搜索支持淘宝、京东、拼多多等多个平台；
- 普通接口使用 `apikey` 鉴权；
- 在“我的应用”创建新应用即可获取 APIKEY；
- 官方 FAQ 表述为填写资料后立即获取，免认证和审核；
- API 文档页中非付费接口可调用；
- 京东、拼多多等接口需要以实际权限为准，不能预设一定开放。

因此下一轮推荐：

1. 创建好单库免费应用并获取 APIKEY；
2. APIKEY 只保存为 GitHub Actions Secret，例如 `HAODANKU_API_KEY`；
3. 先用 AD653C 做淘宝搜索/详情实测；
4. 再检查拼多多权限并做同款实测；
5. 只有返回精确型号、店铺身份和有效价格时才纳入正式监控；
6. 不使用转链、推广链接、订单接口。

在获得 APIKEY 前，不再触发额外 GitHub Actions 测试，以避免无意义消耗额度。
