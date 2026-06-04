# 厦门→新加坡 航班最低价监控网站 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建一个静态网站，展示 XMN→SIN 三个指定航班（SQ869/MF851/MF885）在 2026-07-24/25/26 三个出发日的当前最低含税人民币价，并用 Chart.js 折线图展示历史价格；由本机每小时 + 云端每天 3 次两路触发抓价。

**Architecture:** 单一抓价指令（`scripts/update.md`，给 Claude agent 执行）被两路触发——本机 launchd 每小时调 `claude -p`、云端 claude.ai routine 每天 3 次。抓到的价格经 `scripts/pricedata.py` 去重合并后写入 `data/history.json` 与 `data/latest.json`，git push 到 GitHub `flight-monitor` 仓库，Cloudflare Pages 自动部署纯静态 `index.html`。

**Tech Stack:** Python 3（去重/快照脚本 + pytest）、纯静态 HTML + Chart.js（CDN）、launchd、Claude Code 无头模式 `claude -p`、claude.ai routine、GitHub + Cloudflare Pages。

> **关于 commit：** 用户有长期偏好「不要主动 git add/commit，除非明确要求」。本计划各任务末尾的 commit 步骤为**建议态**——执行时先 `git add` 暂存，**commit 前征求用户确认**，不自动提交。

---

## File Structure

```
index.html                              单页静态网站（表格 + Chart.js 折线图）
data/history.json                       历史价格累积数组（去重）
data/latest.json                        最新快照（页面顶部当前最低价）
scripts/pricedata.py                    合并去重 + 生成 latest 的核心逻辑 + CLI
scripts/update.md                       抓价 + 调脚本 + push 的 agent 指令
tests/test_pricedata.py                 pricedata 的单元测试
local/run_local.sh                      本机入口：cd 仓库 + claude -p 执行 update.md
local/com.gerry.flightmonitor.plist     本机 launchd 配置（每小时）
README.md                               部署 / Cloudflare / token 说明
```

---

## Task 1: 仓库脚手架

**Files:**
- Create: `/Users/keyipeng/Dev/ticketmonitor/.gitignore`
- Create: `data/history.json`
- Create: `data/latest.json`

- [ ] **Step 1: 初始化独立 git 仓库**

仓库目录已是 `/Users/keyipeng/Dev/ticketmonitor`。它嵌在 Dev/ 大仓库内（沿用 Piece Moment 模式），需作为独立 git 仓库初始化。

Run:
```bash
cd /Users/keyipeng/Dev/ticketmonitor && git init -b main && git status
```
Expected: `Initialized empty Git repository`，status 显示已存在的 `docs/` 为 untracked。

- [ ] **Step 2: 写 `.gitignore`**

```
.DS_Store
__pycache__/
*.pyc
.pytest_cache/
local/.env
```

- [ ] **Step 3: 建空数据文件**

`data/history.json`:
```json
[]
```

`data/latest.json`:
```json
{ "updated_at": null, "prices": [] }
```

- [ ] **Step 4: 暂存（commit 前问用户）**

```bash
git add .gitignore data/ docs/
```
Expected: 无报错。Commit 留待用户确认。

---

## Task 2: 价格合并去重核心逻辑（TDD）

**Files:**
- Test: `tests/test_pricedata.py`
- Create: `scripts/pricedata.py`

去重键 = `flight` + `depart_date` + `ts` 的整点小时；同键保留 `ts` 最新的一条。`build_latest` 为每个 `flight+depart_date` 取最近一条，`updated_at` 取全局最大 `ts`。

- [ ] **Step 1: 写失败的测试**

`tests/test_pricedata.py`:
```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import pricedata


def rec(flight, date, ts, price, source="Google Flights"):
    return {"flight": flight, "depart_date": date, "ts": ts,
            "price_cny": price, "source": source}


def test_merge_into_empty():
    new = [rec("SQ869", "2026-07-25", "2026-07-20T09:00:00+08:00", 2380)]
    assert pricedata.merge([], new) == new


def test_merge_dedupes_same_hour_keeps_latest():
    a = rec("SQ869", "2026-07-25", "2026-07-20T09:05:00+08:00", 2380)
    b = rec("SQ869", "2026-07-25", "2026-07-20T09:45:00+08:00", 2310)
    out = pricedata.merge([a], [b])
    assert len(out) == 1
    assert out[0]["price_cny"] == 2310


def test_merge_keeps_different_hours():
    a = rec("SQ869", "2026-07-25", "2026-07-20T09:00:00+08:00", 2380)
    b = rec("SQ869", "2026-07-25", "2026-07-20T10:00:00+08:00", 2400)
    out = pricedata.merge([a], [b])
    assert len(out) == 2


def test_merge_keeps_different_flights_and_dates():
    a = rec("SQ869", "2026-07-25", "2026-07-20T09:00:00+08:00", 2380)
    b = rec("MF851", "2026-07-25", "2026-07-20T09:00:00+08:00", 1980)
    c = rec("SQ869", "2026-07-26", "2026-07-20T09:00:00+08:00", 2500)
    out = pricedata.merge([], [a, b, c])
    assert len(out) == 3


def test_build_latest_picks_most_recent_per_combo():
    h = [
        rec("SQ869", "2026-07-25", "2026-07-20T09:00:00+08:00", 2380),
        rec("SQ869", "2026-07-25", "2026-07-20T10:00:00+08:00", 2310),
        rec("MF851", "2026-07-25", "2026-07-20T10:00:00+08:00", 1980),
    ]
    latest = pricedata.build_latest(h)
    assert latest["updated_at"] == "2026-07-20T10:00:00+08:00"
    sq = [p for p in latest["prices"] if p["flight"] == "SQ869"][0]
    assert sq["price_cny"] == 2310
    assert len(latest["prices"]) == 2


def test_build_latest_empty():
    latest = pricedata.build_latest([])
    assert latest == {"updated_at": None, "prices": []}
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd /Users/keyipeng/Dev/ticketmonitor && python3 -m pytest tests/test_pricedata.py -v`
Expected: FAIL（`ModuleNotFoundError: No module named 'pricedata'`）。

- [ ] **Step 3: 写最小实现**

`scripts/pricedata.py`:
```python
"""航班价格历史的合并去重与快照生成。"""
import json
import sys
from datetime import datetime


def _hour_key(r):
    dt = datetime.fromisoformat(r["ts"])
    return (r["flight"], r["depart_date"], dt.strftime("%Y-%m-%dT%H"))


def merge(existing, new):
    """按 航班+日期+整点小时 去重，同键保留 ts 最新的一条。"""
    by_key = {}
    for r in list(existing) + list(new):
        k = _hour_key(r)
        if k not in by_key or r["ts"] >= by_key[k]["ts"]:
            by_key[k] = r
    return sorted(by_key.values(),
                  key=lambda r: (r["depart_date"], r["flight"], r["ts"]))


def build_latest(history):
    """每个 航班+日期 取最近一条，updated_at 取全局最大 ts。"""
    if not history:
        return {"updated_at": None, "prices": []}
    best = {}
    for r in history:
        k = (r["flight"], r["depart_date"])
        if k not in best or r["ts"] >= best[k]["ts"]:
            best[k] = r
    prices = [
        {"flight": r["flight"], "depart_date": r["depart_date"],
         "price_cny": r["price_cny"], "source": r["source"]}
        for r in sorted(best.values(),
                        key=lambda r: (r["depart_date"], r["flight"]))
    ]
    updated_at = max(r["ts"] for r in history)
    return {"updated_at": updated_at, "prices": prices}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dump(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def main(argv):
    """用法: pricedata.py <history.json> <latest.json> <new_records.json>
    读 history，合并 new_records，写回 history 和 latest。"""
    history_path, latest_path, new_path = argv[1], argv[2], argv[3]
    history = _load(history_path)
    new = _load(new_path)
    merged = merge(history, new)
    _dump(history_path, merged)
    _dump(latest_path, build_latest(merged))
    print(f"merged {len(new)} new -> {len(merged)} total")


if __name__ == "__main__":
    main(sys.argv)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/keyipeng/Dev/ticketmonitor && python3 -m pytest tests/test_pricedata.py -v`
Expected: 6 passed。

- [ ] **Step 5: 暂存（commit 前问用户）**

```bash
git add scripts/pricedata.py tests/test_pricedata.py
```

---

## Task 3: 静态网站页面

**Files:**
- Create: `index.html`

页面 `fetch('data/latest.json')` 和 `fetch('data/history.json')`，渲染当前最低价表格 + Chart.js 折线图（按航班分线，下拉切换出发日期）。

- [ ] **Step 1: 写 `index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>厦门 → 新加坡 航班最低价监控</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root { --bg:#0f1220; --card:#1a1f35; --fg:#e8ecf5; --muted:#8b93ad; --accent:#5b8cff; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",Segoe UI,sans-serif;
         background:var(--bg); color:var(--fg); padding:24px; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:var(--muted); font-size:13px; margin-bottom:20px; }
  .card { background:var(--card); border-radius:12px; padding:18px; margin-bottom:20px; }
  table { width:100%; border-collapse:collapse; }
  th,td { padding:10px 12px; text-align:center; border-bottom:1px solid #2a3050; }
  th { color:var(--muted); font-weight:500; font-size:13px; }
  td.price { font-variant-numeric:tabular-nums; font-weight:600; }
  td.na { color:var(--muted); }
  .controls { margin-bottom:12px; }
  select { background:var(--card); color:var(--fg); border:1px solid #2a3050;
           border-radius:8px; padding:6px 10px; font-size:14px; }
  .updated { color:var(--muted); font-size:12px; margin-top:8px; }
  canvas { max-height:380px; }
</style>
</head>
<body>
  <h1>厦门 (XMN) → 新加坡 (SIN) 航班最低价监控</h1>
  <div class="sub">价格为人民币、含税、含燃油附加费 · 监控航班 SQ869 / MF851 / MF885</div>

  <div class="card">
    <table id="latest-table">
      <thead>
        <tr><th>航班</th><th>7-24</th><th>7-25</th><th>7-26</th></tr>
      </thead>
      <tbody></tbody>
    </table>
    <div class="updated" id="updated"></div>
  </div>

  <div class="card">
    <div class="controls">
      出发日期：
      <select id="date-select">
        <option value="2026-07-24">7 月 24 日</option>
        <option value="2026-07-25" selected>7 月 25 日</option>
        <option value="2026-07-26">7 月 26 日</option>
      </select>
    </div>
    <canvas id="chart"></canvas>
  </div>

<script>
const FLIGHTS = ["SQ869", "MF851", "MF885"];
const DATES = ["2026-07-24", "2026-07-25", "2026-07-26"];
const COLORS = { SQ869:"#5b8cff", MF851:"#ff7a5b", MF885:"#3ddc97" };
let HISTORY = [];
let chart = null;

async function loadJSON(path) {
  const r = await fetch(path + "?t=" + Date.now());
  if (!r.ok) throw new Error(path + " " + r.status);
  return r.json();
}

function renderLatest(latest) {
  const tbody = document.querySelector("#latest-table tbody");
  tbody.innerHTML = "";
  for (const flight of FLIGHTS) {
    const tr = document.createElement("tr");
    let cells = `<td>${flight}</td>`;
    for (const d of DATES) {
      const p = (latest.prices || []).find(x => x.flight === flight && x.depart_date === d);
      cells += p ? `<td class="price">¥${p.price_cny.toLocaleString()}</td>`
                 : `<td class="na">—</td>`;
    }
    tr.innerHTML = cells;
    tbody.appendChild(tr);
  }
  document.getElementById("updated").textContent =
    latest.updated_at ? "最近更新：" + new Date(latest.updated_at).toLocaleString("zh-CN")
                      : "暂无数据";
}

function renderChart(date) {
  const datasets = FLIGHTS.map(flight => {
    const points = HISTORY
      .filter(r => r.flight === flight && r.depart_date === date)
      .sort((a, b) => a.ts.localeCompare(b.ts))
      .map(r => ({ x: r.ts, y: r.price_cny }));
    return { label: flight, data: points, borderColor: COLORS[flight],
             backgroundColor: COLORS[flight], tension: 0.25, spanGaps: true };
  });
  if (chart) chart.destroy();
  chart = new Chart(document.getElementById("chart"), {
    type: "line",
    data: { datasets },
    options: {
      parsing: false,
      scales: {
        x: { type: "time", time: { unit: "hour" },
             ticks: { color: "#8b93ad" }, grid: { color: "#2a3050" } },
        y: { ticks: { color: "#8b93ad", callback: v => "¥" + v },
             grid: { color: "#2a3050" } }
      },
      plugins: { legend: { labels: { color: "#e8ecf5" } } }
    }
  });
}

async function init() {
  const [latest, history] = await Promise.all([
    loadJSON("data/latest.json"), loadJSON("data/history.json")
  ]);
  HISTORY = history;
  renderLatest(latest);
  const sel = document.getElementById("date-select");
  sel.addEventListener("change", () => renderChart(sel.value));
  renderChart(sel.value);
}
init().catch(e => { document.body.insertAdjacentHTML("beforeend",
  `<div class="card">加载失败：${e.message}</div>`); });
</script>
</body>
</html>
```

> 注：Chart.js time 轴需要 date 适配器。在 `<head>` 的 chart.js 之后追加一行 CDN：
> `<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>`

- [ ] **Step 2: 补上 date 适配器脚本标签**

在 `index.html` 的 `chart.umd.min.js` 那行之后插入：
```html
<script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns@3.0.0/dist/chartjs-adapter-date-fns.bundle.min.js"></script>
```

- [ ] **Step 3: 灌入样例数据本地验证**

临时往 `data/history.json` 写两条样例 + 用脚本生成 latest：
```bash
cd /Users/keyipeng/Dev/ticketmonitor
cat > /tmp/seed.json <<'EOF'
[
 {"flight":"SQ869","depart_date":"2026-07-25","ts":"2026-07-20T09:00:00+08:00","price_cny":2380,"source":"Google Flights"},
 {"flight":"SQ869","depart_date":"2026-07-25","ts":"2026-07-20T10:00:00+08:00","price_cny":2310,"source":"Google Flights"},
 {"flight":"MF851","depart_date":"2026-07-25","ts":"2026-07-20T10:00:00+08:00","price_cny":1980,"source":"Google Flights"}
]
EOF
echo "[]" > data/history.json
python3 scripts/pricedata.py data/history.json data/latest.json /tmp/seed.json
python3 -m http.server 8000 >/tmp/serve.log 2>&1 &
```
浏览器打开 `http://localhost:8000/` 确认：表格显示 SQ869/MF851 在 7-25 有价、其余 `—`；折线图 7-25 有 SQ869 两点。验证后停掉 server 并把 `data/history.json` 还原为 `[]`、重生成 latest（`echo "[]" > data/history.json && python3 scripts/pricedata.py data/history.json data/latest.json /tmp/empty.json`，其中 `/tmp/empty.json` 内容为 `[]`）。

- [ ] **Step 4: 暂存（commit 前问用户）**

```bash
git add index.html data/
```

---

## Task 4: 抓价指令 `scripts/update.md`

**Files:**
- Create: `scripts/update.md`

- [ ] **Step 1: 写 `scripts/update.md`**

````markdown
# 抓价并更新数据（云端 routine 与本机 claude -p 共用）

工作目录为本仓库根。按以下步骤执行：

## 1. 抓取价格

对下列 9 个「航班号 × 出发日期」组合，逐个查当前最低价：

- 航班号：SQ869、MF851、MF885
- 出发日期：2026-07-24、2026-07-25、2026-07-26
- 航线：厦门 XMN → 新加坡 SIN

抓取方法（按优先级）：
1. 打开 **Google Flights**（`https://www.google.com/travel/flights`），货币设为 **CNY 人民币**，
   航线 XMN→SIN，选对应出发日期，在结果里找到对应**航班号**那一班，读取其**含税总价**（人民币）。
2. 若 Google Flights 抓不到该航班号，退回 **携程**（flights.ctrip.com）或 **飞猪**，同样取**含税人民币总价**。
3. 该组合彻底抓不到 → **跳过，不要编造价格**。

价格口径：人民币、含税、含燃油附加费、单程经济舱最低价。

## 2. 组装新记录

把抓到的组合写成 JSON 数组存到 `/tmp/new_prices.json`，每条：
```json
{ "flight": "SQ869", "depart_date": "2026-07-25",
  "ts": "<当前北京时间 ISO8601，如 2026-07-20T14:00:00+08:00>",
  "price_cny": 2380, "source": "Google Flights" }
```
`ts` 用当前北京时间（+08:00）。只包含抓到的组合。

## 3. 合并写入

```bash
python3 scripts/pricedata.py data/history.json data/latest.json /tmp/new_prices.json
```

## 4. 提交推送

```bash
git add data/
git commit -m "data: update flight prices $(date +%F\ %H:%M)"
git push
```

## 失败处理
- 任何组合抓不到就跳过；只要至少抓到 1 条就照常写入并 push。
- 9 个全部失败 → 不 commit，记录日志即可。
````

- [ ] **Step 2: 暂存（commit 前问用户）**

```bash
git add scripts/update.md
```

---

## Task 5: 本机每小时触发

**Files:**
- Create: `local/run_local.sh`
- Create: `local/com.gerry.flightmonitor.plist`

- [ ] **Step 1: 写 `local/run_local.sh`**

```bash
#!/bin/bash
# 本机每小时入口：进入仓库，用 claude -p 无头执行抓价指令
set -euo pipefail
REPO="/Users/keyipeng/Dev/ticketmonitor"
cd "$REPO"
LOG="/tmp/flightmonitor_local.log"
echo "=== $(date) start ===" >> "$LOG"
/usr/bin/env claude -p "请严格按 scripts/update.md 的步骤执行：抓取这 9 个航班×日期组合的当前含税人民币最低价，合并写入数据文件并 git push。" \
  --permission-mode acceptEdits >> "$LOG" 2>&1
echo "=== $(date) done ===" >> "$LOG"
```

> 注：`claude` 可执行文件路径若不在 PATH，需在脚本里写绝对路径（用 `which claude` 查）。`--permission-mode` 参数名以本机 `claude --help` 为准，若不支持则去掉。

- [ ] **Step 2: 赋可执行权限**

Run: `chmod +x /Users/keyipeng/Dev/ticketmonitor/local/run_local.sh`

- [ ] **Step 3: 写 launchd plist**

`local/com.gerry.flightmonitor.plist`:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.gerry.flightmonitor</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/keyipeng/Dev/ticketmonitor/local/run_local.sh</string>
  </array>
  <key>StartInterval</key>
  <integer>3600</integer>
  <key>StandardOutPath</key>
  <string>/tmp/flightmonitor_launchd.out</string>
  <key>StandardErrorPath</key>
  <string>/tmp/flightmonitor_launchd.err</string>
</dict>
</plist>
```

- [ ] **Step 4: 暂存（commit 前问用户）。安装 launchd 由用户决定**

```bash
git add local/
```
安装命令（执行时询问用户是否现在装）：
```bash
cp local/com.gerry.flightmonitor.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.gerry.flightmonitor.plist
```

---

## Task 6: README 与部署说明

**Files:**
- Create: `README.md`

- [ ] **Step 1: 写 `README.md`**

````markdown
# flight-monitor

厦门 (XMN) → 新加坡 (SIN) 指定航班最低价监控，纯静态站，Cloudflare Pages 托管。

监控：SQ869 / MF851 / MF885 × 2026-07-24 / 25 / 26。价格为人民币·含税·含燃油。

## 结构
- `index.html` 静态页面（表格 + Chart.js 折线图）
- `data/history.json` 历史价格累积；`data/latest.json` 最新快照
- `scripts/pricedata.py` 合并去重 + 生成快照；`scripts/update.md` 抓价指令
- `local/` 本机每小时 launchd 触发

## 数据更新（双触发）
- **本机每小时**（电脑开机时）：launchd 调 `local/run_local.sh` → `claude -p` 执行 `scripts/update.md`
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
python3 -m pytest tests/ -v
python3 -m http.server 8000   # 浏览器开 http://localhost:8000
```
````

- [ ] **Step 2: 暂存（commit 前问用户）**

```bash
git add README.md
```

---

## Task 7: 云端 routine + GitHub 仓库（执行期手动协作）

这些步骤需用户参与，不在自动化代码范围内，执行时逐项确认。

- [ ] **Step 1: 创建 GitHub 仓库并 push**

执行时：用 `gh repo create flight-monitor --private --source=. --remote=origin` 或请用户在 GitHub 网页建仓后给出 remote URL，然后 `git push -u origin main`（commit 已经用户确认后）。

- [ ] **Step 2: 配置 git push 用的 GitHub PAT**

请用户提供一个对 `flight-monitor` 有写权限的 PAT，配置到本机 remote。

- [ ] **Step 3: 用 /schedule 列出并复用云端 routine**

用 `/schedule` 技能 list 现有 routine，拿到那个「3 次/天」任务的 3 个触发时间；列不出则请用户提供。然后新建一个专门 routine（不污染原任务），prompt 为「按 flight-monitor 仓库的 scripts/update.md 执行抓价并 push」，cron 设为相同 3 个时间。

- [ ] **Step 4: Cloudflare Pages 连接**

请用户在 Cloudflare Pages 连接 GitHub `flight-monitor` 仓库（构建命令空、输出目录 `/`）。

---

## Self-Review 备注

- **Spec 覆盖**：架构(Task 1-6)、数据格式(Task 1,2)、抓价逻辑(Task 4)、页面(Task 3)、本机触发(Task 5)、云端触发(Task 7)、凭证(Task 6,7)、风险兜底(update.md 跳过策略 + latest updated_at) 均有对应任务。
- **去重一致性**：`merge` 用 `flight+depart_date+ts整点小时` 去重；`build_latest` 用 `flight+depart_date` 取最近——与 spec 第 2、4 节一致。
- **commit 偏好**：所有 commit 步骤标注为「暂存 + 问用户」，遵循用户长期偏好。
````
