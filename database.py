from sqlalchemy import create_engine, String, cast
from sqlalchemy.orm import sessionmaker, Session
from models import Base, Product, UserProfile, CartItem, SearchCache
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

class Database:
    def __init__(self, db_url: str, echo: bool = False):
        self.engine = create_engine(db_url, echo=echo)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        return self.SessionLocal()

    def _serialize_value(self, value):
        """Преобразует datetime в строку ISO, остальные значения оставляет как есть."""
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _to_dict(self, obj):
        """Преобразует SQLAlchemy объект в словарь с сериализованными значениями."""
        return {c.name: self._serialize_value(getattr(obj, c.name)) for c in obj.__table__.columns}

    # ---------- Products ----------
    def save_product(self, product_data: dict):
        with self.get_session() as session:
            product = session.get(Product, product_data["id"])
            if product:
                for key, value in product_data.items():
                    if hasattr(product, key):
                        setattr(product, key, value)
                product.updated_at = datetime.utcnow()
            else:
                product = Product(**product_data)
                session.add(product)
            session.commit()

    def save_products(self, products: list[dict]):
        for p in products:
            self.save_product(p)

    def get_product(self, product_id: str) -> dict | None:
        with self.get_session() as session:
            product = session.get(Product, product_id)
            if product:
                return self._to_dict(product)
            return None

    def get_products_by_ids(self, ids: list[str]) -> list[dict]:
        with self.get_session() as session:
            products = session.query(Product).filter(Product.id.in_(ids)).all()
            return [self._to_dict(p) for p in products]

    def search_products_db(self, query: str = "", category: str | None = None,
                          brand: str | None = None, max_price: float | None = None,
                          sort_by: str | None = None, limit: int = 50) -> list[dict]:
        with self.get_session() as session:
            q = session.query(Product)
            if query:
                q = q.filter(
                    Product.name.ilike(f'%{query}%') |
                    Product.brand.ilike(f'%{query}%') |
                    cast(Product.tags, String).ilike(f'%{query}%')
                )
            if category:
                q = q.filter(Product.category == category)
            if brand:
                q = q.filter(Product.brand.ilike(brand))
            if max_price is not None:
                q = q.filter(Product.price <= max_price)

            if sort_by == "price_asc":
                q = q.order_by(Product.price.asc())
            elif sort_by == "rating_desc":
                q = q.order_by(Product.rating.desc())

            products = q.limit(limit).all()
            return [self._to_dict(p) for p in products]

    # ---------- Cart ----------
    def get_cart(self, user_id: str) -> list[dict]:
        with self.get_session() as session:
            items = session.query(CartItem).filter(CartItem.user_id == user_id).all()
            return [self._to_dict(i) for i in items]

    def add_to_cart_db(self, user_id: str, product_id: str, quantity: int = 1) -> dict:
        with self.get_session() as session:
            # 1. Проверяем, существует ли пользователь
            user = session.get(UserProfile, user_id)
            if not user:
                # Создаём профиль пользователя автоматически
                user = UserProfile(user_id=user_id)
                session.add(user)
                session.flush()  # чтобы получить ID, если нужно
            
            # 2. Проверяем товар
            product = session.get(Product, product_id)
            if not product:
                return {"ok": False, "error": f"Product {product_id} not found"}
            
            # 3. Добавляем в корзину
            item = session.query(CartItem).filter_by(user_id=user_id, product_id=product_id).first()
            if item:
                item.quantity += quantity
            else:
                item = CartItem(
                    user_id=user_id,
                    product_id=product_id,
                    quantity=quantity,
                    product_name=product.name,
                    product_price=product.price
                )
                session.add(item)
            session.commit()
            cart_size = session.query(CartItem).filter(CartItem.user_id == user_id).count()
            return {"ok": True, "cart_size": cart_size}

    # ---------- Profile ----------
    def get_profile(self, user_id: str) -> dict:
        with self.get_session() as session:
            profile = session.get(UserProfile, user_id)
            if not profile:
                return {}
            return {c.name: self._serialize_value(getattr(profile, c.name)) for c in profile.__table__.columns if c.name != 'user_id'}

    def update_profile(self, user_id: str, key: str, value: Any):
        with self.get_session() as session:
            profile = session.get(UserProfile, user_id)
            if not profile:
                profile = UserProfile(user_id=user_id)
                session.add(profile)
            setattr(profile, key, value)
            session.commit()
            return {"ok": True}

    # ---------- Search cache ----------
    def get_cached_search(self, query: str, category: str | None, brand: str | None,
                          max_price: float | None, sort_by: str | None) -> list[str] | None:
        with self.get_session() as session:
            cache = session.query(SearchCache).filter(
                SearchCache.query == query,
                SearchCache.category == (category if category else None),
                SearchCache.brand == (brand if brand else None),
                SearchCache.max_price == max_price,
                SearchCache.sort_by == (sort_by if sort_by else None)
            ).first()
            if cache and cache.expires_at > datetime.utcnow():
                return cache.result_ids
            return None

    def save_search_cache(self, query: str, category: str | None, brand: str | None,
                          max_price: float | None, sort_by: str | None, result_ids: list[str],
                          ttl_seconds: int = 3600):
        with self.get_session() as session:
            session.query(SearchCache).filter(
                SearchCache.query == query,
                SearchCache.category == (category if category else None),
                SearchCache.brand == (brand if brand else None),
                SearchCache.max_price == max_price,
                SearchCache.sort_by == (sort_by if sort_by else None)
            ).delete()
            cache = SearchCache(
                query=query,
                category=category,
                brand=brand,
                max_price=max_price,
                sort_by=sort_by,
                result_ids=result_ids,
                created_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(seconds=ttl_seconds)
            )
            session.add(cache)
            session.commit()

    def clean_expired_cache(self):
        with self.get_session() as session:
            session.query(SearchCache).filter(SearchCache.expires_at < datetime.utcnow()).delete()
            session.commit()