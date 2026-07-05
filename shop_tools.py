from database import Database
from state import ShopState
from typing import List

class ShopTools:
    def __init__(self, db: Database, cache_ttl: int = 3600):
        self.db = db
        self.cache_ttl = cache_ttl

    def search_products(self, query: str = "", category: str | None = None,
                        brand: str | None = None, max_price: float | None = None,
                        sort_by: str | None = None) -> List[dict]:
        cached_ids = self.db.get_cached_search(query, category, brand, max_price, sort_by)
        if cached_ids is not None:
            products = self.db.get_products_by_ids(cached_ids)
            if max_price is not None:
                products = [p for p in products if p["price"] <= max_price]
            if sort_by == "price_asc":
                products.sort(key=lambda x: x["price"])
            elif sort_by == "rating_desc":
                products.sort(key=lambda x: -x.get("rating", 0))
            return products

        results = self.db.search_products_db(query, category, brand, max_price, sort_by)
        if results:
            ids = [p["id"] for p in results]
            self.db.save_search_cache(query, category, brand, max_price, sort_by, ids, self.cache_ttl)
        return results

    def add_to_cart(self, state: ShopState, product_id: str, quantity: int = 1) -> dict:
        if not state.user_id:
            return {"ok": False, "error": "User ID not set in state"}
        return self.db.add_to_cart_db(state.user_id, product_id, quantity)