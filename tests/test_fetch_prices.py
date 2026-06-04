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


def test_load_more_results_scrolls_page_before_extracting():
    class Mouse:
        def __init__(self):
            self.wheels = []

        def wheel(self, x, y):
            self.wheels.append((x, y))

    class Page:
        def __init__(self):
            self.mouse = Mouse()
            self.waits = []

        def wait_for_timeout(self, ms):
            self.waits.append(ms)

    page = Page()

    fetch_prices.load_more_results(page)

    assert page.mouse.wheels == [(0, 2500)] * 4
    assert page.waits == [800] * 4
