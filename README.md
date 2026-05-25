# 🎭 文娱热榜聚合（改进版）

每小时自动抓取全网文娱榜单数据，采用**双源自动切换**策略，确保数据真实可靠。

## 🔄 双源抓取策略

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1️⃣ | tophub.today | 优先尝试聚合站抓取 |
| 2️⃣ | 原始平台直连 | tophub 返回假数据时自动切换 |

**自动检测机制**：脚本会自动识别 tophub 返回的虚假数据（如"报刊、设计、校务"等导航占位内容），一旦检测到立即切换到对应平台的官方数据源。

## 📊 数据来源

| 平台 | 榜单 | 主源 | 备用源 |
|------|------|------|--------|
| 🔥 微博 | 文娱榜 | tophub | 微博官方热搜 |
| 🎵 抖音 | 娱乐榜 / 明星榜 | tophub | 抖音网页热榜 |
| 🔍 百度 | 电影榜 / 电视剧榜 | tophub | 百度热搜API |
| 📺 哔哩哔哩 | 影视榜 / 娱乐榜 | tophub | B站热搜API |
| 🎬 豆瓣 | 新片榜 / 正在上映 / 热门剧集 | tophub | 豆瓣官方页面 |

## 🚀 部署步骤

### 1. 创建 GitHub 仓库
- 登录 [GitHub](https://github.com)
- 新建仓库 `entertainment-ranking`，选择 **Public**

### 2. 上传文件
将压缩包内所有文件上传到仓库根目录，保持目录结构：
```
entertainment-ranking/
├── .github/workflows/update.yml
├── scripts/fetch_entertainment.py
├── data/
│   └── .gitkeep
├── index.html
└── README.md
```

### 3. 开启 GitHub Pages
- 仓库 → **Settings** → **Pages**
- Source: `Deploy from a branch` → Branch: `main` → Folder: `/(root)`
- 保存后等待 1-2 分钟，获取访问链接

### 4. 开启 Actions 自动更新
- 仓库 → **Actions** → 点击启用 Workflows
- 左侧选择 **Update Entertainment Ranking**
- 右侧点击 **Run workflow** → **Run workflow**（立即手动运行一次）
- 等待运行完成，确认 `data/entertainment_data.json` 已生成

### 5. 查看效果
- 打开 GitHub Pages 链接查看榜单
- 每个卡片右上角会显示数据来源：`tophub` 或 `直连`

## ⏰ 更新机制

- **自动更新**：每小时整点运行（UTC）
- **手动更新**：Actions 页面点击 Run workflow
- **失败处理**：双源均失败时显示错误信息，不会展示虚假旧数据
- **假数据识别**：自动过滤"报刊、设计、校务"等导航占位内容

## ⚠️ 常见问题

**Q: 某些榜单显示"抓取失败"？**
A: 说明 tophub 和原始平台双源均抓取失败。可能是平台临时维护或反爬升级。下一小时会自动重试。

**Q: 为什么有些榜单显示"直连"而不是"tophub"？**
A: 这是正常情况。当 tophub 返回虚假数据时，脚本自动切换到原始平台直接抓取，确保你看到的是真实榜单内容。

**Q: 首次部署后页面没有数据？**
A: 必须先手动运行一次 Actions 生成 `data/entertainment_data.json`，页面才有数据展示。

**Q: 如何调整更新频率？**
A: 编辑 `.github/workflows/update.yml` 中的 `cron`：
- `'0 * * * *'` = 每小时
- `'0 */2 * * *'` = 每2小时
- `'0 7-23 * * *'` = 每天7-23点每小时

## 📁 文件说明

| 文件 | 作用 |
|------|------|
| `.github/workflows/update.yml` | GitHub Actions 定时任务 |
| `scripts/fetch_entertainment.py` | 双源抓取脚本（tophub + 原始平台 fallback） |
| `index.html` | 前端展示页面（显示数据来源标签） |
| `data/entertainment_data.json` | 生成的榜单数据（Actions 自动提交） |

## 🔒 免责声明

本项目仅抓取公开可访问的热榜数据，仅供个人学习研究使用。数据版权归原平台所有。
