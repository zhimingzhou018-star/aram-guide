# 海克斯大乱斗一图流站

纯静态、手机优先的英雄攻略站。数据由 `scripts/build_onepager_site_data.py` 从当前英雄数据和 Figma 工程目录生成。

本地预览：

```powershell
python -m http.server 8879 --bind 127.0.0.1 --directory web/onepager-site
```

## 漏斗统计

统计入口在 `analytics-config.js`。创建 PostHog 项目后，把 Project API Key 填入 `posthogKey`，并将 `enabled` 改为 `true`。Key 为空或 `enabled` 为 `false` 时不会下载 PostHog SDK，也不会发送任何统计请求。

已记录的业务事件：

- `home_view`
- `hero_search`
- `hero_card_click`
- `guide_view`
- `return_home`

建议在 PostHog 中建立 `home_view → hero_card_click → guide_view → return_home` 漏斗，并把 `hero_search` 作为搜索用户的可选步骤或细分条件。

## 图片缓存

`sw.js` 会持久缓存用户实际加载过的英雄头像和攻略图。发布新一轮攻略时，同时提升 HTML 中的 `rev`、`app.js` 的数据版本和 `sw.js` 的 `CACHE_NAME`，浏览器便会清理旧版缓存。

正式发布路径：`https://zhimingzhou018-star.github.io/aram-guide/`。
