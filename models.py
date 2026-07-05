from sqlalchemy import Column, String, Float, Integer, DateTime, JSON, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Product(Base):
    __tablename__ = 'products'
    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False)
    category = Column(String)
    brand = Column(String)
    price = Column(Float)
    color = Column(String)
    rating = Column(Float)
    tags = Column(JSON)
    description = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_category', 'category'),
        Index('idx_brand', 'brand'),
        Index('idx_price', 'price'),
    )

class UserProfile(Base):
    __tablename__ = 'user_profiles'
    user_id = Column(String, primary_key=True)
    name = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    max_price = Column(Float, nullable=True)
    color = Column(String, nullable=True)
    category = Column(String, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class CartItem(Base):
    __tablename__ = 'cart_items'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey('user_profiles.user_id'))
    product_id = Column(String, ForeignKey('products.id'))
    quantity = Column(Integer, default=1)
    product_name = Column(String)
    product_price = Column(Float)
    added_at = Column(DateTime, default=datetime.utcnow)

class SearchCache(Base):
    __tablename__ = 'search_cache'
    id = Column(Integer, primary_key=True, autoincrement=True)
    query = Column(String, index=True)
    category = Column(String, nullable=True)
    brand = Column(String, nullable=True)
    max_price = Column(Float, nullable=True)
    sort_by = Column(String, nullable=True)
    result_ids = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)