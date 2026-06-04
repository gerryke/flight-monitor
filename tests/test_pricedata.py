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
