# Stage 3 — 好单库真实接口验证

测试日期：2026-08-10

目标商品：CUKTECH / 酷态科 AD653C，65W GaN，2C1A，老款方形，灰色单体版。

## 1. APIKEY 与 GitHub Actions

`HAODANKU_API_KEY` 已通过 Repository Secret 注入 GitHub Actions。

验证结果：

- Workflow 能读取 Secret 并成功调用好单库普通接口；
- Actions 日志中 Secret 显示为 `***`；
- 测试脚本不把 APIKEY 写入 JSON artifact；
- Workflow 保留 `timeout-minutes: 3`。

## 2. 官方文档运行时发现

测试脚本会在运行时下载好单库官方 OpenAPI 文档包，不硬编码未知接口。

当前文档确认：

### 淘宝商品搜索

- GET `v3.api.haodanku.com/supersearch`
- 必填：`apikey, keyword`
- 权限：普通接口

### 淘宝商品详情

- GET `v3.api.haodanku.com/item_detail`
- 必填：`apikey, itemid`
- 权限：普通接口

### 京东商品搜索/详情

- GET `v3.api.haodanku.com/unify_jdgoods_search`
- 当前账号调用结果：无京东平台权限，需要另行开通京东官方账号

### 拼多多商品搜索/详情

- GET `v3.api.haodanku.com/unify_pdd_goods_search`
- 当前账号调用结果：当前账号未开启官方授权

因此好单库不能作为当前账号下淘宝 + 京东 + 拼多多统一零门槛数据源。

## 3. 淘宝 / 天猫实际结果

好单库淘宝搜索、详情接口均已在 GitHub-hosted runner 上真实返回 HTTP 200 + `code=1 / SUCCESS`。

品牌店铺结果可以识别：

`CUKTECH酷态科旗舰店`

目标相关结果包括：

- `CUKTECH酷态科PD快充65W氮化镓充电器双typec多口40/45W套装插头...`
  - itemprice：108
  - itemendprice：78
  - 因标题包含“套装”，不能仅凭标题将其当作用户指定“灰色单体版”；但该商品页很可能包含多个规格。

- `【CUKTECH酷态科】PD快充65W氮化镓多口充电器BBJ`
  - 店铺：CUKTECH酷态科旗舰店
  - itemprice：108
  - itemendprice：108
  - 详情接口成功
  - 详情文本能确认 65W、多口、旗舰店，但没有出现 `AD653C`、`2C1A`、`灰色`、`单体` 字段。

因此好单库已经证明可以稳定取得天猫品牌旗舰店商品级价格，但当前详情 API 不提供足够的 SKU 规格信息，不能仅靠 API 自动证明某个商品结果就是“AD653C 灰色单体版”。

## 4. 外部交叉验证

公开价格索引显示：

- 商品：酷态科 65W 2C1A 氮化镓充电器 AD653C；
- 渠道：天猫精选；
- 店铺：CUKTECH酷态科旗舰店；
- 规格：灰色单体版，2C1A 三口，65W；
- 页面价：108 元；
- 近期立减后价格：78 元。

这与好单库返回的同品牌旗舰店 65W 商品“108 → 78”价格结构高度一致，可用于一次性商品页映射佐证。

但正式自动化不能把这种外部索引当作每次运行的实时 SKU API，因此仍需把“商品页级价格”和“精确 SKU 价格”两个概念分开。

## 5. 当前推荐数据源架构

| 平台 | 推荐数据源 | 状态 |
|---|---|---|
| 京东 | Maishou v1 搜索 + v3 详情，固定京东 SKU `100068768088` | 可用 |
| 淘宝/天猫 | 好单库 `supersearch` + `item_detail` | 商品页级可用，SKU 需校验 |
| 拼多多 | 尚未解决 | Maishou 详情失败；好单库要求官方授权 |

## 6. 正式系统必须遵守的限制

1. 不把商品列表的最低价无条件当作目标 SKU 价格；
2. 天猫若 API 未返回规格字段，状态标记为 `PRODUCT_PAGE_PRICE`，不能标记为 `EXACT_SKU_PRICE`；
3. 只有商品、店铺、规格均得到确认时才能发送“精确目标价”通知；
4. 若只有商品页价格满足阈值，可以生成“候选降价，需要打开页面确认规格”的低置信度状态，但默认不发送正式目标价通知；
5. 京东继续固定 SKU，不重新退回关键词第一条匹配；
6. 拼多多在找到无需官方授权且可验证店铺/商品的来源前，不参与正式价格触发。
