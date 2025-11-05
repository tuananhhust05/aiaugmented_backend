from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

# Groq Schemas
class GroqChatRequest(BaseModel):
    model_id: str  # 1-6 để chọn model
    message: str

class GroqChatResponse(BaseModel):
    model_id: str
    model_name: str
    response: str

# Summary Report Schemas
class SummarySection(BaseModel):
    title: str
    content: str
    points: list[str]

class SummaryReport(BaseModel):
    executive_summary: str
    key_points: list[str]
    sections: list[SummarySection]
    conclusions: str
    recommendations: list[str]

# Workspace Schemas
class WorkspaceCreate(BaseModel):
    name: str

class WorkspaceUpdate(BaseModel):
    name: Optional[str] = None

class WorkspaceResponse(BaseModel):
    id: str
    user_id: str
    name: str

    class Config:
        from_attributes = True

# Node Schemas
class NodeCreate(BaseModel):
    workspace_id: str
    name: str
    model_id: str  # 1-6 để chọn model từ Groq

class NodeUpdate(BaseModel):
    workspace_id: Optional[str] = None
    name: Optional[str] = None
    model_id: Optional[str] = None

class NodeResponse(BaseModel):
    id: str
    user_id: str
    workspace_id: str
    name: str
    model_id: str

    class Config:
        from_attributes = True

# Message Schemas
class MessageCreate(BaseModel):
    node_id: str
    sender: str  # "AI" hoặc "You"
    content: str

class MessageUpdate(BaseModel):
    sender: Optional[str] = None
    content: Optional[str] = None

class MessageResponse(BaseModel):
    id: str
    node_id: str
    sender: str
    content: str

    class Config:
        from_attributes = True

