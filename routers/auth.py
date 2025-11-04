from fastapi import APIRouter, Depends, HTTPException, status
from datetime import timedelta
from database import get_database
from schemas import UserCreate, UserResponse, Token, UserLogin
from auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    get_current_user
)
router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate):
    """API đăng ký user mới"""
    db = get_database()
    
    # Kiểm tra email đã tồn tại chưa
    existing_user = await db.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được sử dụng"
        )
    
    # Hash password
    hashed_password = get_password_hash(user_data.password)
    
    # Tạo user mới
    user_dict = {
        "email": user_data.email,
        "password": hashed_password
    }
    
    result = await db.users.insert_one(user_dict)
    user_dict["_id"] = result.inserted_id
    
    # Trả về user (không có password)
    return UserResponse(id=str(user_dict["_id"]), email=user_dict["email"])

@router.post("/login", response_model=Token)
async def login(user_data: UserLogin):
    """API đăng nhập"""
    db = get_database()
    
    # Tìm user theo email
    user = await db.users.find_one({"email": user_data.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Kiểm tra password
    if not verify_password(user_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Tạo access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["email"]}, expires_delta=access_token_expires
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user_email: str = Depends(get_current_user)):
    """Lấy thông tin user hiện tại"""
    db = get_database()
    user = await db.users.find_one({"email": current_user_email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User không tìm thấy"
        )
    return UserResponse(id=str(user["_id"]), email=user["email"])

