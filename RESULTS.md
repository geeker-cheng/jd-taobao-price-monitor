# Maishou API Smoke Test Results

测试日期：2026-08-10（GitHub Actions hosted runner）

## 结论摘要

1. `6110440` 当前可以通过 `POST /api/v1/homepage/searchList` 的邀请码/登录校验。
2. 同一 v1 请求将 `inviteCode` 留空时，淘宝、京东、拼多多均返回业务码 `401`，消息为 `用户未登录`。
3. `Kumagt/price-monitor` 文档/代码使用的 `POST /api/v3/goods/list` 当前对三个平台均返回 HTTP 200，但业务码为 `404 Not Found`，因此该 v3 搜索路径已不可用于当前价格查询。
4. v1 搜索接口在京东平台已实际返回商品列表和价格字段；淘宝和拼多多尚未通过可用性验证。

## A/B 测试

### 淘宝（sourceType=1）

关键词：`小米手环`

使用 `6110440`：
- HTTP：200
- API status：`error`
- API code：500
- message：`服务异常，请稍后重试`
- 商品数：0

空邀请码：
- HTTP：200
- API status：`error`
- API code：401
- message：`用户未登录`
- 商品数：0

结论：`6110440` 能通过与空邀请码不同的鉴权路径，但淘宝查询本轮发生服务端业务错误，不能据此认定淘宝数据源可用。

### 京东（sourceType=2）

关键词：`iPhone 16`

使用 `6110440`：
- HTTP：200
- API status：`success`
- API code：200
- 商品数：5
- 第一条商品标题：`Apple/苹果 iPhone 17 Pro 256GB 银色 支持移动联通电信5G 双卡双待手机`
- 店铺：`Apple产品京东自营旗舰店`
- actualPrice：`7899`
- originalPrice：`8099`
- couponPrice：`0`

空邀请码：
- HTTP：200
- API status：`error`
- API code：401
- message：`用户未登录`
- 商品数：0

结论：`6110440` 当前可以用于 v1 京东搜索并返回商品与价格数据。但是搜索关键词 `iPhone 16` 的首条结果却是 `iPhone 17 Pro`，因此后续正式监控不能采用“关键词搜索后直接取第一条”的策略，必须校验精确商品/规格。

### 拼多多（sourceType=3）

关键词：`纸巾`

使用 `6110440`：
- HTTP：200
- API status：`success`
- API code：200
- data：空数组
- 商品数：0

空邀请码：
- HTTP：200
- API status：`error`
- API code：401
- message：`用户未登录`
- 商品数：0

结论：`6110440` 能通过接口校验，但当前请求没有返回拼多多商品，因此尚不能认定拼多多数据源可用。

## 旧 v3 路径验证

接口：`POST https://appapi.maishou88.com/api/v3/goods/list`

淘宝、京东、拼多多均得到：

```json
{
  "status": "error",
  "code": 404,
  "message": "Not Found",
  "data": null
}
```

因此不能直接使用 `Kumagt/price-monitor` 当前记录的 v3 搜索路径。

## 下一步

下一轮需要使用用户实际希望监控的三个真实商品链接/商品 ID，分别验证：

- 能否准确命中同一商品；
- `actualPrice` 是否与真实页面公开价格一致；
- 是否能锁定容量、颜色等具体 SKU/规格；
- 淘宝与拼多多是否需要额外但合规的请求参数；
- 不调用推广分享链接接口。
