from os import stat
from jwt import PyJWKClient
import requests
import json
from fastapi import Depends, HTTPException, Request
from sqlalchemy import BigInteger, and_
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from datetime import timedelta, datetime, timezone
from src.database import get_db
from ..models.user import User, BlockedUsers, OTP, Follow
from ..models.post import Post, Like, Comment, UserSavedPosts, UserSharedPosts, post_hashtags
from ..models.activity import Activity
from .schemas import UserCreate, UserUpdate
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_404_NOT_FOUND, HTTP_503_SERVICE_UNAVAILABLE
import random
import string
import bcrypt
from ..config import Settings
from ..notification_service import send_push_notification
from azure.communication.sms import SmsClient, SmsSendResult
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

connection_string = "endpoint=https://acs-for-testing.unitedstates.communication.azure.com/;accesskey=DShwBDybMlZQDy3AzLR1Kydo7EfUVOgq7qnZr8JwPWBL3UBAY0x8JQQJ99BBACULyCpZLpE0AAAAAZCS7wUJ"
sms_client = SmsClient.from_connection_string(connection_string)

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
# def verify_jwt(token: str):
#     """
#     Verifies the JWT token using Azure AD B2C public keys and returns the decoded payload.
#     """
#     try:
#         # Fetch the public JWKS from Azure AD B2C
#         jwks_client = PyJWKClient(Settings.JWKS_URL)
#         signing_key = jwks_client.get_signing_key_from_jwt(token)

#         # Decode the token using RS256
#         payload = jwt.decode(
#             token,
#             signing_key.key,
#             algorithms=["RS256"],
#             audience=Settings.CLIENT_ID,  # Ensures the token is for our app
#             issuer=Settings.ISSUER,  # Ensures it's from Azure AD B2C
#         )

#         # Return user data
#         return payload

#     except jwt.ExpiredSignatureError:
#         raise HTTPException(status_code=401, detail="Token has expired")
#     except jwt.InvalidTokenError:
#         raise HTTPException(status_code=401, detail="Invalid token")

# Function to hash passwords using bcrypt
# def hash_password(password: str) -> str:
#     return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

# # Function to verify passwords
# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

# Function to check for existing user by username or email
async def existing_user(db: Session, username: str, phone_number: int = None):
    """
    Check if a user with the given username or email already exists in the database.
    Returns the existing user if found, otherwise returns None.
    """
    db_user = db.query(User).filter(User.username == username).first()
    if db_user:
        return db_user
    if phone_number:
        db_user = db.query(User).filter(User.phone_number == phone_number).first()
    return db_user


# Function to create an access token for the user
async def create_access_token(username: str, id: int):
    """
    Create and return a JWT access token containing the username and user ID.
    The token will expire in a specified number of minutes.
    """
    encode = {"sub": username, "id": id}
    
    # Set expiration time in minutes (from your settings)
    expires = datetime.now(timezone.utc) + timedelta(minutes=Settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    # Convert expiration time to a Unix timestamp (seconds since epoch)
    encode.update({"exp": expires.timestamp()})  # Convert to seconds
    
    # Return the JWT token
    return jwt.encode(encode, Settings.SECRET_KEY, algorithm=Settings.ALGORITHM)


# Function to get the current user based on the provided token
async def get_current_user(db: Session = Depends(get_db), token: str = Depends(oauth2_bearer)):
    """
    Decode the JWT token, verify its validity, and return the user associated with the token.
    Returns None if the token is invalid or expired.
    """
    print(f"Received token: {token}")  # Debugging line
    try:
        # Decode the JWT token
        payload = jwt.decode(token, Settings.SECRET_KEY, algorithms=[ALGORITHM])
        print(f"Decoded payload: {payload}")  # Debugging line

        username: str = payload.get("sub")
        user_id: int = payload.get("id")
        expires: int = payload.get("exp")  # Expiration timestamp

        # Debugging expiration
        print(f"Token expires at: {datetime.fromtimestamp(expires)}")

        # Check if the token has expired
        if datetime.fromtimestamp(expires) < datetime.now():
            print("Token has expired!")  # Debugging line
            raise HTTPException(status_code=401, detail="Token has expired")

        # Check if the username or user ID is missing from the token
        if username is None or user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")

        # Fetch the user from the database
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        return user
    
    except JWTError as e:
        print(f"JWT Decode Error: {str(e)}")  # Debugging line
        raise HTTPException(status_code=401, detail="Invalid token")



# Function to get a user by their user ID
async def get_user_from_user_id(db: Session, user_id: int):
    """
    Fetch a user from the database using their user ID.
    """
    return db.query(User).filter(User.id == user_id).first()

# Function to get a user by their user ID
async def get_user_by_username(db: Session, username: str):
    """
    Fetch a user from the database using their user ID.
    """
    return db.query(User).filter(User.username == username).first()

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
async def authenticate(db: Session, username: str, phone_number: BigInteger):
    """
    Authenticate a user by verifying their username and password.
    Returns the user if authentication is successful, otherwise returns None.
    """
    db_user = db.query(User).filter(and_(User.username == username, User.phone_number == phone_number)).first()

    if not db_user:
        print("No user found with this username")
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
    db.refresh(db_user)  # Refresh the user instance to get updated data
    return db.query(User).filter(User.id == db_user.id).first()

async def block_user_svc(db, blocker_id, blocked_id):
    # Ensure both users exist
    blocker = db.query(User).filter(User.id == blocker_id).first()
    blocked = db.query(User).filter(User.id == blocked_id).first()
    
    if not blocker:
        raise ValueError(f"Blocker with ID {blocker_id} does not exist")
    if not blocked:
        raise ValueError(f"Blocked user with ID {blocked_id} does not exist")
    
    # Check if the user is already blocked
    existing_block = db.query(BlockedUsers).filter(
        BlockedUsers.blocker_id == blocker_id,
        BlockedUsers.blocked_id == blocked_id
    ).first()
    
    if existing_block:
        # Return False to indicate that the user is already blocked
        return False
    
    # Add the new block if no existing block is found
    new_block = BlockedUsers(blocker_id=blocker_id, blocked_id=blocked_id)
    db.add(new_block)
    db.commit()
    
    # Return True to indicate the user has been successfully blocked
    return True

async def unblock_user_svc(db: Session, blocker_id: int, blocked_id: int):
    existing_block = db.query(BlockedUsers).filter(
        BlockedUsers.blocker_id == blocker_id,
        BlockedUsers.blocked_id == blocked_id
    ).first()

    if not existing_block:
        return False  # Not blocked

    db.delete(existing_block)
    db.commit()
    return True

async def get_blocked_users_svc(db: Session, user_id: int):
    blocked_users = db.query(User).join(BlockedUsers, User.id == BlockedUsers.blocked_id).filter(
        BlockedUsers.blocker_id == user_id
    ).all()

    return blocked_users

async def send_notification_to_user(db: Session, user_id: int, title: str, message: str):
    user = await get_user_from_user_id(db, user_id)
    if user and user.device_token:
        await send_push_notification(
            device_token=user.device_token,
            platform=user.platform,
            title=title,
            message=message
        )

# OTP Generation function
async def generate_otp(otp_length=6):
    base_number = 10 ** (otp_length - 1)
    number = random.randint(base_number, base_number * 10 - 1)
    return str(number)

# Send SMS function using the SMS API (SMSCountry in this case)
async def send_sms(mobile, otp):
    if str(mobile).startswith("91"):
        url = "https://restapi.smscountry.com/v0.1/Accounts/mQWTheACJyLM60UPeREV/SMSes/"
        headers = {
            'Authorization': 'Basic bVFXVGhlQUNKeUxNNjBVUGVSRVY6SUxhc2FZc0hXcVVVSklvSHBWbXNkYkNPNjFrMVBvdDQyeWNjbmRDWQ==',
            'Content-Type': 'application/json',
        }
        data = {
            "Text": f"Hello your log in OTP is {otp},please do not share with anyone.-Vreels",
            "Number": mobile,
            "SenderId": "",
            "DRNotifyUrl": "https://www.domainname.com/notifyurl",
            "DRNotifyHttpMethod": "POST",
            "Tool": "API"
        }
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code in [200, 202]:
            return True
        else:
            return False
    elif str(mobile).startswith("1"):
        # United States - Using Azure Communication Services (ACS)
        from_number = "+18338432200"  # Replace with your ACS purchased phone number
        to_number = f"+{mobile}"  # Ensure the mobile number is in E.164 format

        # Define the SMS message
        message = sms_client.send(
            from_=from_number,
            to=[to_number],
            message=f"Hello your log in OTP is {otp}, please do not share with anyone.-Vreels"
        )

        # Send the SMS via Azure Communication Services
        try:
            response = sms_client.send(
                from_=from_number,
                to=[to_number],
                message=f"Hello your log in OTP is {otp}, please do not share with anyone.-Vreels"
            )
            if response:
                for result in response:
                    if result.message_id:
                        return True
            else:
                return False
        except Exception as e:
            print(f"Error sending SMS via ACS: {e}")
            return False

    else:
        # Invalid country code or other cases
        return True

# OTP function to store OTP in the database
async def otp_function(db, user_id, phone_number):
    if str(phone_number).startswith("91"):
        otp = await generate_otp(6)
    elif str(phone_number).startswith("1"):  # Check for US country code (+1)
        otp = await generate_otp(6)
    else:
        otp = "123456"

    otp_details = OTP(
        user_id=user_id,
        otp=otp,
        created_at=datetime.now(timezone.utc),
    )
    
    db.add(otp_details)
    db.commit()
    db.refresh(otp_details)
    
    return otp

# User Authentication (checking if user exists by phone number in the users table)
async def authenticateMobile(db, phone_number):
    # Querying the 'users' table to check if the phone number exists
    user = db.query(User).filter(User.phone_number == phone_number).first()
    return user

async def authenticateUserID(db, user_id):
    # Querying the 'users' table to check if the phone number exists
    user = db.query(User).filter(User.id == user_id).first()
    return user

async def delete_account_svc(db: Session, user_id: int) -> bool:
    """
    Service to delete the user's account and all associated data.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return False
    
    # Delete related data from all associated tables

    # 1. Delete post hashtags before deleting posts
    post_ids = [post.id for post in db.query(Post).filter(Post.author_id == user_id).all()]
    if post_ids:
        db.execute(post_hashtags.delete().where(post_hashtags.c.post_id.in_(post_ids)))

    # 2. Delete user posts, comments, and likes
    db.query(Post).filter(Post.author_id == user_id).delete(synchronize_session=False)
    db.query(Comment).filter(Comment.user_id == user_id).delete(synchronize_session=False)
    db.query(Like).filter(Like.user_id == user_id).delete(synchronize_session=False)

    # 3. Delete saved posts and shared posts (sent and received)
    db.query(UserSavedPosts).filter(UserSavedPosts.user_id == user_id).delete(synchronize_session=False)
    db.query(UserSharedPosts).filter(UserSharedPosts.sender_user_id == user_id).delete(synchronize_session=False)
    db.query(UserSharedPosts).filter(UserSharedPosts.receiver_user_id == user_id).delete(synchronize_session=False)

    # 4. Delete from followers and following
    db.query(Follow).filter((Follow.follower_id == user_id) | (Follow.following_id == user_id)).delete(synchronize_session=False)

    # 5. Delete blocked users (both directions)
    db.query(BlockedUsers).filter((BlockedUsers.blocker_id == user_id) | (BlockedUsers.blocked_id == user_id)).delete(synchronize_session=False)

    # 6. Delete user activity logs
    db.query(Activity).filter(Activity.username == user.username).delete(synchronize_session=False)
    db.query(Activity).filter(Activity.username_like == user.username).delete(synchronize_session=False)
    db.query(Activity).filter(Activity.username_comment == user.username).delete(synchronize_session=False)
    db.query(Activity).filter(Activity.followed_username == user.username).delete(synchronize_session=False)

    # 7. Delete OTP entries
    db.query(OTP).filter(OTP.user_id == user_id).delete(synchronize_session=False)

    # 8. Finally, delete the user itself
    db.delete(user)
    
    # Commit changes to the database
    db.commit()

    return True


