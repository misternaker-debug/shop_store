import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///shop.db")
GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")
if not GIGACHAT_CREDENTIALS:
    raise ValueError("GIGACHAT_CREDENTIALS not set in environment")

MODEL_NAME = os.getenv("MODEL_NAME", "GigaChat-Pro")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))