from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from jose import jwt
from datetime import datetime, timedelta, timezone

from app.config   import get_settings
from app.database import get_db
from app.models   import User
from app.schemas  import UserRegister, UserLogin, Token, UserOut

settings   = get_settings()
router     = APIRouter(prefix="/auth", tags=["Autenticación"])
pwd_ctx    = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = (
        datetime.now(timezone.utc)
        + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


@router.post(
    "/register",
    response_model=UserOut,
    status_code=201,
    summary="Registrar un nuevo usuario",
    description="Crea una cuenta nueva con username y contraseña. "
                "La contraseña se almacena hasheada con bcrypt (nunca en texto plano).",
)
def register(body: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El username ya está en uso",
        )
    user = User(
        username      = body.username,
        password_hash = hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión",
    description="Valida las credenciales y devuelve un token JWT. "
                "El token se usa en el header Authorization: Bearer <token> "
                "para acceder a endpoints protegidos.",
)
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    # Mismo mensaje tanto si no existe como si la contraseña es incorrecta (HU-02)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas",
        )
    token = create_token({"sub": str(user.user_id), "username": user.username})
    return {"access_token": token, "token_type": "bearer"}
