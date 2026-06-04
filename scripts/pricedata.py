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
