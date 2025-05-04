from os import stat
from jwt import PyJWKClient
import requests
import json
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import BigInteger, and_, desc
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from datetime import timedelta, datetime, timezone
from src.database import get_db
from ..models.user import User, BlockedUsers, OTP, Follow, UserDevice, FollowRequest, UserDeviceContact
from ..models.post import Post, Like, Comment, UserSavedPosts, UserSharedPosts, post_hashtags,MediaInteraction
from ..models.report import ReportUser
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
    db_user.email = user_update.email or db_user.email
    db_user.location = user_update.location or db_user.location
    db_user.account_type = user_update.account_type or db_user.account_type
    db_user.profile_pic = user_update.profile_pic or db_user.profile_pic
    db_user.username = user_update.username or db_user.username

    db.commit()
    db.refresh(db_user)  # Refresh the user instance to get updated data
    return db.query(User).filter(User.id == db_user.id).first()

async def block_user_svc(db, blocker_id, blocked_id):
    blocker = db.query(User).filter(User.id == blocker_id).first()
    blocked = db.query(User).filter(User.id == blocked_id).first()
    
    if not blocker or not blocked:
        raise ValueError("Invalid blocker or blocked user ID")
    
    # Check if already blocked
    if db.query(BlockedUsers).filter_by(blocker_id=blocker_id, blocked_id=blocked_id).first():
        return False

    # Remove follow relationship if exists
    follow = db.query(Follow).filter(
        ((Follow.follower_id == blocker_id) & (Follow.following_id == blocked_id)) |
        ((Follow.follower_id == blocked_id) & (Follow.following_id == blocker_id))
    ).all()
    
    # ✅ 1. Delete mutual follow relationships
    db.query(Follow).filter(
        ((Follow.follower_id == blocker_id) & (Follow.following_id == blocked_id)) |
        ((Follow.follower_id == blocked_id) & (Follow.following_id == blocker_id))
    ).delete(synchronize_session=False)

    # ✅ 2. Delete any pending follow requests (in either direction)
    db.query(FollowRequest).filter(
        ((FollowRequest.requester_id == blocker_id) & (FollowRequest.target_id == blocked_id)) |
        ((FollowRequest.requester_id == blocked_id) & (FollowRequest.target_id == blocker_id))
    ).delete(synchronize_session=False)

    for f in follow:
        # Adjust follower/following counts
        if f.follower_id == blocker_id:
            blocker.following_count -= 1
            blocked.followers_count -= 1
        else:
            blocked.following_count -= 1
            blocker.followers_count -= 1
        db.delete(f)

    # Add the block
    db.add(BlockedUsers(blocker_id=blocker_id, blocked_id=blocked_id))
    db.commit()
    
    # Return True to indicate the user has been successfully blocked
    return True

async def unblock_user_svc(db: Session, blocker_id: int, blocked_id: int):
    existing_block = db.query(BlockedUsers).filter_by(
        blocker_id=blocker_id,
        blocked_id=blocked_id
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
    # Fetch the user and the associated device data
    user = await get_user_from_user_id(db, user_id)
    
    if user:
        # Get the device information from the UserDevice table
        user_devices = db.query(UserDevice).filter(UserDevice.user_id == user_id).all()
        
        if not user_devices:
            print(f"No devices found for user_id {user_id}")
            return

        for device in user_devices:
            if device.device_token and device.platform:
            
            # Send the notification if both device_token and platform are available\
                try:
                    await send_push_notification(
                        device_token=device.device_token,
                        platform=device.platform,
                        title=title,
                        message=message
                    )
                except Exception as e:
                    print(f"Failed to send notification to device {device.device_id}: {e}")
            else:
                print(f"Missing device_token/platform for device_id {device.device_id}")

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
import logging

logger = logging.getLogger(__name__)

async def delete_account_svc(db: Session, user_id: int) -> bool:
    try:
        # Fetch the user
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False

        # 1. Fetch post IDs authored by the user
        post_ids = [post.id for post in db.query(Post.id).filter(Post.author_id == user_id).all()]

        if post_ids:
            # 2. Delete media interactions related to the user's posts
            db.query(MediaInteraction).filter(MediaInteraction.post_id.in_(post_ids)).delete(synchronize_session=False)

            # 3. Delete likes associated with the user's posts
            db.query(Like).filter(Like.post_id.in_(post_ids)).delete(synchronize_session=False)

            # 4. Delete comments associated with the user's posts
            db.query(Comment).filter(Comment.post_id.in_(post_ids)).delete(synchronize_session=False)

            # 5. Delete post hashtags associated with the user's posts
            db.execute(post_hashtags.delete().where(post_hashtags.c.post_id.in_(post_ids)))

            # 6. Delete the user's posts
            db.query(Post).filter(Post.id.in_(post_ids)).delete(synchronize_session=False)

        # 7. Delete likes made by the user
        db.query(Like).filter(Like.user_id == user_id).delete(synchronize_session=False)

        # 8. Delete comments authored by the user
        db.query(Comment).filter(Comment.user_id == user_id).delete(synchronize_session=False)

        # 9. Delete saved and shared posts (sent and received)
        db.query(UserSavedPosts).filter(UserSavedPosts.user_id == user_id).delete(synchronize_session=False)
        db.query(UserSharedPosts).filter(UserSharedPosts.sender_user_id == user_id).delete(synchronize_session=False)
        db.query(UserSharedPosts).filter(UserSharedPosts.receiver_user_id == user_id).delete(synchronize_session=False)

        # 10. Delete followers and following relationships
        db.query(Follow).filter((Follow.follower_id == user_id) | (Follow.following_id == user_id)).delete(synchronize_session=False)

        # 11. Delete blocked users (both directions)
        db.query(BlockedUsers).filter((BlockedUsers.blocker_id == user_id) | (BlockedUsers.blocked_id == user_id)).delete(synchronize_session=False)

        # 12. Delete activity logs
        db.query(Activity).filter(Activity.username == user.username).delete(synchronize_session=False)
        db.query(Activity).filter(Activity.username_like == user.username).delete(synchronize_session=False)
        db.query(Activity).filter(Activity.username_comment == user.username).delete(synchronize_session=False)
        db.query(Activity).filter(Activity.followed_username == user.username).delete(synchronize_session=False)

        # 13. Delete OTP entries
        db.query(OTP).filter(OTP.user_id == user_id).delete(synchronize_session=False)

        # 14. Delete reports where the user is the reporter
        db.query(ReportUser).filter(ReportUser.reported_by == user_id).delete(synchronize_session=False)

        # 15. Delete reports where the user is the reported user
        db.query(ReportUser).filter(ReportUser.user_id == user_id).delete(synchronize_session=False)
        
        #16. Delete follow requests associated with that user
        db.query(FollowRequest).filter((FollowRequest.requester_id == user_id) | (FollowRequest.target_id == user_id)).delete(synchronize_session=False)
        
        #17. Delete all UserDeviceContact records associated with a specific user_id
        db.query(UserDeviceContact).filter(UserDeviceContact.user_device_id == user_id).delete(synchronize_session=False)

        # 18. Finally, delete the user itself
        db.delete(user)

        # Commit changes to the database
        db.commit()

        return True

    except Exception as e:
        db.rollback()  # Rollback if there's an error
        logger.exception(f"Error deleting account for user_id {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting the account: {str(e)}"
        )


async def update_device_token_svc(user_id: int, device_id: str, device_token: str, platform: str, db: Session):
    try:
        # Check for existing device using only device_id
        existing_device = db.query(UserDevice).filter(UserDevice.device_id == device_id).first()

        if existing_device:
            # Update the device's user_id and token if necessary
            existing_device.user_id = user_id
            existing_device.device_token = device_token
            existing_device.platform = platform.lower()
            db.commit()
            db.refresh(existing_device)
            return {"message": "Device token updated successfully!"}
        else:
            # Add a new device record
            new_device = UserDevice(
                user_id=user_id,
                device_id=device_id,
                device_token=device_token,
                platform=platform.lower(),
                notify_likes=True,
                notify_comments=True,
                notify_share=True,
                notify_calls=True,
                notify_messages=True,
                notify_follow=True,
                notify_posts=True,
                notify_status=True,
                sync_contacts=False,
            )
            db.add(new_device)
            db.commit()
            db.refresh(new_device)
            return {"message": "Device added successfully!"}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update device token: {str(e)}"
        )

async def optional_current_user(request: Request) -> Optional[User]:
    try:
        return await get_current_user(request)
    except:
        return None



# updated login--------------------------------------------------
# List of country prefixes
country_prefixes = [
    "1242", "1246", "1264", "1268", "1340", "1345", "1441", "1473", "1649", "1664", "1671",
    "1684", "1758", "1767", "1784", "1787", "1809", "1868", "1869", "1876", "211", "213", "216",
    "220", "221", "222", "224", "225", "226", "227", "228", "229", "231", "232", "235", "237",
    "238", "239", "240", "241", "242", "243", "244", "245", "248", "249", "250", "252", "2538",
    "257", "258", "260", "262", "263", "264", "265", "266", "267", "268", "269", "26920", "27",
    "291", "297", "298", "299", "30", "31", "32", "33", "34", "350", "351", "352", "353", "354",
    "357", "36", "372", "373", "376", "378", "380", "382", "383", "385", "387", "39", "40", "41",
    "420", "43", "47", "49", "500", "501", "502", "503", "504", "505", "506", "507", "508", "51",
    "52", "53", "54", "55", "56", "57", "590", "591", "592", "593", "594", "595", "598", "599",
    "60", "64", "670", "673", "674", "675", "676", "677", "678", "679", "680", "682", "683", "684",
    "685", "686", "687", "689", "691", "692", "81", "82", "852", "853", "855", "856", "886", "91",
    "93", "960", "962", "963", "967", "972", "973", "975", "976", "992", "994", "995", "996", "509"
]

def check_country_code(phone_number):
    return any(str(phone_number).startswith(prefix) for prefix in country_prefixes)

# OTP function to store OTP in the database
async def otp_function(db, user_id, phone_number):
    if check_country_code(phone_number):
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