from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.config   import get_settings
from app.database import get_db
from app.models   import User
from app.schemas  import TokenData

settings = get_settings()
bearer_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency reutilizable: valida el JWT y devuelve el usuario activo.
    Úsala en cualquier endpoint protegido: current_user = Depends(get_current_user)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido o expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.SECRET_KEY,
                             algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        username: str = payload.get("username")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=int(user_id), username=username)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.query(User).filter(User.user_id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    return user
