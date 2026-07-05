import sys
from config import DATABASE_URL, CACHE_TTL
from database import Database
from shop_tools import ShopTools
from state import ShopState, ToolTracer
from agents import run_shopping_agent, CoordinatorAgent, AgentContext, RankerAgent
import copy

# Static catalog for initial population
CATALOG = [
    {"id": "p1",  "name": "Sony WH-1000XM5",            "category": "headphones", "brand": "Sony",     "price": 349, "color": "black",    "rating": 4.8, "tags": ["wireless", "noise-cancelling", "premium"]},
    {"id": "p2",  "name": "Sony WH-CH720N",              "category": "headphones", "brand": "Sony",     "price": 129, "color": "blue",     "rating": 4.4, "tags": ["wireless", "budget", "noise-cancelling"]},
    {"id": "p3",  "name": "Bose QuietComfort Ultra",     "category": "headphones", "brand": "Bose",     "price": 379, "color": "white",    "rating": 4.7, "tags": ["wireless", "noise-cancelling", "premium"]},
    {"id": "p4",  "name": "Apple AirPods Pro 2",         "category": "earbuds",    "brand": "Apple",    "price": 249, "color": "white",    "rating": 4.6, "tags": ["wireless", "noise-cancelling", "ios"]},
    {"id": "p5",  "name": "Anker Soundcore Liberty 4 NC","category": "earbuds",    "brand": "Anker",    "price": 99,  "color": "black",    "rating": 4.3, "tags": ["wireless", "budget", "noise-cancelling"]},
    {"id": "p6",  "name": "Logitech MX Master 3S",       "category": "mouse",      "brand": "Logitech", "price": 109, "color": "graphite", "rating": 4.8, "tags": ["wireless", "productivity", "premium"]},
    {"id": "p7",  "name": "Logitech Pebble 2",           "category": "mouse",      "brand": "Logitech", "price": 34,  "color": "white",    "rating": 4.2, "tags": ["wireless", "budget", "portable"]},
    {"id": "p8",  "name": "Keychron K2",                 "category": "keyboard",   "brand": "Keychron", "price": 89,  "color": "black",    "rating": 4.5, "tags": ["wireless", "mechanical", "compact"]},
    {"id": "p9",  "name": "NuPhy Air75",                 "category": "keyboard",   "brand": "NuPhy",    "price": 139, "color": "gray",     "rating": 4.6, "tags": ["wireless", "mechanical", "low-profile"]},
    {"id": "p10", "name": "Amazon Kindle Paperwhite",    "category": "ereader",    "brand": "Amazon",   "price": 149, "color": "black",    "rating": 4.7, "tags": ["reading", "portable", "gift"]},
]

def populate_db_from_catalog(db: Database, catalog: list):
    for item in catalog:
        db.save_product(item)

def run_tests(db, tools):
    print("Running tests...")
    # [3.A]
    _s3a = ShopState(user_id="test_user")
    _res3a = CoordinatorAgent().run(
        "Find the best wireless mouse under 120 dollars and add it to cart", _s3a, tools
    )
    assert "delegate_retriever" in _res3a.trace
    assert "delegate_pros" in _res3a.trace and "delegate_cons" in _res3a.trace
    assert "delegate_ranker" in _res3a.trace and "delegate_cart" in _res3a.trace
    assert len(_s3a.cart) == 1 and _s3a.cart[0]["product_id"] == "p6"
    assert _res3a.context.best is not None and _res3a.context.best["id"] == "p6"
    assert len(_res3a.context.pros) > 0 and len(_res3a.context.cons) > 0
    print("OK 3.A")

    # [3.B]
    _s3b = ShopState(user_id="test_user")
    _res3b = CoordinatorAgent().run("Find a wireless keyboard", _s3b, tools)
    assert "delegate_retriever" in _res3b.trace
    assert "delegate_pros" in _res3b.trace and "delegate_cons" in _res3b.trace
    assert "delegate_ranker" in _res3b.trace
    assert "delegate_cart" not in _res3b.trace and len(_s3b.cart) == 0
    assert _res3b.context.best is not None
    print("OK 3.B")

    # [3.C]
    _ctx3c = AgentContext(query="test", candidates=[
        {"id": "x1", "name": "A", "price": 200, "rating": 4.8},
        {"id": "x2", "name": "B", "price": 150, "rating": 4.8},
        {"id": "x3", "name": "C", "price": 100, "rating": 4.5},
    ])
    _tr3c = ToolTracer()
    _ctx3c = RankerAgent().run(_ctx3c, _tr3c)
    assert _ctx3c.best["id"] == "x2" and _tr3c.called("rank_candidates")
    print("OK 3.C")

    # [3.D]
    _ctx3d = AgentContext(
        query="mouse under 120 dollars",
        max_price=120.0,
        candidates=[
            {"id": "expensive", "name": "Super Mouse",  "price": 200, "rating": 4.9},
            {"id": "p6",        "name": "MX Master 3S", "price": 109, "rating": 4.8},
            {"id": "p7",        "name": "Pebble 2",      "price": 34,  "rating": 4.2},
        ],
    )
    _tr3d = ToolTracer()
    _ctx3d = RankerAgent().run(_ctx3d, _tr3d)
    assert _ctx3d.best is not None and _ctx3d.best["id"] == "p6"
    print("OK 3.D")
    print("All tests passed!")

def main():
    db = Database(DATABASE_URL)
    tools = ShopTools(db, cache_ttl=CACHE_TTL)

    # Populate DB if empty
    from models import Product
    with db.get_session() as session:
        if session.query(Product).count() == 0:
            print("Populating database with catalog...")
            populate_db_from_catalog(db, CATALOG)
            print("Done.")

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        run_tests(db, tools)
        return

    state = ShopState(user_id="test_user")
    tracer = ToolTracer()
    print("Welcome! Type your request (or 'exit' to quit).")
    while True:
        user_input = input("\n> ")
        if user_input.lower() in ["exit", "quit"]:
            break
        if not user_input.strip():
            continue
        response = run_shopping_agent(user_input, state, tools, tracer)
        print("\n" + response)

if __name__ == "__main__":
    main()