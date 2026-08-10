# Maishou API Smoke Test Results

测试日期：2026-08-10（GitHub Actions hosted runner）

## 结论摘要

1. `6110440` 当前可以通过 `POST /api/v1/homepage/searchList` 的邀请码/登录校验。
2. 同一 v1 请求将 `inviteCode` 留空时，淘宝、京东、拼多多均返回业务码 `401`，消息为 `用户未登录`。
3. `Kumagt/price-monitor` 文档/代码使用的 `POST /api/v3/goods/list` 当前对三个平台均返回 HTTP 200，但业务码为 `404 Not Found`；但 `POST /api/v3/goods/detail` 当前在京东仍然可用。
4. 精确目标：`CUKTECH/酷态科 AD653C 65W GaN 2C1A 老款方形充电器，单体`，排除 mini / Ultra / 屏显 / 卡片 / 90W / 100W / 套装 / 线材 / 电池。
5. 详情级验证结果：京东通过；拼多多搜索能返回候选，但详情 3/3 均返回 `422 商品不存在`；淘宝 4/4 精确关键词查询均返回 `500 服务异常，请稍后重试`。

## 当前接口状态

- 搜索：`POST https://appapi.maishou88.com/api/v1/homepage/searchList`
- 详情：`POST https://appapi.maishou88.com/api/v3/goods/detail`
- 旧搜索：`POST https://appapi.maishou88.com/api/v3/goods/list` 已失效
- 本测试没有调用 `https://msapi.maishou88.com/api/v1/share/getTargetUrl`，因此没有生成或使用推广购买链接。

## 邀请码 A/B 测试

使用 `6110440` 后可以进入当前搜索接口业务流程。将 `inviteCode` 留空时，淘宝、京东、拼多多均返回：

```json
{
  "code": 401,
  "message": "用户未登录"
}
```

因此 `6110440` 当前确实具有实际鉴权作用。

## AD653C 三平台精确测试

目标：

`CUKTECH/酷态科 AD653C 65W GaN 2C1A 老款方形充电器，单体`

店铺约束：
- 京东：京东自营或 CUKTECH/酷态科品牌旗舰店；
- 淘宝/天猫：CUKTECH/酷态科官方或旗舰店；
- 拼多多：CUKTECH/酷态科官方或旗舰店。

排除：

`mini / Ultra / 屏显 / 卡片 / 电能卡片 / 90W / 100W / 套装 / 套餐 / 数据线 / 充电线 / 电池`

### 淘宝 / 天猫

测试关键词：
- `酷态科 AD653C`
- `CUKTECH AD653C`
- `酷态科 65W 2C1A`
- `酷态科 65W 氮化镓`

最新一轮四个请求均得到：
- HTTP：200
- API status：`error`
- API code：`500`
- message：`服务异常，请稍后重试`
- 商品数：0

此前测试还曾出现连接超时。

结论：**失败。当前 Maishou 不适合作为淘宝 AD653C 正式价格数据源。**

### 京东

精确型号 `AD653C` 关键词本身没有直接返回商品，但 `酷态科 65W 氮化镓` 成功返回 20 个结果。筛出的 3 个老款 65W 多口候选全部来自：

`CUKTECH酷态科京东自营旗舰店`

且详情接口 `POST /api/v3/goods/detail` 对三者均成功：
- HTTP：200
- API status：`success`
- API code：200
- `shopName`：`CUKTECH酷态科京东自营旗舰店`
- `shopType`：1
- `tagList` 中包含 `自营`

候选 1：
- 标题：`CUKTECH酷态科65W氮化镓充电器多口Type-C快充头兼容40W适用小米苹果17手机/ipad/MacBookNeo笔记本电脑`
- actualPrice：`86.2`
- originalPrice：`93.2`
- couponPrice：`0`
- `jdGoodsIdB`：`3xcjcDDVDGKSVJmQFn`
- 标签包含：`自营`、`7天无理由退货`、`超级补贴`，并可能包含购新国补提示

候选 2：
- 标题：`CUKTECH酷态科65W氮化镓充电头USB/Type-C多口快充器适用40W苹果17小米/华为/三星/MacbookNeo/笔记本电脑`
- actualPrice：`77.7`
- originalPrice：`77.7`
- couponPrice：`0`
- `jdGoodsIdB`：`3nmugCitgMCAZO0wcs`
- 标签包含：`自营`、`7天无理由退货`、`超级补贴`

候选 3：
- 标题：`CUKTECH酷态科65W氮化镓充电头USB/Type-C多口快充器适用40W苹果17小米/华为/MacbookNeo笔记本`
- actualPrice：`78`
- originalPrice：`99`
- couponPrice：`0`
- `jdGoodsIdB`：`391fhWgEXxrB4zqSXI`
- 标签包含：`自营`、`7天无理由退货`

详情响应还提供 `goodsBannerList`、`shopInfo`、`defineInfo`、`tagList` 等字段，但当前测试中没有看到直接标明 `AD653C` 或“单体规格”的明确 SKU 属性字段。

结论：**京东的 Maishou 搜索 + 详情 + 自营店身份验证均通过。** 但同一京东自营旗舰店出现三个近似商品实体/活动价，因此正式监控前仍必须确定哪一个对应用户要买的“AD653C 单体”，不能擅自把最低的 `77.7` 当成目标商品价。

### 拼多多

使用 `酷态科 AD653C` 即可返回 20 个搜索结果，其中筛出 3 个高度匹配老款 65W 三口/2C1A 的候选：

候选 1：
- 标题：`【酷态科】65W手机充电器氮化镓三口适配器PD快充适用于小米苹果17`
- actualPrice：`68.9`
- shopName：`null`

候选 2：
- 标题：`【酷态科】65W氮化镓手机充电器三口适配器PD快充适用于苹果小米`
- actualPrice：`73`
- shopName：`null`

候选 3：
- 标题：`【酷态科】65W充电器头PD快充2C1A适用苹果iPhone17手机iPad6平板安卓`
- actualPrice：`78.9`
- shopName：`null`

随后分别将三个搜索返回的 `goodsId` 传入当前详情接口 `POST /api/v3/goods/detail`，三次均得到：

```json
{
  "status": "error",
  "code": 422,
  "message": "商品不存在"
}
```

结论：**失败。** 搜索层能产生看似合理的商品与价格，但详情层无法解析这些商品，且搜索层没有店铺名称，无法验证官方/旗舰店身份。因此这些 PDD 价格不能用于正式通知。

## 旧 v3 搜索路径验证

`POST https://appapi.maishou88.com/api/v3/goods/list`

淘宝、京东、拼多多均得到 HTTP 200 + 业务码：

```json
{
  "status": "error",
  "code": 404,
  "message": "Not Found",
  "data": null
}
```

因此 `Kumagt/price-monitor` 当前记录的 v3 搜索路径必须更换。

## 当前判断

| 平台 | 搜索 | 详情 | 店铺验证 | 当前是否适合正式监控 |
|---|---|---|---|---|
| 京东 | 通过 | 通过 | 自营旗舰店已验证 | **有条件通过** |
| 淘宝/天猫 | 500/偶发超时 | 无法进入 | 无 | **不通过** |
| 拼多多 | 搜索可返回候选 | 422 商品不存在 | 无 | **不通过** |

### Maishou 整体判断

Maishou **不能作为淘宝 + 京东 + 拼多多三个平台的统一正式数据源**。

目前最合理的用途是：
- 京东：可以继续使用 Maishou；
- 淘宝：需要另找数据源或网页采集；
- 拼多多：需要网页/其他数据源验证，不应依据当前 Maishou 搜索价格直接提醒。

京东正式上线前还剩最后一个核心问题：确定 AD653C 单体版的唯一京东商品实体/SKU，并对 Maishou `actualPrice` 与真实京东页面价格进行一次人工交叉验证。
