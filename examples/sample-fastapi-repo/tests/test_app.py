"""Baseline tests for the sample product API.

These pass out-of-the-box so DevPilot agent runs start from a green baseline;
the agent then adds new modules + tests (e.g. caching, validation, health).
"""
from app.main import get_product, search_products


def test_search_finds_by_name():
    results = search_products("keyboard")
    assert len(results) == 1
    assert results[0].id == 1


def test_search_filters_by_category():
    results = search_products("", category="accessories")
    assert {p.id for p in results} == {3, 5}


def test_get_product_returns_dict():
    product = get_product(1)
    assert product["name"] == "Mechanical Keyboard"
