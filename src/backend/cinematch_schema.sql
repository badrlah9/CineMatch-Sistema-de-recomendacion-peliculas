-- CineMatch · Esquema PostgreSQL
-- Grupo E-12 · Fase 1
--
-- Bloque 1 (MovieLens): genres, movies, movie_genres, links, ratings
-- Bloque 2 (CineMatch): users, user_genre_preferences

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid(), crypt()
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- búsqueda parcial de títulos


-- Bloque 1: Dataset MovieLens

-- 1.1 genres
-- Catálogo de los 19 géneros de MovieLens. Lo usan movie_genres y user_genre_preferences.
CREATE TABLE genres (
    genre_id   SERIAL       PRIMARY KEY,
    name       VARCHAR(50)  NOT NULL UNIQUE
);

COMMENT ON TABLE  genres      IS 'Catálogo de géneros cinematográficos (vocabulario controlado MovieLens).';
COMMENT ON COLUMN genres.name IS 'Nombre del género, e.g. Action, Comedy, Drama …';

-- Seed: los 19 géneros oficiales de MovieLens
INSERT INTO genres (name) VALUES
    ('Action'),
    ('Adventure'),
    ('Animation'),
    ('Children'),
    ('Comedy'),
    ('Crime'),
    ('Documentary'),
    ('Drama'),
    ('Fantasy'),
    ('Film-Noir'),
    ('Horror'),
    ('Musical'),
    ('Mystery'),
    ('Romance'),
    ('Sci-Fi'),
    ('Thriller'),
    ('War'),
    ('Western'),
    ('(no genres listed)');


-- 1.2 movies
-- 87.585 títulos. movie_id es el ID original de MovieLens (no SERIAL)
-- para mantener consistencia con ratings.csv y links.csv.
CREATE TABLE movies (
    movie_id   INTEGER      PRIMARY KEY,
    title      VARCHAR(500) NOT NULL
);

COMMENT ON TABLE  movies          IS 'Catálogo de películas del dataset MovieLens 32M (87.585 títulos).';
COMMENT ON COLUMN movies.movie_id IS 'ID original MovieLens, consistente entre ratings.csv, movies.csv y links.csv.';
COMMENT ON COLUMN movies.title    IS 'Título con año de estreno entre paréntesis.';

-- Índice trigramas para búsqueda parcial de título
CREATE INDEX idx_movies_title_trgm ON movies USING GIN (title gin_trgm_ops);


-- 1.3 movie_genres
-- Relación N:M entre movies y genres.
CREATE TABLE movie_genres (
    movie_id   INTEGER NOT NULL REFERENCES movies (movie_id) ON DELETE CASCADE,
    genre_id   INTEGER NOT NULL REFERENCES genres (genre_id) ON DELETE RESTRICT,
    CONSTRAINT pk_movie_genres PRIMARY KEY (movie_id, genre_id)
);

COMMENT ON TABLE movie_genres IS 'Relación N:M película–género. Normaliza el campo genres pipe-separated de movies.csv.';

CREATE INDEX idx_movie_genres_genre ON movie_genres (genre_id);


-- 1.4 links
-- tmdb_id e imdb_id para enriquecer con la TMDB API (pósters, sinopsis).
CREATE TABLE links (
    movie_id   INTEGER PRIMARY KEY REFERENCES movies (movie_id) ON DELETE CASCADE,
    imdb_id    VARCHAR(20),
    tmdb_id    INTEGER
);

COMMENT ON TABLE  links         IS 'IDs externos (IMDb, TMDb) vinculados 1:1 a cada película. Fuente: links.csv.';
COMMENT ON COLUMN links.tmdb_id IS 'ID en The Movie Database. Usado para obtener pósters y sinopsis via TMDB API.';
COMMENT ON COLUMN links.imdb_id IS 'ID en IMDb (sin el prefijo tt).';

CREATE INDEX idx_links_tmdb ON links (tmdb_id);


-- 1.5 ratings
-- 32M valoraciones de MovieLens. Los user_id son anónimos del dataset,
-- distintos e incompatibles con los user_id de la tabla users de CineMatch.
CREATE TABLE ratings (
    rating_id   BIGSERIAL    PRIMARY KEY,
    user_id     INTEGER      NOT NULL,
    movie_id    INTEGER      NOT NULL REFERENCES movies (movie_id) ON DELETE CASCADE,
    rating      NUMERIC(2,1) NOT NULL
                             CHECK (rating >= 0.5 AND rating <= 5.0),
    rated_at    TIMESTAMPTZ  NOT NULL
);

COMMENT ON TABLE  ratings         IS 'Valoraciones históricas del dataset MovieLens 32M. user_id es anónimo y distinto al de la tabla users.';
COMMENT ON COLUMN ratings.user_id IS 'ID anónimo del usuario de MovieLens. Sin relación con la tabla users de CineMatch.';
COMMENT ON COLUMN ratings.rating  IS 'Valoración de 0.5 a 5.0 en incrementos de 0.5 estrellas.';
COMMENT ON COLUMN ratings.rated_at IS 'Timestamp convertido de Unix epoch a TIMESTAMPTZ durante la ingesta ETL.';

CREATE INDEX idx_ratings_user     ON ratings (user_id);
CREATE INDEX idx_ratings_movie    ON ratings (movie_id);
CREATE INDEX idx_ratings_rated_at ON ratings (rated_at DESC);
CREATE UNIQUE INDEX idx_ratings_user_movie ON ratings (user_id, movie_id);


-- Bloque 2: Plataforma CineMatch

-- 2.1 users
-- Solo username y hash de contraseña (minimización de datos, GDPR).
CREATE TABLE users (
    user_id        SERIAL       PRIMARY KEY,
    username       VARCHAR(50)  NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  users               IS 'Usuarios registrados en CineMatch. Solo username + hash de contraseña (GDPR).';
COMMENT ON COLUMN users.password_hash IS 'Hash bcrypt de la contraseña. Nunca se almacena el texto plano.';
COMMENT ON COLUMN users.username      IS 'Nombre de usuario único para login.';

CREATE INDEX idx_users_username ON users (username);

-- Trigger para mantener updated_at automáticamente
CREATE OR REPLACE FUNCTION fn_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();


-- 2.2 user_genre_preferences
-- Preferencias de género por usuario. Resuelve el cold-start hasta tener historial.
CREATE TABLE user_genre_preferences (
    user_id    INTEGER        NOT NULL REFERENCES users  (user_id)  ON DELETE CASCADE,
    genre_id   INTEGER        NOT NULL REFERENCES genres (genre_id) ON DELETE RESTRICT,
    score      NUMERIC(5,4)   NOT NULL DEFAULT 0.5000
                              CHECK (score >= 0.0 AND score <= 5.0),
    updated_at TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_user_genre_prefs PRIMARY KEY (user_id, genre_id)
);

COMMENT ON TABLE  user_genre_preferences       IS 'Preferencias de género por usuario. Solución al cold-start hasta disponer de historial.';
COMMENT ON COLUMN user_genre_preferences.score IS 'Afinidad del usuario hacia el género [0.0–5.0].';

CREATE INDEX idx_ugp_genre ON user_genre_preferences (genre_id);

CREATE TRIGGER trg_ugp_updated_at
    BEFORE UPDATE ON user_genre_preferences
    FOR EACH ROW EXECUTE FUNCTION fn_set_updated_at();


-- 2.3 cinematch_ratings
-- Valoraciones de los usuarios de CineMatch (distintas de los ratings históricos de MovieLens).
-- Separadas para evitar colisión de user_id con los datos del dataset.
CREATE TABLE cinematch_ratings (
    rating_id   BIGSERIAL    PRIMARY KEY,
    user_id     INTEGER      NOT NULL REFERENCES users  (user_id)  ON DELETE CASCADE,
    movie_id    INTEGER      NOT NULL REFERENCES movies (movie_id) ON DELETE CASCADE,
    rating      NUMERIC(2,1) NOT NULL
                             CHECK (rating >= 0.5 AND rating <= 5.0),
    rated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_cinematch_ratings_user_movie UNIQUE (user_id, movie_id)
);

COMMENT ON TABLE cinematch_ratings IS 'Valoraciones de usuarios CineMatch. Separada de ratings (MovieLens) para evitar colisión de user_id.';

CREATE INDEX idx_cinematch_ratings_user  ON cinematch_ratings (user_id);
CREATE INDEX idx_cinematch_ratings_movie ON cinematch_ratings (movie_id);


-- 2.4 user_recommendation_state
-- Estado de rotación del motor ML por usuario.
-- Primera llamada → state = NULL. Cada respuesta del ML devuelve un estado
-- actualizado que se persiste aquí y se reenvía en la siguiente llamada,
-- evitando que el modelo repita siempre las mismas recomendaciones.
CREATE TABLE user_recommendation_state (
    user_id    INTEGER      PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    state      TEXT         NOT NULL,   -- JSON serializado del recommendation_state del ML
    updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE user_recommendation_state IS 'Estado de rotación del ML por usuario. Se acumula entre llamadas para evitar repetir recomendaciones.';


-- Vistas

-- Estadísticas agregadas por película
CREATE OR REPLACE VIEW vw_movie_stats AS
SELECT
    m.movie_id,
    m.title,
    COUNT(r.rating_id)      AS total_ratings,
    ROUND(AVG(r.rating), 2) AS avg_rating,
    MIN(r.rated_at)         AS first_rated_at,
    MAX(r.rated_at)         AS last_rated_at
FROM movies m
LEFT JOIN ratings r ON r.movie_id = m.movie_id
GROUP BY m.movie_id, m.title;

COMMENT ON VIEW vw_movie_stats IS 'Estadísticas agregadas por película: total valoraciones y media.';


-- Géneros de cada película desnormalizados (cómodo para el frontend)
CREATE OR REPLACE VIEW vw_movie_genres AS
SELECT
    m.movie_id,
    m.title,
    STRING_AGG(g.name, ' | ' ORDER BY g.name) AS genres
FROM movies m
JOIN movie_genres mg ON mg.movie_id = m.movie_id
JOIN genres       g  ON g.genre_id  = mg.genre_id
GROUP BY m.movie_id, m.title;

COMMENT ON VIEW vw_movie_genres IS 'Géneros de cada película concatenados con pipe (|).';


-- Top-N películas más populares con score bayesiano (fallback cold-start)
CREATE OR REPLACE VIEW vw_top_popular AS
SELECT
    m.movie_id,
    m.title,
    l.tmdb_id,
    COUNT(r.rating_id)      AS total_ratings,
    ROUND(AVG(r.rating), 2) AS avg_rating,
    ROUND(
        (COUNT(r.rating_id)::NUMERIC / (COUNT(r.rating_id) + 500)) * AVG(r.rating)
        + (500.0 / (COUNT(r.rating_id) + 500)) * 3.5,
    4) AS bayesian_score
FROM movies  m
JOIN ratings r  ON r.movie_id = m.movie_id
LEFT JOIN links l ON l.movie_id = m.movie_id
GROUP BY m.movie_id, m.title, l.tmdb_id
HAVING COUNT(r.rating_id) >= 50
ORDER BY bayesian_score DESC;

COMMENT ON VIEW vw_top_popular IS 'Ranking de películas por score bayesiano. Fallback de cold-start y para el dashboard.';
