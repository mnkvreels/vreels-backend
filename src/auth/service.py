from os import stat
from jwt import PyJWKClient
import requests
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from datetime import timedelta, datetime, timezone

from src.database import get_db
from ..models.user import User
from .schemas import UserCreate, UserUpdate
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND, HTTP_503_SERVICE_UNAVAILABLE
import random
import string
import bcrypt
from ..config import Settings

# Password hashing context using bcrypt
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 password bearer token URL
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="v1/auth/token")

# Algorithm used for JWT token encoding
ALGORITHM = "HS256"  # JWT algorithm for encoding the token

# Token expiration time set to 30 days
TOKEN_EXPIRE_MINS = Settings.ACCESS_TOKEN_EXPIRE_MINUTES  # 30 days

# JWT Configuration
SECRET_KEY = Settings.SECRET_KEY
ALGORITHM = "HS256"

def get_public_keys():
    try:
        # Your JWKS URL here
        jwks_url = "https://<your-tenant-name>.b2clogin.com/<your-tenant-name>.onmicrosoft.com/discovery/v2.0/keys"
        response = requests.get(jwks_url)
        response.raise_for_status()  # Raises an error for bad HTTP status codes
        return response.json().get("keys", [])
    except requests.RequestException as e:
        # Handle errors from network, wrong URL, etc.
        raise HTTPException(
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to fetch JWKS keys from Azure AD B2C",
        )

# PUBLIC_KEYS = get_public_keys()

# Token verification function
def verify_jwt(token: str):
    """
    Verifies the JWT token using Azure AD B2C public keys and returns the decoded payload.
    """
    try:
        # Fetch the public JWKS from Azure AD B2C
        jwks_client = PyJWKClient(Settings.JWKS_URL)
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode the token using RS256
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=Settings.CLIENT_ID,  # Ensures the token is for our app
            issuer=Settings.ISSUER,  # Ensures it's from Azure AD B2C
        )

        # Return user data
        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Function to hash passwords using bcrypt
# def hash_password(password: str) -> str:
#     return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# # Function to verify passwords
# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# Function to check for existing user by username or email
async def existing_user(db: Session, username: str, phone_number: int):
    """
    Check if a user with the given username or email already exists in the database.
    Returns the existing user if found, otherwise returns None.
    """
    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        return db_user
    db_user = db.query(User).filter(User.phone_number == phone_number).first()
    return db_user


# Function to create an access token for the user
async def create_access_token(username: str, id: int):
    """
    Create and return a JWT access token containing the username and user ID.
    The token will expire in 30 days.
    """
    encode = {"sub": username, "id": id}
    expires = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE_MINS)
    encode.update({"exp": expires})
    return jwt.encode(encode, Settings.SECRET_KEY, algorithm=ALGORITHM)


# Function to get the current user based on the provided token
async def get_current_user(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Missing token")

    user_data = verify_jwt(token.replace("Bearer ", ""))  # Validate Azure B2C Token
    
    if not user_data:
        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Invalid token")

    # Query user from database (optional)
    user = db.query(User).filter(User.id == user_data.get("oid")).first()
    if not user:
        raise HTTPException(status_code=HTTP_404_NOT_FOUND, detail="User not found")

    return user


# Function to get a user by their user ID
async def get_user_from_user_id(db: Session, user_id: int):
    """
    Fetch a user from the database using their user ID.
    """
    return db.query(User).filter(User.id == user_id).first()


# Function to create a new user in the database
async def create_user(db: Session, user: UserCreate):
    """
    Create a new user in the database with the provided user data.
    The password will be hashed before storing it in the database.
    """
    db_user = User(
        phone_number=user.phone_number,
        username=user.username.lower().strip(),
        # hashed_password=bcrypt_context.hash(user.password),
        # Optionally, you can add other fields like `dob`, `gender`, etc.
        # dob=user.dob or None,
        # gender=user.gender or None,
        # bio=user.bio or None,
        # location=user.location or None,
        # profile_pic=user.profile_pic or None,
        # name=user.name or None,
    )
    print('user data is:',db_user)
    db.add(db_user)
    db.commit()

    return db_user


# Function to authenticate a user by verifying their username and password
# async def authenticate(db: Session, username: str, password: str):
#     """
#     Authenticate a user by verifying their username and password.
#     Returns the user if authentication is successful, otherwise returns None.
#     """
#     db_user = db.query(User).filter(User.username == username).first()
#     if not db_user:
#         print("No user found with this username")
#         return None
#     if not bcrypt_context.verify(password, db_user.hashed_password):
#         return None
#     return db_user


# Function to update an existing user's profile with new data
async def update_user(db: Session, db_user: User, user_update: UserUpdate):
    """
    Update the existing user's profile with the provided user update data.
    Fields that are not provided will remain unchanged.
    """
    db_user.bio = user_update.bio or db_user.bio
    db_user.name = user_update.name or db_user.name
    db_user.dob = user_update.dob or db_user.dob
    db_user.gender = user_update.gender or db_user.gender
    db_user.location = user_update.location or db_user.location
    db_user.profile_pic = user_update.profile_pic or db_user.profile_pic

    db.commit()
