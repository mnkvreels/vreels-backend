from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
from core.database import SessionLocal
from users.models import User, Profile
from core.auth import create_access_token, hash_password, verify_password, verify_jwt_token
from pydantic import BaseModel
from typing import List, Optional
from core.email_service import send_reset_email
from accounts.models import BlacklistedToken

app = FastAPI()

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    profile: Optional["Profile"]  # Forward reference

    class Config:
        arbitrary_types_allowed = True
        allow_population_by_field_name = True
        json_encoders = {
            Profile: lambda v: f'Profile {v}'
        }

class Profile(BaseModel):
    bio: Optional[str]
    profile_picture: Optional[str]

class LoginRequest(BaseModel):
    username: str
    password: str

class PasswordResetRequest(BaseModel):
    email: str

class ProfileUpdate(BaseModel):
    bio: str = None
    phone_number: str = None
    profile_picture: str = None

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/register/")
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == user.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists")

    hashed_password = hash_password(user.password)
    new_user = User(username=user.username, email=user.email, hashed_password=hashed_password, is_verified=False)
    
    db.add(new_user)
    db.commit()
    return {"message": "User registered successfully. Please verify your email."}

@app.post("/login/")
async def login_user(login: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == login.username).first()
    if not user or not verify_password(login.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

@app.post("/request-password-reset/")
async def request_password_reset(request: PasswordResetRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Email not registered")

    reset_token = create_access_token({"sub": user.email}, timedelta(minutes=15))
    await send_reset_email(user.email, reset_token)
    return {"message": "Password reset email sent"}

@app.post("/reset-password/{token}")
async def reset_password(token: str, new_password: str, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Token expired")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.hashed_password = hash_password(new_password)
    db.commit()
    return {"message": "Password updated successfully"}

@app.post("/logout/")
async def logout_user(token: str, db: Session = Depends(get_db)):
    db.add(BlacklistedToken(token=token))
    db.commit()
    return {"message": "Logged out successfully"}

@app.get("/profile/")
async def get_profile(token: str, db: Session = Depends(get_db)):
    payload = verify_jwt_token(token, db)
    user = db.query(User).filter(User.username == payload["sub"]).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()
    
    return {
        "username": user.username,
        "email": user.email,
        "bio": profile.bio if profile else None,
        "phone_number": profile.phone_number if profile else None,
        "profile_picture": profile.profile_picture if profile else None
    }

@app.put("/profile/")
async def update_profile(profile_update: ProfileUpdate, token: str, db: Session = Depends(get_db)):
    payload = verify_jwt_token(token, db)
    user = db.query(User).filter(User.username == payload["sub"]).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    profile = db.query(Profile).filter(Profile.user_id == user.id).first()

    if not profile:
        profile = Profile(user_id=user.id, bio=profile_update.bio, phone_number=profile_update.phone_number, profile_picture=profile_update.profile_picture)
        db.add(profile)
    else:
        if profile_update.bio:
            profile.bio = profile_update.bio
        if profile_update.phone_number:
            profile.phone_number = profile_update.phone_number
        if profile_update.profile_picture:
            profile.profile_picture = profile_update.profile_picture
    
    db.commit()
    return {"message": "Profile updated successfully"}
