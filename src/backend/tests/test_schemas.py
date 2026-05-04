"""
Tests unitarios puros de los schemas Pydantic.
No requieren base de datos ni cliente HTTP.
"""
import pytest
from pydantic import ValidationError

from app.schemas import UserRegister, PreferenceIn, RecommendationItem
from app.routers.ratings import RatingIn


class TestUserRegisterSchema:
    def test_valid(self):
        u = UserRegister(username="alice", password="secret123")
        assert u.username == "alice"

    def test_username_stripped(self):
        u = UserRegister(username="  bob  ", password="secret123")
        assert u.username == "bob"

    def test_username_too_short_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(username="ab", password="secret123")
        assert "3 caracteres" in str(exc_info.value)

    def test_username_stripped_then_too_short_raises(self):
        # "  a  " → strip → "a" → longitud 1 → error
        with pytest.raises(ValidationError):
            UserRegister(username="  a  ", password="secret123")

    def test_password_too_short_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            UserRegister(username="alice", password="abc")
        assert "6" in str(exc_info.value)

    def test_password_exact_minimum(self):
        u = UserRegister(username="alice", password="abcdef")
        assert u.password == "abcdef"


class TestRatingInSchema:
    def test_valid_boundary_low(self):
        r = RatingIn(movie_id=1, rating=0.5)
        assert r.rating == 0.5

    def test_valid_boundary_high(self):
        r = RatingIn(movie_id=1, rating=5.0)
        assert r.rating == 5.0

    def test_valid_mid(self):
        r = RatingIn(movie_id=1, rating=3.5)
        assert r.rating == 3.5

    def test_rating_rounded_to_one_decimal(self):
        r = RatingIn(movie_id=1, rating=4.05)
        assert r.rating == round(4.05, 1)

    def test_below_range_raises(self):
        with pytest.raises(ValidationError):
            RatingIn(movie_id=1, rating=0.4)

    def test_above_range_raises(self):
        with pytest.raises(ValidationError):
            RatingIn(movie_id=1, rating=5.1)

    def test_zero_raises(self):
        with pytest.raises(ValidationError):
            RatingIn(movie_id=1, rating=0.0)


class TestPreferenceInSchema:
    def test_valid(self):
        p = PreferenceIn(genre_id=1, score=3.5)
        assert p.score == 3.5

    def test_score_zero_valid(self):
        p = PreferenceIn(genre_id=1, score=0.0)
        assert p.score == 0.0

    def test_score_five_valid(self):
        p = PreferenceIn(genre_id=1, score=5.0)
        assert p.score == 5.0

    def test_score_above_range_raises(self):
        with pytest.raises(ValidationError):
            PreferenceIn(genre_id=1, score=5.1)

    def test_score_below_range_raises(self):
        with pytest.raises(ValidationError):
            PreferenceIn(genre_id=1, score=-0.1)

    def test_score_rounded_to_4_decimals(self):
        p = PreferenceIn(genre_id=1, score=2.12345)
        assert p.score == round(2.12345, 4)


class TestRecommendationItemSchema:
    def test_defaults(self):
        item = RecommendationItem(
            movie_id=10, title="Inception", score=0.95, source="model"
        )
        assert item.genres == []
        assert item.tmdb_id is None
        assert item.poster_url is None

    def test_full_construction(self):
        item = RecommendationItem(
            movie_id=10,
            title="Inception",
            genres=["Sci-Fi", "Thriller"],
            score=0.95,
            tmdb_id=27205,
            source="genre_based",
        )
        assert len(item.genres) == 2
        assert item.source == "genre_based"
