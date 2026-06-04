# flight-monitor

指定赴新加坡航班最低价监控，纯静态站，Cloudflare Pages 托管。

监控：SQ869 / MF851 / MF885 / CZ353 / CZ3039 × 2026-07-24 / 25 / 26。价格为人民币·含税·含燃油。

## 结构
- `index.html` 静态页面（表格 + Chart.js 折线图）
- `data/history.json` 历史价格累积；`data/latest.json` 最新快照
- `scripts/fetch_prices.py` 本机抓价；`scripts/pricedata.py` 合并去重 + 生成快照；`scripts/update.md` 云端抓价指令
- `local/` 本机每小时 launchd 触发

## 数据更新（双触发）
- **本机每小时**（电脑开机时）：launchd 调 `local/run_local.sh` → `scripts/fetch_prices.py`
- **云端每天 3 次**（兜底）：claude.ai routine 执行 `scripts/update.md`
- 两路都按 航班+日期+整点 去重合并，push 后 Cloudflare Pages 自动部署

## 部署（Cloudflare Pages）
1. 把本仓库 push 到 GitHub `flight-monitor`
2. Cloudflare Pages → 连接该仓库 → 构建命令留空、输出目录设为根 `/`
3. push 即自动部署

## Token 配置
云端 routine 与本机均需能 `git push`：配置一个仅对 `flight-monitor` 有 contents 写权限的 GitHub PAT。
- 本机：`git remote set-url origin https://<PAT>@github.com/<user>/flight-monitor.git` 或用凭证助手
- 云端 routine：在 routine 环境中配置同样的 git 凭证

## 本机 launchd 安装
```bash
cp local/com.gerry.flightmonitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.gerry.flightmonitor.plist
```
卸载：`launchctl unload ~/Library/LaunchAgents/com.gerry.flightmonitor.plist`

## 本地测试
```bash
python3 -m venv .venv && .venv/bin/pip install pytest
.venv/bin/pytest tests/ -v
python3 -m http.server 8000   # 浏览器开 http://localhost:8000
```
