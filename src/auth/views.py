from fastapi import APIRouter, Depends, status, HTTPException, Form, UploadFile, File
from azure.core.exceptions import ResourceNotFoundError
from urllib.parse import urlparse, unquote, quote
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func ,literal_column, union_all
from src.models.user import User, OTP, UserDevice, UserDeviceContact, Follow,BlockedUsers
from src.auth.schemas import UserUpdate, User as UserSchema, UserCreate, UserIdRequest, DeviceTokenRequest, UpdateNotificationFlagsRequest, ToggleContactsSyncRequest, ContactIn
from src.database import get_db
from typing import List
from datetime import timedelta, datetime, timezone
from .enums import AccountTypeEnum, GenderEnum
from ..azure_blob import upload_to_azure_blob,blob_service_client, AZURE_IMAGE_CONTAINER

from src.auth.service import (
    get_current_user,
    authenticate,
    update_user as update_user_svc,
    existing_user,
    create_user as create_user_svc,
    create_access_token,
    block_user_svc,
    unblock_user_svc,
    get_blocked_users_svc,
    generate_otp,
    authenticateMobile,
    authenticateUserID,
    otp_function,
    send_sms,
    delete_account_svc,
    update_device_token_svc
)
from ..config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

# signup
# signup
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    db_user = await existing_user(db, user.username, user.phone_number)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already registered",
        )    
    # create user if user doesn't exist 
    db_user = await create_user_svc(db, user)
    return {"message": "User is successfully registered."}



@router.post("/login", status_code=status.HTTP_201_CREATED)
async def login(user: UserCreate, db: Session = Depends(get_db)):
    db_user = await authenticate(db, user.username, user.phone_number)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or phone number",
        )
    
    access_token = await create_access_token(db_user.username, db_user.id)
    return {"access_token": access_token, "token_type": "bearer", "user_id": db_user.id}

@router.post("/update-device-token")
async def update_device_token(request: DeviceTokenRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = current_user
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")

    # Call the service layer to update or add the device token
    result = await update_device_token_svc(user.id, request.device_id, request.device_token, request.platform, db)
    
    return result

@router.get("/profile", status_code=status.HTTP_200_OK, response_model=UserSchema)
async def profile(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # Get list of user IDs the current user is following
        following_ids = db.query(Follow.following_id).filter(Follow.follower_id == current_user.id).all()
        following_ids = [fid[0] for fid in following_ids]

         # Subquery to get IDs of users who are blocked by or have blocked the current user
        blocked_users_subq = (
            db.query(BlockedUsers.blocked_id)
            .filter(BlockedUsers.blocker_id == current_user.id)
            .union(
                db.query(BlockedUsers.blocker_id)
                .filter(BlockedUsers.blocked_id == current_user.id)
            )
            .subquery()
        )

        # Friends-of-Friends (second-degree) - return user_id
        second_degree_subq = (
            db.query(Follow.following_id.label("user_id"))
            .filter(
                Follow.follower_id.in_(following_ids),
                Follow.following_id != current_user.id,
                ~Follow.following_id.in_(following_ids),
                ~Follow.following_id.in_(blocked_users_subq)
            )
        )

        # Users who follow current_user but are not followed back - return user_id
        followers_not_followed_back_subq = (
            db.query(Follow.follower_id.label("user_id"))
            .filter(
                Follow.following_id == current_user.id,
                ~Follow.follower_id.in_(following_ids),
                Follow.follower_id != current_user.id
            )
        )

        # Combine the two with UNION and count distinct user_id
        union_subq = second_degree_subq.union(followers_not_followed_back_subq).subquery()
        suggested_follower_count = db.query(func.count(func.distinct(union_subq.c.user_id))).scalar()

        return {
            **current_user.__dict__,
            "suggested_follower_count": suggested_follower_count
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching profile: {str(e)}")


# @router.put("/profile", status_code=status.HTTP_204_NO_CONTENT)
# async def update_profile(
#     token: str, user_update: UserUpdate, db: Session = Depends(get_db)
# ):
#     db_user = await get_current_user(db, token)
#     if not db_user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid"
#         )
    
#     await update_user_svc(db, db_user, user_update)
#     return {"message": "Profile updated successfully."}

@router.put("/profile")
async def update_profile(
    name: str = Form(None),
    bio: str = Form(None),
    dob: str = Form(None),
    email: str = Form(None),
    gender: GenderEnum = Form(None),
    location: str = Form(None),
    account_type: AccountTypeEnum = Form(None),
    profile_pic: UploadFile = File(None),  # Accept profile picture
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    # Create a UserUpdate object
    user_update = UserUpdate(
        username=current_user.username,
        name=name,
        bio=bio,
        dob=dob,
        email = email,
        gender=gender,
        location=location,
        account_type= account_type
    )

    # Check if a new profile pic is uploaded
    if profile_pic:
        # Upload to Azure and get the URL
        new_profile_pic_url, media_type, thumbnail_url = await upload_to_azure_blob(
            profile_pic, current_user.username, str(current_user.id)
        )
        # Set new profile pic URL to update
        user_update.profile_pic = new_profile_pic_url

    # Call the update service
    updated_user = await update_user_svc(db, current_user, user_update)
    return jsonable_encoder(updated_user)

#Removing profile picture from the profile
@router.put("/profile/remove-profile-pic", status_code=200)
async def remove_profile_pic(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not current_user.profile_pic:
        raise HTTPException(status_code=400, detail="No profile picture found to remove.")

    try:
        parsed_url = urlparse(current_user.profile_pic)
        blob_path = parsed_url.path.lstrip('/') 

        container_client = blob_service_client.get_container_client(AZURE_IMAGE_CONTAINER)
        blob_client = container_client.get_blob_client(blob_path)

        try:
            blob_client.delete_blob()
        except ResourceNotFoundError:
            pass  

        current_user.profile_pic = ""
        db.commit()
        db.refresh(current_user)

        return {
            "message": "Profile picture removed from profile.",
            "profile_pic": current_user.profile_pic
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while removing the profile picture: {str(e)}"
        )


# @router.post("/request-password-reset", status_code=status.HTTP_200_OK)
# async def request_password_reset(request: ResetPasswordRequest, db: Session = Depends(get_db)):
#     db_user = db.query(User).filter(User.phone_number == request.phone_number).first()
#     if not db_user:
#         raise HTTPException(status_code=404, detail="User not found.")

#     # Generate and send OTP
#     otp = generate_otp()
#     send_otp_via_sms(request.phone_number, otp)

#     # Store OTP in database
#     db_user.otp = otp
#     db.commit()
#     db.refresh(db_user)

#     return {"message": "Password reset OTP sent successfully."}


# @router.post("/verify-reset-password", status_code=status.HTTP_200_OK)
# async def verify_reset_password(request: ResetPasswordVerify, db: Session = Depends(get_db)):
#     db_user = db.query(User).filter(User.phone_number == request.phone_number).first()
#     if not db_user:
#         raise HTTPException(status_code=404, detail="User not found.")

#     if db_user.otp != request.otp:
#         raise HTTPException(status_code=400, detail="Invalid OTP.")

#     # Hash new password and update user record
#     hashed_password = hash_password(request.new_password)
#     db_user.password = hashed_password
#     db_user.otp = None  # Clear OTP after reset
#     db.commit()
#     db.refresh(db_user)

#     return {"message": "Password reset successful. You can now log in with your new password."}

@router.post("/block", status_code=status.HTTP_200_OK)
async def block_user(
    request: UserIdRequest, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Block a user by adding an entry to the blocked_users table.
    """
    if current_user.id == request.user_id or current_user.username == request.username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="You cannot block yourself"
        )
    
    blocked = await block_user_svc(db, current_user.id, request)
    if blocked:
        return {"message": "User successfully blocked"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already blocked"
        )

@router.post("/unblock", status_code=status.HTTP_200_OK)
async def unblock_user(
    request: UserIdRequest, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Unblock a user by removing the entry from the blocked_users table.
    """
    unblocked = await unblock_user_svc(db, current_user.id, request)
    if unblocked:
        return {"message": "User successfully unblocked"}
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not blocked"
        )

@router.get("/blocked-users", status_code=status.HTTP_200_OK)
async def get_blocked_users(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Fetch the list of users blocked by the current user.
    """
    blocked_users = await get_blocked_users_svc(db, current_user.id)
    return jsonable_encoder(blocked_users)

@router.post("/logout")
async def logout(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    user = current_user
    user.device_token = None
    db.add(user)
    db.commit()
    return {"message": "Logged out successfully!"}

# send otp endpoint
@router.post("/send-otp", status_code=status.HTTP_200_OK)
async def send_otp(user: UserUpdate, db: Session = Depends(get_db)):
    # Check if user exists in the database (based on phone number in 'users' table)
    db_user = await authenticateMobile(db, user.phone_number)
    
    if db_user:
        # If user exists, generate OTP for the existing user and send it
        otp_value = await otp_function(db, db_user.id, user.phone_number)
        sms_status = await send_sms(user.phone_number, otp_value)
        
        if sms_status:
            return {"message": "OTP sent successfully", "user_id": db_user.id}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Mobile number not registered",
        )

# verify otp endpoint
@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp(user_id: int = Form(...), otp: str = Form(...), db: Session = Depends(get_db)):
    otp_record = db.query(OTP).filter(OTP.user_id == user_id, OTP.otp == otp).order_by(OTP.created_at.desc()).first()

    # Check if OTP exists
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )

    # Handle naive datetime properly
    if otp_record.created_at.tzinfo is None:
        created_at_aware = otp_record.created_at.replace(tzinfo=timezone.utc)
    else:
        created_at_aware = otp_record.created_at

    # Check OTP expiry
    if datetime.now(timezone.utc) > created_at_aware + timedelta(minutes=5):
        # Optionally, you can delete expired OTPs here, or leave them in the DB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired",
        )
    
    db_user = await authenticateUserID(db, user_id)
    if db_user.username and db_user.username != "":
        # Generate access token if username exists and is not empty
        access_token = await create_access_token(db_user.username, user_id)
        return {
            "message": "OTP verified successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_id
            }
    else:
        # Handle case when username is missing or empty
         return {
            "message": "OTP verified successfully",
            "user": db_user,
            "user_id": user_id
            }
    
#  update profile first time login
@router.put("/user_profile")
async def update_profile(user_update: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated_user = await update_user_svc(db, current_user, user_update)
    if updated_user.username and updated_user.username != "":
        access_token = await create_access_token(updated_user.username, updated_user.id)
        return {
            "message": "Profile updated successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": updated_user.id
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is missing or invalid"
        )

@router.delete("/delete-account", status_code=status.HTTP_200_OK)
async def delete_account(
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    """
    Delete the current user's account and all associated data.
    """
    try:
        deleted = await delete_account_svc(db, current_user.id)

        if deleted:
            return {"message": "Account and all related data deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to delete account or account not found"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while deleting the account: {str(e)}"
        )
        
@router.post("/device/notification-settings")
async def update_notification_flags(
    request: UpdateNotificationFlagsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    device = db.query(UserDevice).filter(
        UserDevice.user_id == current_user.id,
        UserDevice.device_id == request.device_id
    ).first()

    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Update only provided fields
    for field, value in request.dict(exclude_unset=True).items():
        if field != "device_id":
            setattr(device, field, value)

    db.commit()
    db.refresh(device)
    return {"message": "Notification settings updated successfully"}

@router.post("/contacts/sync")
def toggle_sync_contacts(request: ToggleContactsSyncRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    user_device = db.query(UserDevice).filter_by(device_id=request.device_id, user_id=current_user.id).first()
    if not user_device:
        raise HTTPException(status_code=404, detail="Device not found.")

    user_device.sync_contacts = request.sync_contacts

    if request.sync_contacts:
        # Remove old contacts (if any)
        db.query(UserDeviceContact).filter_by(user_device_id=user_device.id).delete()

        # Insert new contacts
        for contact in request.contacts:
            db.add(UserDeviceContact(
                user_device_id=user_device.id,
                name=contact.name.strip(),
                phone_number=str(contact.phone_number).strip()
            ))
    else:
        # Delete all contacts if sync is disabled
        db.query(UserDeviceContact).filter_by(user_device_id=user_device.id).delete()

    db.commit()
    return {"message": f"Contacts sync {'enabled' if request.sync_contacts else 'disabled'} successfully."}

@router.get("/contacts", response_model=List[ContactIn])
def get_synced_contacts(device_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    user_device = db.query(UserDevice).filter_by(device_id=device_id, user_id=current_user.id).first()
    if not user_device:
        raise HTTPException(status_code=404, detail="Device not found.")
    contacts = db.query(UserDeviceContact).filter_by(user_device_id=user_device.id).all()
    return contacts


# updated login--------------------------------------------------

# send otp endpoint
@router.post("/app-login", status_code=status.HTTP_200_OK)
async def app_login(user: UserUpdate, db: Session = Depends(get_db)):
    # Check if user exists in the database (based on phone number in 'users' table)
    db_user = await authenticateMobile(db, user.phone_number)

    if db_user:
        # If user exists, generate OTP for the existing user and send it
        otp_value = await otp_function(db, db_user.id, user.phone_number)
        sms_status = await send_sms(user.phone_number, otp_value)

        if sms_status:
            return {"message": "OTP sent successfully", "user_id": db_user.id}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP",
            )
    else:
        # If user does not exist, insert user mobile number into the 'users' table
        new_user = User(phone_number=user.phone_number)
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Generate OTP and send SMS
        otp_value = await otp_function(db, new_user.id, user.phone_number)
        sms_status = await send_sms(user.phone_number, otp_value)

        if sms_status:
            return {"message": "OTP sent successfully", "user_id": new_user.id}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send OTP",
            )


@router.post("/verification-otp", status_code=status.HTTP_200_OK)
async def verification_otp(user_id: int = Form(...), otp: str = Form(...), db: Session = Depends(get_db)):
    otp_record = db.query(OTP).filter(OTP.user_id == user_id, OTP.otp == otp).order_by(OTP.created_at.desc()).first()

    # Check if OTP exists
    if not otp_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP",
        )

    # Handle naive datetime properly
    if otp_record.created_at.tzinfo is None:
        created_at_aware = otp_record.created_at.replace(tzinfo=timezone.utc)
    else:
        created_at_aware = otp_record.created_at

    # Check OTP expiry
    if datetime.now(timezone.utc) > created_at_aware + timedelta(minutes=5):
        # Optionally, you can delete expired OTPs here, or leave them in the DB
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP has expired",
        )

        # Delete the OTP record after successful verification
    db.delete(otp_record)
    db.commit()

    db_user = await authenticateUserID(db, user_id)
    if db_user.username and db_user.username != "":
        # Generate access token if username exists and is not empty
        access_token = await create_access_token(db_user.username, user_id)
        return {
            "message": "OTP verified successfully",
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_id,
            "user": db_user,
        }
    else:
        # Handle case when username is missing or empty
        # access_token = await create_access_token(db_user.username, user_id)
        return {
            "message": "OTP verified successfully",
            "user": db_user,
            "access_token": "",
            "token_type": "bearer",
            "user_id": user_id
        }

#  update profile first time login
@router.put("/user-profile-setup")
async def user_profile_setup(
    username: str = Form(None),
    name: str = Form(None),
    bio: str = Form(None),
    dob: str = Form(None),
    email: str = Form(None),
    gender: GenderEnum = Form(None),
    location: str = Form(None),
    account_type: AccountTypeEnum = Form(None),
    profile_pic: UploadFile = File(None),  # Accept profile picture
    user_id: int = Form(...),
    db: Session = Depends(get_db)
):
    # Fetch user from DB
    db_user = db.query(User).filter(User.id == user_id).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    # Prepare update data dictionary
    user_update_data = {
        "username": username,
        "name": name,
        "bio": bio,
        "dob": dob,
        "email": email,
        "gender": gender,
        "location": location,
        "account_type": account_type,
    }
    filtered_data = {k: v for k, v in user_update_data.items() if v is not None}
    user_update = UserUpdate(**filtered_data)

    # Handle profile picture upload
    if profile_pic:
        new_profile_pic_url, media_type, thumbnail_url = await upload_to_azure_blob(
            profile_pic, username or f"user_{db_user.id}", str(db_user.id)
        )
        user_update.profile_pic = new_profile_pic_url

    # Call the update service
    updated_user = await update_user_svc(db, db_user, user_update)

    # Generate access token
    access_token = await create_access_token(updated_user.username, updated_user.id)

    return {
        "message": "Profile updated successfully",
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": updated_user.id,
        "user":user_update_data
    }


