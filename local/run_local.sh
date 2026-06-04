#!/bin/bash
# 本机每小时入口：进入仓库，用 claude -p 无头执行抓价指令
set -euo pipefail
REPO="/Users/keyipeng/Dev/ticketmonitor"
cd "$REPO"
LOG="/tmp/flightmonitor_local.log"
# launchd 的 PATH 很精简，补上常用路径供 git / node 等使用
export PATH="/Users/keyipeng/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
CLAUDE="/Users/keyipeng/.local/bin/claude"
echo "=== $(date) start ===" >> "$LOG"
"$CLAUDE" -p "请严格按 scripts/update.md 的步骤执行：抓取这 9 个航班×日期组合的当前含税人民币最低价，合并写入数据文件并 git push。" \
  --permission-mode acceptEdits >> "$LOG" 2>&1
echo "=== $(date) done ===" >> "$LOG"
