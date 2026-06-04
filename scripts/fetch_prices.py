#!/usr/bin/env python3
"""
用系统 Chrome（非 Playwright 自带 Chromium）从携程抓 XMN→SIN 含税人民币最低价。
无 GUI 弹窗，完全后台运行，适合 launchd 定时触发。
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

FLIGHTS = ["SQ869", "MF851", "MF885", "CZ3039", "CZ353"]
DATES   = ["2026-07-24", "2026-07-25", "2026-07-26"]
REPO    = Path(__file__).parent.parent
HISTORY = REPO / "data" / "history.json"
LATEST  = REPO / "data" / "latest.json"
TMP     = Path("/tmp/new_prices.json")

# 航班号 → 已知起飞时间（用于辅助匹配）
FLIGHT_DEP = {
    "SQ869": ["13:40"],
    "MF851": ["09:30", "10:55"],
    "MF885": ["17:55", "18:00", "21:30"],
    "CZ353": ["08:20"],
    "CZ3039": ["12:45"],
}

FLIGHT_ROUTES = {
    "SQ869": "xmn-sin",
    "MF851": "xmn-sin",
    "MF885": "xmn-sin",
    "CZ353": "can-sin",
    "CZ3039": "can-sin",
}


def now_cst() -> str:
    return datetime.now(tz=timezone(timedelta(hours=8))).strftime("%Y-%m-%dT%H:%M:%S+08:00")


def parse_price(text: str) -> int | None:
    """从 '¥1,257' 或 '1257元' 等格式提取整数。"""
    m = re.search(r'[\d,]{4,}', text.replace("￥", "").replace("¥", ""))
    if m:
        v = int(m.group().replace(",", ""))
        return v if 500 < v < 50000 else None
    return None


def group_flights_by_route(flights: list[str]) -> dict[str, list[str]]:
    groups = {}
    for flight in flights:
        route = FLIGHT_ROUTES[flight]
        groups.setdefault(route, []).append(flight)
    return groups


def search_date(page, date: str, route: str, flights: list[str]) -> list[dict]:
    """抓单日、单航线目标航班的含税价。"""
    url = (f"https://flights.ctrip.com/international/search/oneway/{route}"
           f"?depdate={date}&cabin=y&adult=1")
    page.goto(url, wait_until="domcontentloaded", timeout=40000)
    page.wait_for_timeout(5000)

    # 等待航班列表出现
    try:
        page.wait_for_selector("[class*='flight-item'], [class*='FlightItem'], .result-item", timeout=10000)
        page.wait_for_timeout(2000)
    except Exception:
        page.wait_for_timeout(3000)

    # 携程航班行的 class 是 flight-item，价格格式是 ¥XXXX起
    result = page.evaluate(r"""
        (flights) => {
            const results = {};
            // 找所有航班行容器（直接匹配携程结构）
            const items = document.querySelectorAll(
                '.flight-item, .flight-box, [class*="flight-item"]'
            );
            for (const item of items) {
                const txt = item.innerText || '';
                for (const fn of flights) {
                    if (!txt.includes(fn)) continue;
                    // 携程价格格式：¥1,257起 或 ¥1257起
                    const m = txt.match(/[¥￥]([\d,]+)起/);
                    if (m) {
                        const price = parseInt(m[1].replace(/,/g, ''));
                        if (price > 500 && price < 50000) {
                            if (!(fn in results) || price < results[fn]) {
                                results[fn] = price;
                            }
                        }
                    }
                }
            }
            return results;
        }
    """, flights)

    ts = now_cst()
    records = []
    for flight, price in result.items():
        if price:
            records.append({
                "flight": flight,
                "depart_date": date,
                "ts": ts,
                "price_cny": price,
                "source": "携程",
            })
    return records


def fetch_all() -> list[dict]:
    all_records = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        ctx = browser.new_context(
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            viewport={"width": 1400, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            extra_http_headers={"Accept-Language": "zh-CN,zh;q=0.9"},
        )
        page = ctx.new_page()
        Stealth().apply_stealth_sync(page)

        route_groups = group_flights_by_route(FLIGHTS)
        for date in DATES:
            print(f"\n--- {date} ---", flush=True)
            for route, flights in route_groups.items():
                print(f"  route {route}", flush=True)
                try:
                    records = search_date(page, date, route, flights)
                    for r in records:
                        print(f"    {r['flight']} ¥{r['price_cny']:,}", flush=True)
                        all_records.append(r)
                    missing = [f for f in flights if not any(r["flight"] == f for r in records)]
                    for f in missing:
                        print(f"    {f} skipped (not found)", flush=True)
                except Exception as e:
                    print(f"    ERROR: {e}", flush=True)

        ctx.close()
        browser.close()
    return all_records


def main():
    print(f"[{now_cst()}] 开始抓价 ...", flush=True)
    records = fetch_all()
    print(f"\n抓到 {len(records)} 条记录", flush=True)

    if not records:
        print("全部失败，不写入数据。", flush=True)
        sys.exit(0)

    TMP.write_text(json.dumps(records, ensure_ascii=False, indent=2))

    subprocess.run(
        [sys.executable, str(REPO / "scripts" / "pricedata.py"),
         str(HISTORY), str(LATEST), str(TMP)],
        check=True
    )

    subprocess.run(["git", "-C", str(REPO), "add", "data/"], check=True)
    subprocess.run(
        ["git", "-C", str(REPO), "commit", "-m",
         f"data: update prices {now_cst()[:16]}"],
        check=True
    )
    subprocess.run(["git", "-C", str(REPO), "push"], check=True)
    print("已 push 到 GitHub。", flush=True)


if __name__ == "__main__":
    main()
