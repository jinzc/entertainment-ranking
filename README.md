# 🎭 文娱热榜聚合

每小时自动抓取全网文娱榜单数据，聚合展示在 GitHub Pages。

## 📊 数据来源

| 平台 | 榜单 | 状态 |
|------|------|------|
| 🔥 微博 | 文娱榜 | 自动抓取 |
| 🎵 抖音 | 娱乐榜 / 明星榜 | 自动抓取 |
| 🔍 百度 | 电影榜 / 电视剧榜 | 自动抓取 |
| 📺 哔哩哔哩 | 影视榜 / 娱乐榜 | 自动抓取 |
| 🎬 豆瓣 | 新片榜 / 正在上映 / 热门剧集 | 自动抓取 |

## 🚀 部署步骤（5分钟完成）

### 1. 创建 GitHub 仓库
- 登录 [GitHub](https://github.com)
- 点击右上角 **+** → **New repository**
- 仓库名填写 `entertainment-ranking`（或其他名称）
- 选择 **Public**（公开仓库才能使用免费 GitHub Pages）
- 点击 **Create repository**

### 2. 上传文件
将本压缩包内的所有文件上传到仓库根目录：
```
entertainment-ranking/
├── .github/
│   └── workflows/
│       └── update.yml
├── scripts/
│   └── fetch_entertainment.py
├── data/
│   └── (空文件夹，首次运行后自动生成数据)
├── index.html
└── README.md
```

上传方式：
- **方式A**：网页上传 → 进入仓库 → Add file → Upload files → 拖拽所有文件
- **方式B**：命令行（需安装Git）
  ```bash
  git clone https://github.com/你的用户名/entertainment-ranking.git
  cd entertainment-ranking
  # 复制文件到此处
  git add .
  git commit -m "init"
  git push
  ```

### 3. 开启 GitHub Pages
1. 进入仓库 → 点击 **Settings**（设置）
2. 左侧菜单选择 **Pages**
3. **Source** 选择 `Deploy from a branch`
4. **Branch** 选择 `main`（或 `master`），文件夹选 `/(root)`
5. 点击 **Save**
6. 等待 1-2 分钟，访问显示的链接（如 `https://你的用户名.github.io/entertainment-ranking/`）

### 4. 开启 Actions 自动更新
1. 进入仓库 → 点击顶部 **Actions**
2. 如果看到提示 "Workflows aren't being run on this repository"，点击 **I understand my workflows, go ahead and enable them**
3. 点击左侧 **Update Entertainment Ranking**
4. 点击右侧 **Run workflow** → **Run workflow**（立即手动运行一次）
5. 等待运行完成（约 1-2 分钟）

### 5. 验证数据
- 运行完成后，进入仓库主页，确认 `data/entertainment_data.json` 文件已生成
- 刷新你的 GitHub Pages 链接，即可看到榜单数据

## ⏰ 更新机制

- **自动更新**：每小时整点运行（基于 UTC 时间，北京时间约每小时）
- **手动更新**：进入 Actions → Update Entertainment Ranking → Run workflow
- **失败处理**：抓取失败时该榜单显示为空，不会保留旧数据

## ⚠️ 常见问题

**Q: 页面打开后没有数据？**
A: 首次部署后需要等待 Actions 执行一次（或手动触发），生成 `data/entertainment_data.json` 后才有数据。

**Q: 某些榜单显示"抓取失败"？**
A: tophub.today 可能有反爬机制或临时维护。脚本会自动重试，如持续失败请检查 Actions 日志。

**Q: 如何修改更新频率？**
A: 编辑 `.github/workflows/update.yml` 中的 `cron` 表达式：
- `'0 * * * *'` = 每小时
- `'0 */2 * * *'` = 每2小时
- `'0 7-23 * * *'` = 每天7点到23点每小时

**Q: 如何添加/删除榜单？**
A: 编辑 `scripts/fetch_entertainment.py` 中的 `SOURCES` 字典，添加或删除对应的 hashid 即可。

## 📁 文件说明

| 文件 | 作用 |
|------|------|
| `.github/workflows/update.yml` | GitHub Actions 定时任务配置 |
| `scripts/fetch_entertainment.py` | Python 数据抓取脚本 |
| `index.html` | 前端展示页面（自动读取 data 目录下的 JSON） |
| `data/entertainment_data.json` | 生成的榜单数据（Actions 自动提交） |

## 🔒 免责声明

本项目仅抓取公开可访问的热榜数据，仅供个人学习研究使用。数据版权归原平台所有。
