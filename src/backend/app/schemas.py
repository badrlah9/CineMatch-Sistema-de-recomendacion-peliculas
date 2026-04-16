from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


# Auth

class UserRegister(BaseModel):
    username: str
    password: str

    @field_validator("username")
    def username_min_length(cls, v):
        v = v.strip()
        if len(v) < 3:
            raise ValueError("El username debe tener al menos 3 caracteres")
        return v

    @field_validator("password")
    def password_min_length(cls, v):
        if len(v) < 6:
            raise ValueError("La contraseña debe tener al menos 6 caracteres")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id:  int
    username: str


class UserOut(BaseModel):
    user_id:   int
    username:  str
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# Géneros

class GenreOut(BaseModel):
    genre_id: int
    name: str

    model_config = {"from_attributes": True}


# Preferencias de género

class PreferenceIn(BaseModel):
    genre_id: int
    score: float

    @field_validator("score")
    def score_range(cls, v):
        if not (0.0 <= v <= 5.0):
            raise ValueError("El score debe estar entre 0.0 y 5.0")
        return round(v, 4)


class PreferenceOut(BaseModel):
    genre_id:   int
    genre_name: str
    score:      float

    model_config = {"from_attributes": True}


# Películas

class MovieBase(BaseModel):
    movie_id: int
    title:    str

    model_config = {"from_attributes": True}


class MovieOut(MovieBase):
    genres:       list[str] = []
    avg_rating:   Optional[float] = None
    total_ratings: Optional[int]  = None
    tmdb_id:      Optional[int]   = None
    # Campos enriquecidos desde TMDB (opcionales, pueden ser None si la API falla)
    poster_url:   Optional[str]   = None
    overview:     Optional[str]   = None
    release_date: Optional[str]   = None


# Recomendaciones

class RecommendationItem(BaseModel):
    movie_id:     int
    title:        str
    genres:       list[str] = []
    score:        float               # score del modelo o bayesian_score
    tmdb_id:      Optional[int]   = None
    poster_url:   Optional[str]   = None
    overview:     Optional[str]   = None
    source:       str = "model"       # "model" | "popularity" | "genre_based"


class RecommendationsOut(BaseModel):
    user_id:        int
    total:          int
    source:         str               # "model" | "popularity" | "genre_based"
    recommendations: list[RecommendationItem]


# Health

class HealthOut(BaseModel):
    status:   str
    database: str
    version:  str
