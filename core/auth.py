from passlib.context import CryptContext
from sqlalchemy.orm import Session  # Import Session from SQLAlchemy
import jwt
from datetime import datetime, timedelta
from typing import Optional

SECRET_KEY = "django-insecure-=zzn-uq121w*elzh)_(hapbyq0zk&9ay+1b3flxxa3lnkiz0ao"  
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verify_jwt_token(token: str, db: Session):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    
    blacklisted = db.query(BlacklistedToken).filter(BlacklistedToken.token == token).first()
    if blacklisted:
        raise HTTPException(status_code=401, detail="Token has been revoked")

    return payload

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def hash_password(password):
    return pwd_context.hash(password)
