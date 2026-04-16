# CineMatch — Backend API · Grupo E-12

API REST construida con **FastAPI** y **PostgreSQL** para el sistema de recomendación de películas CineMatch.

---

## Estructura del proyecto

```
cinematch-backend/
├── app/
│   ├── main.py              # App principal + health check
│   ├── config.py            # Settings (cargadas desde .env)
│   ├── database.py          # Conexión SQLAlchemy
│   ├── models.py            # Modelos ORM (tablas)
│   ├── schemas.py           # Schemas Pydantic (validación)
│   ├── dependencies.py      # JWT middleware reutilizable
│   ├── routers/
│   │   ├── auth.py          # POST /auth/register, POST /auth/login
│   │   ├── recommendations.py  # GET /recommendations/me, /popular
│   │   ├── movies.py        # GET /movies/search, /movies/{id}
│   │   └── preferences.py   # GET/PUT /users/me/preferences
│   └── services/
│       ├── tmdb.py          # Cliente TMDB API
│       └── recommendations.py  # Lógica de recomendación (3 capas)
├── cinematch_schema.sql     # Schema PostgreSQL completo
├── requirements.txt
├── .env.example             # Plantilla de variables de entorno
└── .gitignore
```

---

## Puesta en marcha (Windows)

### 1. Requisitos previos
- Python 3.11+
- PostgreSQL 16+
- Git

### 2. Clonar e instalar

```powershell
git clone https://github.com/badrlah9/CineMatch-Sistema-de-recomendacion-peliculas
cd cinematch-backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configurar variables de entorno

```powershell
copy .env.example .env
# Edita .env con tus credenciales
```

### 4. Crear la base de datos

```sql
-- En pgAdmin o psql como superusuario:
CREATE USER cinematch_user WITH PASSWORD 'cinematch_pass';
CREATE DATABASE cinematch OWNER cinematch_user;
```

```powershell
psql -U cinematch_user -d cinematch -f cinematch_schema.sql
```

### 5. Arrancar

```powershell
uvicorn app.main:app --reload
```

Documentación interactiva: **http://localhost:8000/docs**

---

## Endpoints disponibles

### Sistema
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/health` | ❌ | Estado de la API y la BD |

### Autenticación
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| POST | `/auth/register` | ❌ | Registrar usuario |
| POST | `/auth/login` | ❌ | Login → devuelve JWT |

### Recomendaciones
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/recommendations/me` | ✅ | Top-K personalizado |
| GET | `/recommendations/popular` | ❌ | Top por popularidad |

### Películas
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/movies/search` | ❌ | Buscar por título o género |
| GET | `/movies/{movie_id}` | ❌ | Detalle de una película |

### Preferencias
| Método | Ruta | Auth | Descripción |
|--------|------|------|-------------|
| GET | `/users/me/preferences` | ✅ | Ver mis géneros favoritos |
| PUT | `/users/me/preferences` | ✅ | Actualizar géneros favoritos |
| DELETE | `/users/me/preferences` | ✅ | Eliminar preferencias |

---

## Lógica de recomendación (3 capas)

```
1. Modelo ML  →  si ML_SERVICE_URL responde correctamente
2. Por género →  si el usuario tiene preferencias definidas
3. Popularidad → fallback siempre disponible
```

El campo `source` en la respuesta indica qué estrategia se usó.

## Integración con el compañero de ML

Cuando el servicio ML esté listo, añadir en `.env`:
```
ML_SERVICE_URL=http://<ip-del-servidor-ml>:8001
```

El endpoint ML esperado:
```
POST /recommend
Body:    { "user_id": int, "k": int }
Response: { "recommendations": [ { "movie_id": int, "score": float } ] }
```

---

## Integrantes del equipo
- **Daniel Ruiz González** — Backend & API Developer
- **Badr Lahrarti** — Data Engineer & Git Lead
- **Alejandro González Mateos** — ML Engineer
- **Francisco López Fenoll** — Frontend & Visualización
