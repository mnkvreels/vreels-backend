from fastapi import Depends
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from datetime import timedelta, datetime, timezone
from .models import User
from .schemas import UserCreate, UserUpdate
import random
import string
import bcrypt
from twilio.rest import Client
from ..config import Settings

# Password hashing context using bcrypt
bcrypt_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 password bearer token URL
oauth2_bearer = OAuth2PasswordBearer(tokenUrl="v1/auth/token")

# Algorithm used for JWT token encoding
ALGORITHM = "HS256"  # JWT algorithm for encoding the token

# Token expiration time set to 30 days
TOKEN_EXPIRE_MINS = Settings.ACCESS_TOKEN_EXPIRE_MINUTES  # 30 days

# Twilio API Credentials (Stored in settings or env variables)
TWILIO_ACCOUNT_SID = Settings.TWILIO_ACCOUNT_SID
TWILIO_AUTH_TOKEN = Settings.TWILIO_AUTH_TOKEN
TWILIO_PHONE_NUMBER = Settings.TWILIO_PHONE_NUMBER

# JWT Configuration
SECRET_KEY = Settings.SECRET_KEY
ALGORITHM = "HS256"

# Function to send OTP via SMS using Twilio
def send_otp_via_sms(phone_number: str, otp: str):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"Your OTP code is: {otp}",
            from_=TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        return message.sid
    except Exception as e:
        raise Exception(f"Failed to send OTP: {str(e)}")

# Function to generate a 6-digit OTP
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

# Function to hash passwords using bcrypt
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# Function to verify passwords
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

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
async def get_current_user(db: Session, token: str = Depends(oauth2_bearer)):
    """
    Decode the JWT token, verify its validity, and return the user associated with the token.
    Returns None if the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, Settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        id: str = payload.get("id")
        expires: datetime = payload.get("exp")

        # Check if the token has expired
        if datetime.fromtimestamp(expires) < datetime.now():
            return None
        
        # Check if the username or user ID is missing from the token
        if username is None or id is None:
            return None
        
        return db.query(User).filter(User.id == id).first()
    
    except JWTError:
        return None


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
        email=user.email.lower().strip(),
        username=user.username.lower().strip(),
        hashed_password=bcrypt_context.hash(user.password),
        # Optionally, you can add other fields like `dob`, `gender`, etc.
        # dob=user.dob or None,
        # gender=user.gender or None,
        # bio=user.bio or None,
        # location=user.location or None,
        # profile_pic=user.profile_pic or None,
        # name=user.name or None,
    )
    db.add(db_user)
    db.commit()

    return db_user


# Function to authenticate a user by verifying their username and password
async def authenticate(db: Session, username: str, password: str):
    """
    Authenticate a user by verifying their username and password.
    Returns the user if authentication is successful, otherwise returns None.
    """
    db_user = db.query(User).filter(User.username == username).first()
    if not db_user:
        print("No user found with this username")
        return None
    if not bcrypt_context.verify(password, db_user.hashed_password):
        return None
    return db_user


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
