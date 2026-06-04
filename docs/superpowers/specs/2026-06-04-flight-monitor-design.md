# 厦门→新加坡 航班最低价监控网站 — 设计文档

日期：2026-06-04
仓库名（GitHub）：`flight-monitor`
本地目录：`/Users/keyipeng/Dev/ticketmonitor`（独立 git 仓库，嵌在 Dev 下，沿用 Piece Moment 同款模式）
托管：Cloudflare Pages（连 GitHub 仓库，用户自行连接）

## 1. 目标

一个静态网站，展示 **厦门(XMN) → 新加坡(SIN)** 指定航班、指定出发日期的**当前最低价**（人民币、含税、含燃油附加费），并把历史价格累积下来用**折线图**展示。

- 监控航班号：`SQ869`、`MF851`、`MF885`
- 出发日期：**2026-07-24**、**2026-07-25**、**2026-07-26**
- 共 3 航班 × 3 日期 = 每轮最多 9 个价格点

## 2. 整体架构

```
抓价逻辑（单一来源：scripts/update.md，给 Claude agent 执行）
        │
   ┌────┴─────────────────────┐
   │                          │
本机触发                    云端触发
launchd 每小时              claude.ai routine 每天 3 次
claude -p 无头执行          （复用现有 3 次/天 routine 的时间）
（仅电脑开机时）             （始终运行，作兜底基线）
   │                          │
   └──────────┬───────────────┘
              ▼
     git push 到 flight-monitor 仓库
     （data/history.json 追加 + data/latest.json 覆盖）
              ▼
     Cloudflare Pages 自动重新部署
              ▼
     index.html 读 JSON → 表格 + Chart.js 折线图
```

**双触发的合并规则**：两边都向 `history.json` 追加，**按「航班号 + 出发日期 + 整点小时」去重**。
- 电脑关机 → 只有云端每天 3 个点。
- 电脑开机 → 本机每小时补点，曲线更密。
- 不需要"检测本机是否开机再决定是否调云端"的复杂逻辑；云端一直跑作基线，本机开机时叠加。

## 3. 仓库结构

```
index.html              单页静态网站（表格 + Chart.js 折线图，中文）
data/history.json       历史价格累积数组（agent 每轮追加，去重）
data/latest.json        最新一轮快照（页面顶部「当前最低价」直接读）
scripts/update.md       抓价 + 写入 + push 的指令（routine / claude -p 都调它）
scripts/dedupe.py       追加并按 航班+日期+整点 去重的小工具（被 update.md 调用）
local/com.gerry.flightmonitor.plist   本机 launchd 配置（每小时）
local/run_local.sh      本机入口脚本：cd 仓库 + claude -p 执行 update.md
README.md               说明（部署、Cloudflare 连接、token 配置）
docs/superpowers/specs/ 本设计文档
```

## 4. 数据格式

### `data/history.json`
```json
[
  { "ts": "2026-07-20T09:00:00+08:00",
    "flight": "SQ869",
    "depart_date": "2026-07-25",
    "price_cny": 2380,
    "source": "Google Flights" }
]
```
- `ts`：抓取时间（北京时间 ISO8601，带时区）。
- 去重键：`flight` + `depart_date` + `ts` 的整点小时（同一小时内重复抓只保留最新一条）。

### `data/latest.json`
```json
{
  "updated_at": "2026-07-20T09:00:00+08:00",
  "prices": [
    { "flight": "SQ869", "depart_date": "2026-07-25", "price_cny": 2380, "source": "Google Flights" }
  ]
}
```
页面顶部「当前最低价」表格直接读它，避免每次解析整个 history。

## 5. 抓价逻辑（scripts/update.md，agent 每轮执行）

1. 对每个「航班号 + 出发日期」组合（共 9 个）：
   - 打开 **Google Flights**，locale/货币设为中国·人民币（能直接出含税总价），筛出该航班号当天的最低价。
   - 抓不到 → 退回 **携程 / 飞猪** 兜底（同样取含税人民币总价）。
2. 读 `data/history.json` → 调 `scripts/dedupe.py` 追加这一轮记录（自动去重）。
3. 覆盖写 `data/latest.json`。
4. `git add data/ && git commit && git push`。
5. **抓失败的组合直接跳过本轮，不写假数据**；页面靠 `updated_at` 显示"最近更新时间"，让用户知道数据新鲜度。

## 6. 网站页面（index.html）

- **纯静态、零构建**，Chart.js 用 CDN 引入，Cloudflare Pages 直接托管。
- **顶部表格**：3×3，当前各航班各出发日期的最低价（人民币），并显示「最近更新时间」。
- **折线图**：
  - 横轴 = 抓取时间，纵轴 = 人民币价格。
  - 按航班号分线（3 条线：SQ869 / MF851 / MF885）。
  - 提供出发日期切换（7-24 / 7-25 / 7-26），切换后图只显示该日期的三条航班价格曲线。
- 语言：先做中文。

## 7. 定时触发

### 本机（每小时，电脑开机时）
- `local/com.gerry.flightmonitor.plist`：launchd Agent，`StartInterval` 或 `StartCalendarInterval` 每小时一次。
- 调 `local/run_local.sh` → `cd` 到仓库 → `claude -p "按 scripts/update.md 执行"` 无头运行。
- 电脑休眠/关机时自然不跑（launchd 不补跑，符合预期）。

### 云端（每天 3 次，兜底）
- 复用 claude.ai 已有的 3 次/天 routine 的时间点。
- 实施时先用 `/schedule` 技能列出现有 routine 拿到那 3 个时间；列不出来则请用户提供。
- **新建一个专门的 routine**（不污染原有任务），每次执行 `scripts/update.md` 同一套指令。

## 8. 凭证 / 权限

- 云端 routine 和本机 `claude -p` 都需要能 `git push` 到 `flight-monitor` 仓库。
- 配置一个 GitHub Personal Access Token（仅该仓库 contents 写权限），分别放入云端 routine 环境和本机 git 凭证。
- Cloudflare Pages 由用户自行连接 GitHub 仓库（push 即自动部署）。

## 9. 已知风险

- **抓价稳定性**：Google Flights JS 重、有反爬，agent 浏览仍可能偶发抓不到 → 用携程/飞猪兜底 + 跳过策略 + 「最近更新时间」兜底显示。
- **含税口径**：不同站点"含税总价"口径可能略有差异，`source` 字段记录来源便于核对。
- **token 成本**：本机每小时调一次 `claude -p` 有 token 开销（用户已接受）。
- **去重边界**：本机与云端在同一小时都跑时，按整点小时去重保留最新一条。

## 10. 范围外（YAGNI）

- 不做多语言（先中文）。
- 不做价格预警/通知（只展示）。
- 不做除这 3 航班 / 3 日期外的通用查询。
- 不做后端数据库（JSON 文件足够）。
