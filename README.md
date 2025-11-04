# FastAPI MongoDB Authentication API

Backend API với FastAPI, MongoDB, Docker và Docker Compose cho đăng ký và đăng nhập.

## Cấu trúc dự án

```
BE/
├── main.py              # FastAPI application
├── database.py          # MongoDB connection
├── models.py            # MongoDB models
├── schemas.py           # Pydantic schemas
├── auth.py              # Authentication utilities (JWT, password hashing)
├── routers/
│   ├── __init__.py
│   └── auth.py          # Authentication routes
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker image configuration
├── docker-compose.yml   # Docker Compose configuration
└── README.md

```

## Cài đặt và chạy

### Sử dụng Docker Compose (Khuyến nghị)

1. Build và chạy containers:
```bash
docker-compose up --build
```

2. API sẽ chạy tại: `http://localhost:8000`

3. API Documentation: `http://localhost:8000/docs`

### Chạy local (không dùng Docker)

1. Cài đặt MongoDB local

2. Cài đặt dependencies:
```bash
pip install -r requirements.txt
```

3. Chạy server:
```bash
uvicorn main:app --reload
```

## API Endpoints

### 1. Đăng ký (Register)
- **URL**: `POST /auth/register`
- **Body**:
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```
- **Response**: 
```json
{
  "id": "user_id",
  "email": "user@example.com"
}
```

### 2. Đăng nhập (Login)
- **URL**: `POST /auth/login`
- **Body** (form-data):
  - `username`: email
  - `password`: password
- **Response**:
```json
{
  "access_token": "jwt_token",
  "token_type": "bearer"
}
```

### 3. Lấy thông tin user hiện tại
- **URL**: `GET /auth/me`
- **Headers**: `Authorization: Bearer {access_token}`
- **Response**:
```json
{
  "id": "user_id",
  "email": "user@example.com"
}
```

## Environment Variables

Có thể tạo file `.env` với các biến sau:

```
DATABASE_URL=mongodb://db:27017/fastapi_db
MONGO_DB=fastapi_db
SECRET_KEY=your-secret-key-change-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

## Database Schema

### Collection: users
- `_id`: ObjectId (auto-generated)
- `email`: String (unique, required)
- `password`: String (hashed, required)

## Công nghệ sử dụng

- **FastAPI**: Web framework
- **MongoDB**: Database
- **Motor**: Async MongoDB driver
- **JWT**: Authentication tokens
- **Bcrypt**: Password hashing
- **Docker & Docker Compose**: Containerization

