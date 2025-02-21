from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from src.models.user import User
from src.auth.schemas import UserCreate, UserUpdate, User as UserSchema, VerifyOTPRequest, ResetPasswordRequest, ResetPasswordVerify
from src.database import get_db
from src.auth.service import (
    existing_user,
    create_access_token,
    get_current_user,
    create_user as create_user_svc,
    authenticate,
    update_user as update_user_svc,
    send_otp_via_sms, 
    generate_otp,
    verify_password, 
    hash_password
)

router = APIRouter(prefix="/auth", tags=["auth"])

# signup
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(user: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    db_user = await existing_user(db, user.username, user.phone_number)
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Phone number already registered",
        )
    
    # Hash password
    hashed_password = hash_password(user.password)
    otp = generate_otp()
    
    # Send OTP
    send_otp_via_sms(user.phone_number, otp)
    
    # Create user with OTP verification
    db_user = await create_user_svc(db, user.phone_number, hashed_password, otp)
    return {"message": "User registered successfully. OTP sent to your phone."}


@router.post("/verify-otp", status_code=status.HTTP_200_OK)
async def verify_otp(request: VerifyOTPRequest, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.phone_number == request.phone_number).first()
    if not db_user:
        raise HTTPException(status_code=400, detail="User not found.")
    
    if db_user.otp != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP.")
    
    db_user.is_verified = True
    db_user.otp = None
    db.commit()
    db.refresh(db_user)
    
    return {"message": "OTP verified successfully. User account is now active."}


@router.post("/login", status_code=status.HTTP_201_CREATED)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    db_user = await authenticate(db, form_data.username, form_data.password)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect phone number or password.",
        )
    
    if not db_user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is not verified. Please verify OTP."
        )
    
    access_token = await create_access_token(db_user.phone_number, db_user.id)
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/profile", status_code=status.HTTP_200_OK, response_model=UserSchema)
async def profile(token: str, db: Session = Depends(get_db)):
    db_user = await get_current_user(db, token)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid"
        )
    return db_user


@router.put("/profile", status_code=status.HTTP_204_NO_CONTENT)
async def update_profile(
    token: str, user_update: UserUpdate, db: Session = Depends(get_db)
):
    db_user = await get_current_user(db, token)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalid"
        )
    
    await update_user_svc(db, db_user, user_update)
    return {"message": "Profile updated successfully."}

@router.post("/request-password-reset", status_code=status.HTTP_200_OK)
async def request_password_reset(request: ResetPasswordRequest, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.phone_number == request.phone_number).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    # Generate and send OTP
    otp = generate_otp()
    send_otp_via_sms(request.phone_number, otp)

    # Store OTP in database
    db_user.otp = otp
    db.commit()
    db.refresh(db_user)

    return {"message": "Password reset OTP sent successfully."}


@router.post("/verify-reset-password", status_code=status.HTTP_200_OK)
async def verify_reset_password(request: ResetPasswordVerify, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.phone_number == request.phone_number).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found.")

    if db_user.otp != request.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP.")

    # Hash new password and update user record
    hashed_password = hash_password(request.new_password)
    db_user.password = hashed_password
    db_user.otp = None  # Clear OTP after reset
    db.commit()
    db.refresh(db_user)

    return {"message": "Password reset successful. You can now log in with your new password."}
