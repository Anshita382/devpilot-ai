"""A small product catalog + search API.

This is an intentionally simple but realistic FastAPI service used as a target
repository for DevPilot AI agent runs (e.g. "add Redis caching to product
search", "add input validation", "add a health check endpoint").
"""
from __future__ import annotations

from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Sample Product API", version="0.1.0")


@dataclass
class Product:
    id: int
    name: str
    category: str
    price: float
    tags: list[str] = field(default_factory=list)


_PRODUCTS: list[Product] = [
    Product(1, "Mechanical Keyboard", "peripherals", 89.99, ["rgb", "wired"]),
    Product(2, "Wireless Mouse", "peripherals", 39.50, ["wireless", "ergonomic"]),
    Product(3, "USB-C Hub", "accessories", 24.00, ["usb-c", "hub"]),
    Product(4, "27in Monitor", "displays", 219.00, ["4k", "ips"]),
    Product(5, "Laptop Stand", "accessories", 32.75, ["aluminium"]),
]


def search_products(query: str, category: str | None = None) -> list[Product]:
    """Return products whose name/tags match the query (case-insensitive)."""
    q = query.lower().strip()
    results = []
    for p in _PRODUCTS:
        haystack = " ".join([p.name, p.category, *p.tags]).lower()
        if q in haystack and (category is None or p.category == category):
            results.append(p)
    return results


@app.get("/products")
def list_products():
    return [p.__dict__ for p in _PRODUCTS]


@app.get("/products/search")
def product_search(q: str, category: str | None = None):
    matches = search_products(q, category)
    return {"count": len(matches), "results": [p.__dict__ for p in matches]}


@app.get("/products/{product_id}")
def get_product(product_id: int):
    for p in _PRODUCTS:
        if p.id == product_id:
            return p.__dict__
    raise HTTPException(status_code=404, detail="product not found")
