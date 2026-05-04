from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # detecta conexiones caídas automáticamente
    pool_size=10,
    max_overflow=20,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency de FastAPI: abre y cierra la sesión por cada request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
