from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.config   import get_settings
from app.database import engine
from app.routers  import auth, recommendations, movies, preferences

settings = get_settings()

app = FastAPI(
    title       = "CineMatch API",
    description = "Backend del sistema de recomendación de películas — Grupo E-12",
    version     = settings.APP_VERSION,
    docs_url    = "/docs",
    redoc_url   = "/redoc",
)

# CORS: permite que el frontend de Streamlit (compañero) pueda llamar a la API
app.add_middleware(
    CORSMiddleware,
    allow_origins  = ["*"],   # En producción, restringir al dominio del frontend
    allow_methods  = ["*"],
    allow_headers  = ["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(recommendations.router)
app.include_router(movies.router)
app.include_router(preferences.router)


# Health check
@app.get(
    "/health",
    tags=["Sistema"],
    summary="Verificar que la API y la base de datos están operativas",
    description="Endpoint de monitorización. Comprueba la conexión a PostgreSQL "
                "y devuelve el estado del sistema. No requiere autenticación.",
)
def health_check():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return {
        "status":   "ok" if db_status == "ok" else "degraded",
        "database": db_status,
        "version":  settings.APP_VERSION,
    }


# Root
@app.get("/", include_in_schema=False)
def root():
    return {
        "message": "CineMatch API · Grupo E-12",
        "docs":    "/docs",
        "health":  "/health",
    }
