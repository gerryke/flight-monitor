# 抓价并更新数据（云端 routine 与本机 claude -p 共用）

工作目录为本仓库根。按以下步骤执行：

## 1. 抓取价格

对下列 15 个「航班号 × 出发日期」组合，逐个查当前最低价：

- XMN → SIN 航班号：SQ869、MF851、MF885
- CAN → SIN 航班号：CZ353、CZ3039
- 出发日期：2026-07-24、2026-07-25、2026-07-26
- 航线：按上述航班对应航线查询

抓取方法（按优先级）：
1. 打开 **Google Flights**（`https://www.google.com/travel/flights`），货币设为 **CNY 人民币**，
   选对应航线与出发日期，在结果里找到对应**航班号**那一班，读取其**含税总价**（人民币）。
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
- 15 个全部失败 → 不 commit，记录日志即可。
