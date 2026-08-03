# 海克斯大乱斗一图流站

纯静态、手机优先的英雄攻略站。数据由 `scripts/build_onepager_site_data.py` 从当前英雄数据和 Figma 工程目录生成。

本地预览：

```powershell
python tools/preview_site.py
```

该命令会先校验内嵌资源并运行完整测试，再打开 `http://127.0.0.1:8879/`。只校验、不启动服务时使用 `python tools/preview_site.py --check-only`。

## Git 验收与发布

所有网站修改都在功能分支完成。本地预览验收后，先把功能分支合并到 `main`，为验收提交创建版本标签，并把分支与标签推送 GitHub，再从干净的 `main` 执行腾讯云发布。正式部署必须显式传入用户验收的提交 SHA 和版本标签；脚本会拒绝功能分支、未提交改动、未推送提交或标签、SHA 不一致的发布。

```powershell
git tag -a release-YYYYMMDD-NN -m "Production release YYYY-MM-DD"
git push origin main release-YYYYMMDD-NN
python ../../../scripts/deploy_onepager_cos.py --config <腾讯云私有配置路径> --site-dir . --bucket-base haidou-guide-hk --region ap-hongkong --approved-commit <验收提交SHA> --release-tag release-YYYYMMDD-NN
```

`--dry-run` 只读校验不受 Git 发布门禁影响，也不会上传腾讯云。

需要回滚时，从旧标签恢复网站文件并在 `main` 创建一个新的回滚提交和版本标签，再按同一门禁发布；不改写 Git 历史。

## 漏斗统计

统计入口在 `analytics-config.js`。生产环境通过 `https://data.zhishitft.cn` 加载 PostHog SDK，并通过 `https://data.zhishitft.cn/ingest` 中转上报；浏览器不直接连接海外 PostHog。Key 为空或 `enabled` 为 `false` 时不会下载 SDK，也不会发送任何统计请求。

已记录的业务事件：

- `home_view`
- `hero_search`
- `hero_card_click`
- `guide_view`
- `return_home`

建议在 PostHog 中建立 `home_view → hero_card_click → guide_view → return_home` 漏斗，并把 `hero_search` 作为搜索用户的可选步骤或细分条件。

## 图片缓存

`sw.js` 会持久缓存用户实际加载过的英雄头像和攻略图。发布新一轮攻略时，同时提升 HTML 中的 `rev`、`app.js` 的数据版本和 `sw.js` 的 `CACHE_NAME`，浏览器便会清理旧版缓存。

正式发布路径：`https://haidou.zhishitft.cn/`。GitHub Pages `https://zhimingzhou018-star.github.io/aram-guide/` 仅作备用。
