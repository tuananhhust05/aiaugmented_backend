from fastapi import APIRouter, HTTPException, status
from schemas import GroqChatRequest, GroqChatResponse
from groq import Groq
import os

router = APIRouter(prefix="/groq", tags=["groq"])

# Groq API Key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
print(GROQ_API_KEY, "GROQ_API_KEY")
# Initialize Groq client (will be None if API key is not set)
groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

# 6 Models được fix cứng
GROQ_MODELS = {
    "1": {
        "model": "meta-llama/llama-4-maverick-17b-128e-instruct",
        "name": "Orchestrator (Chief of Staff)",
        "description": "Tổng hợp 5 góc nhìn, nhận diện mâu thuẫn, 'reframe' quyết định"
    },
    "2": {
        "model": "moonshotai/kimi-k2-instruct",
        "name": "Market Compass",
        "description": "Phân tích tín hiệu thị trường, xu hướng, cạnh tranh"
    },
    "3": {
        "model": "openai/gpt-oss-20b",
        "name": "Financial Guardian",
        "description": "Mô phỏng dòng tiền, stress-test tài chính, logic & tính toán"
    },
    "4": {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
        "name": "Strategy Analyst",
        "description": "Framework logic, blind spot, testing assumption"
    },
    "5": {
        "model": "llama-3.3-70b-versatile",
        "name": "People Advisor",
        "description": "Tâm lý tổ chức, phản ứng con người, tone phù hợp"
    },
    "6": {
        "model": "llama-3.1-8b-instant",
        "name": "Action Architect",
        "description": "Thực thi, timeline, resource, risk realism"
    }
}

@router.get("/models")
async def get_models():
    """Lấy danh sách 6 models có sẵn"""
    models_list = []
    for model_id, model_info in GROQ_MODELS.items():
        models_list.append({
            "id": model_id,
            "name": model_info["name"],
            "model": model_info["model"],
            "description": model_info["description"]
        })
    return {"models": models_list}

@router.post("/chat", response_model=GroqChatResponse)
async def chat_with_groq(request: GroqChatRequest):
    """
    Gửi message đến Groq và nhận phản hồi
    
    model_id: 1-6 để chọn một trong 6 models
    message: Nội dung câu hỏi/input từ user
    """
    # Kiểm tra Groq API Key
    if not groq_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GROQ_API_KEY chưa được cấu hình. Vui lòng cấu hình GROQ_API_KEY trong environment variables."
        )
    
    # Kiểm tra model_id hợp lệ
    if request.model_id not in GROQ_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Model ID không hợp lệ. Vui lòng chọn từ 1-6. Bạn đã chọn: {request.model_id}"
        )
    
    model_info = GROQ_MODELS[request.model_id]
    model_name = model_info["model"]
    
    try:
        # Call Groq API
        chat_completion = groq_client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": request.message
                }
            ],
            model=model_name,
            temperature=0.7,
            max_tokens=2048
        )
        
        # Lấy response
        response_content = chat_completion.choices[0].message.content
        
        return GroqChatResponse(
            model_id=request.model_id,
            model_name=model_info["name"],
            response=response_content
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi gọi Groq API: {str(e)}"
        )

