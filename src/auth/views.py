from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from src.models.user import User
from src.auth.schemas import UserUpdate, User as UserSchema, UserCreate, UserIdRequest, DeviceTokenRequest
from src.database import get_db


from src.auth.service import (
    get_current_user,
    authenticate,
    update_user as update_user_svc,
    existing_user,
    create_user as create_user_svc,
    create_access_token,
    block_user_svc,
    unblock_user_svc,
    get_blocked_users_svc
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

    # Update device token and platform
    user.device_token = request.device_token
    user.platform = request.platform.lower()

    db.add(user)
    db.commit()
    db.refresh(user)

    return {"message": "Device token updated successfully!"}

@router.get("/profile", status_code=status.HTTP_200_OK, response_model=UserSchema)
async def profile(current_user: User = Depends(get_current_user)):
    return current_user


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
async def update_profile(user_update: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    updated_user = await update_user_svc(db, current_user, user_update)
    return jsonable_encoder(updated_user)

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
    if current_user.id == request.user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="You cannot block yourself"
        )
    
    blocked = await block_user_svc(db, current_user.id, request.user_id)
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
    unblocked = await unblock_user_svc(db, current_user.id, request.user_id)
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
