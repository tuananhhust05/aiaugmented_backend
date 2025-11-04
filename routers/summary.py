from fastapi import APIRouter, Depends, HTTPException, status, Query
from database import get_database
from auth import get_current_user_id
from groq import Groq
from schemas import GroqChatResponse
from bson import ObjectId
import os
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/summary", tags=["summary"])

# Groq API Key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

# Model cho tổng hợp
SUMMARY_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"

def estimate_tokens(text: str) -> int:
    """
    Ước lượng số token từ text
    Quy tắc: 1 token ≈ 4 ký tự (tiếng Việt có thể nhiều hơn một chút)
    """
    return len(text) // 3  # Ước lượng an toàn hơn cho tiếng Việt

def truncate_to_token_limit(text: str, max_tokens: int = 6000) -> str:
    """
    Cắt text để không vượt quá max_tokens
    """
    current_tokens = estimate_tokens(text)
    if current_tokens <= max_tokens:
        return text
    
    # Tính số ký tự tương ứng với max_tokens
    max_chars = max_tokens * 3
    # Cắt và thêm dấu ...
    truncated = text[:max_chars - 3] + "..."
    return truncated

@router.post("/workspace/{workspace_id}", response_model=GroqChatResponse)
async def summarize_workspace(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    API tổng hợp: Lấy tin nhắn cuối cùng của các node trong workspace,
    gom lại và gọi Groq để tổng hợp thành báo cáo
    """
    db = get_database()
    
    # Kiểm tra Groq API Key
    if not groq_client:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="GROQ_API_KEY chưa được cấu hình"
        )
    
    # Kiểm tra workspace_id hợp lệ
    if not ObjectId.is_valid(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace ID không hợp lệ"
        )
    
    # Kiểm tra workspace tồn tại và thuộc về user
    workspace = await db.workspaces.find_one({
        "_id": ObjectId(workspace_id),
        "user_id": user_id
    })
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace không tìm thấy"
        )
    
    # Lấy tất cả nodes của workspace, sắp xếp theo _id
    nodes = await db.nodes.find({
        "workspace_id": workspace_id,
        "user_id": user_id
    }).sort("_id", 1).to_list(length=1000)
    
    if not nodes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy node nào trong workspace này"
        )
    
    # Lấy tin nhắn cuối cùng của mỗi node
    messages_data = []
    for node in nodes:
        # Lấy tin nhắn cuối cùng (sắp xếp theo _id giảm dần, lấy 1)
        last_message = await db.messages.find_one(
            {"node_id": str(node["_id"])},
            sort=[("_id", -1)]  # Sắp xếp giảm dần để lấy tin nhắn mới nhất
        )
        
        if last_message:
            messages_data.append({
                "node_name": node.get("name", ""),
                "node_id": str(node["_id"]),
                "model_id": node.get("model_id", "1"),
                "sender": last_message.get("sender", ""),
                "content": last_message.get("content", "")
            })
    
    if not messages_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tin nhắn nào trong các node"
        )
    
    # Combine messages content into one text (English labels)
    workspace_name = workspace.get("name", "Workspace")
    combined_content = f"Workspace: {workspace_name}\n\n"
    combined_content += "=" * 80 + "\n\n"
    
    for idx, msg in enumerate(messages_data, 1):
        combined_content += f"=== Conversation {idx}: {msg['node_name']} ===\n"
        combined_content += f"Model ID: {msg['model_id']}\n"
        combined_content += f"Sender: {msg['sender']}\n"
        combined_content += f"Content:\n{msg['content']}\n"
        combined_content += "\n" + "-" * 80 + "\n\n"
    
    # Giới hạn 6000 token
    truncated_content = truncate_to_token_limit(combined_content, max_tokens=6000)
    
    # Design prompt to synthesize into structured report (English)
    prompt = f"""You are an expert analyst and information synthesizer. Your task is to analyze the following conversations and create a well-structured summary report.

Input data:
{truncated_content}

Requirements:
1. Analyze and synthesize content from all conversations
2. Create a structured report with the following sections:
   - Executive Summary
   - Key Points Discussed
   - Conclusions and Recommendations (if any)
3. Divide into clear, readable points
4. Use markdown format for presentation
5. Preserve the meaning and context of the original conversations

Please create the summary report:"""
    
    # Log the prompt for debugging
    logger.info("=" * 80)
    logger.info("GROQ API REQUEST - Summary Workspace")
    logger.info("=" * 80)
    logger.info(f"Workspace ID: {workspace_id}")
    logger.info(f"Number of nodes: {len(nodes)}")
    logger.info(f"Number of messages: {len(messages_data)}")
    logger.info(f"Estimated input tokens: {estimate_tokens(truncated_content)}")
    logger.info(f"Model: {SUMMARY_MODEL}")
    logger.info(f"Prompt length: {len(prompt)} characters")
    logger.info("-" * 80)
    logger.info("FULL PROMPT SENT TO GROQ:")
    logger.info("-" * 80)
    logger.info(prompt)
    logger.info("=" * 80)
    
    try:
        # Prepare request data
        request_data = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "model": SUMMARY_MODEL,
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        # Log request data
        logger.info("GROQ API REQUEST DATA:")
        logger.info(f"Model: {request_data['model']}")
        logger.info(f"Temperature: {request_data['temperature']}")
        logger.info(f"Max tokens: {request_data['max_tokens']}")
        logger.info(f"Messages count: {len(request_data['messages'])}")
        
        # Call Groq API
        chat_completion = groq_client.chat.completions.create(**request_data)
        
        # Get response
        response_content = chat_completion.choices[0].message.content
        
        # Log response for debugging
        logger.info("=" * 80)
        logger.info("GROQ API RESPONSE - Summary Workspace")
        logger.info("=" * 80)
        logger.info(f"Response length: {len(response_content)} characters")
        logger.info(f"Estimated response tokens: {estimate_tokens(response_content)}")
        logger.info("-" * 80)
        logger.info("FULL RESPONSE FROM GROQ:")
        logger.info("-" * 80)
        logger.info(response_content)
        logger.info("=" * 80)
        
        return GroqChatResponse(
            model_id="1",  # Model ID của Orchestrator
            model_name="Orchestrator (Chief of Staff) - Summary Report",
            response=response_content
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi gọi Groq API: {str(e)}"
        )

