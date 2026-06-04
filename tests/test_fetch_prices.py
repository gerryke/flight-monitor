import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fetch_prices


def test_groups_target_flights_by_route():
    groups = fetch_prices.group_flights_by_route(["SQ869", "CZ353", "MF885", "CZ3039"])

    assert groups == {
        "xmn-sin": ["SQ869", "MF885"],
        "can-sin": ["CZ353", "CZ3039"],
    }
