from sqlalchemy import (
    Column, Integer, BigInteger, String, Numeric,
    DateTime, ForeignKey, UniqueConstraint, func
)
from sqlalchemy.orm import relationship
from app.database import Base


# Bloque MovieLens

class Genre(Base):
    __tablename__ = "genres"

    genre_id = Column(Integer, primary_key=True, index=True)
    name     = Column(String(50), nullable=False, unique=True)

    movie_genres       = relationship("MovieGenre", back_populates="genre")
    user_preferences   = relationship("UserGenrePreference", back_populates="genre")


class Movie(Base):
    __tablename__ = "movies"

    movie_id = Column(Integer, primary_key=True, index=True)
    title    = Column(String(500), nullable=False)

    genres  = relationship("MovieGenre", back_populates="movie")
    link    = relationship("Link", back_populates="movie", uselist=False)
    ratings = relationship("Rating", back_populates="movie")


class MovieGenre(Base):
    __tablename__ = "movie_genres"

    movie_id = Column(Integer, ForeignKey("movies.movie_id", ondelete="CASCADE"),
                      primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.genre_id", ondelete="RESTRICT"),
                      primary_key=True)

    movie = relationship("Movie",  back_populates="genres")
    genre = relationship("Genre",  back_populates="movie_genres")


class Link(Base):
    __tablename__ = "links"

    movie_id = Column(Integer, ForeignKey("movies.movie_id", ondelete="CASCADE"),
                      primary_key=True)
    imdb_id  = Column(String(20))
    tmdb_id  = Column(Integer, index=True)

    movie = relationship("Movie", back_populates="link")


class Rating(Base):
    __tablename__ = "ratings"

    rating_id = Column(BigInteger, primary_key=True, index=True)
    user_id   = Column(Integer, nullable=False, index=True)   # ID anónimo MovieLens
    movie_id  = Column(Integer, ForeignKey("movies.movie_id", ondelete="CASCADE"),
                       nullable=False, index=True)
    rating    = Column(Numeric(2, 1), nullable=False)
    rated_at  = Column(DateTime(timezone=True), nullable=False)

    movie = relationship("Movie", back_populates="ratings")

    __table_args__ = (
        UniqueConstraint("user_id", "movie_id", name="uq_ratings_user_movie"),
    )


# Bloque CineMatch

class User(Base):
    __tablename__ = "users"

    user_id       = Column(Integer, primary_key=True, index=True)
    username      = Column(String(50), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    created_at    = Column(DateTime(timezone=True), server_default=func.now())
    updated_at    = Column(DateTime(timezone=True), server_default=func.now(),
                           onupdate=func.now())

    genre_preferences = relationship("UserGenrePreference", back_populates="user",
                                     cascade="all, delete-orphan")


class UserGenrePreference(Base):
    __tablename__ = "user_genre_preferences"

    user_id  = Column(Integer, ForeignKey("users.user_id",  ondelete="CASCADE"),
                      primary_key=True)
    genre_id = Column(Integer, ForeignKey("genres.genre_id", ondelete="RESTRICT"),
                      primary_key=True)
    score    = Column(Numeric(5, 4), nullable=False, default=0.5)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(),
                        onupdate=func.now())

    user  = relationship("User",  back_populates="genre_preferences")
    genre = relationship("Genre", back_populates="user_preferences")
