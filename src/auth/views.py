import httpx
from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from src.models.user import User
from src.auth.schemas import UserUpdate, User as UserSchema, UserCreate
from src.database import get_db
from src.auth.service import (
    get_current_user,
    update_user as update_user_svc,
    existing_user,
    create_user as create_user_svc
)
from ..config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

# signup
@router.post("/register-or-login")
async def register_or_login(user: UserCreate, db: Session = Depends(get_db)):
    """
    Handles user registration or login by integrating with Azure AD B2C OTP authentication.
    """
    # First, check if the user already exists in your local database.
    db_user = await existing_user(db, user.username, user.phone_number)
    if not db_user:
        # If user doesn't exist, redirect them to the Azure AD B2C signup page
        # This will initiate the registration process via OTP
        # Here we redirect them to the appropriate Azure AD B2C signup URL
        db_user = await create_user_svc(db, user)
        azure_signup_url = (
            f"https://{Settings.TENANT_NAME}.b2clogin.com/{Settings.TENANT_NAME}"
            f".onmicrosoft.com/{Settings.B2C_POLICY}/oauth2/v2.0/authorize?"
            f"client_id={Settings.CLIENT_ID}&response_type=code&redirect_uri={Settings.REDIRECT_URI}"
            f"&response_mode=query&scope=openid&state=12345&nonce=67890"
        )
        return RedirectResponse(url=azure_signup_url)

    # If the user exists, handle the login via OTP using Azure AD B2C
    # This is where you call the Azure AD B2C login flow (for OTP verification)
    # You can initiate the login by sending them to the login page of Azure AD B2C.
    
    azure_login_url = (
        f"https://{Settings.TENANT_NAME}.b2clogin.com/{Settings.TENANT_NAME}"
        f".onmicrosoft.com/{Settings.B2C_POLICY}/oauth2/v2.0/authorize?"
        f"client_id={Settings.CLIENT_ID}&response_type=code&redirect_uri={Settings.REDIRECT_URI}"
        f"&response_mode=query&scope=openid&state=12345&nonce=67890"
    )
    return RedirectResponse(url=azure_login_url)

@router.get("/callback")
async def auth_callback(code: str):
    """
    This route handles the callback from Azure AD B2C after OTP validation.
    It exchanges the 'code' for an access token and logs in the user.
    """
    # Now use the code to get the access token from Azure AD B2C
    token_url = "https://login.microsoftonline.com/{}/oauth2/v2.0/token".format(Settings.TENANT_NAME)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    payload = {
        "client_id": Settings.CLIENT_ID,
        "client_secret": Settings.CLIENT_SECRET,
        "code": code,
        "redirect_uri": Settings.REDIRECT_URI,
        "grant_type": "authorization_code"
    }
    
    # Make an HTTP POST request to exchange the code for an access token
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, headers=headers, data=payload)
        
    # Handle the response, extracting the access token
    if response.status_code == 200:
        access_token = response.json().get("access_token")
        
        # Now, you can use the access token (JWT) to fetch user info or log the user in
        return {"message": "User logged in successfully", "access_token": access_token}
    else:
        raise HTTPException(status_code=400, detail="Failed to get token")

@router.get("/protected-route", status_code=status.HTTP_200_OK)
async def protected_route(user: dict = Depends(get_current_user)):
    return {"message": "Authenticated!", "user": user}


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
