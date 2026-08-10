# Maishou API Smoke Test

用于验证 `maishou88.com` 商品价格接口是否能在 GitHub Actions 公网环境中正常调用。

## 测试范围

- 淘宝：`sourceType=1`
- 京东：`sourceType=2`
- 拼多多：`sourceType=3`
- 搜索接口：`POST https://appapi.maishou88.com/api/v3/goods/list`
- 详情接口：`POST https://appapi.maishou88.com/api/v3/goods/detail`

## 安全边界

本仓库仅做技术可用性测试：

- 使用公开出现过的第三方邀请码 `6110440`，仅用于冒烟测试；
- 不调用 `getTargetUrl`；
- 不生成推广/购买链接；
- 不保存账号、Cookie、Token 或个人信息；
- 不代表该邀请码适合正式长期使用。

测试通过后仍需进一步核对 API 返回价格与真实商品页面价格是否一致。
