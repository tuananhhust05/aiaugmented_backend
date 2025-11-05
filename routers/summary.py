from fastapi import APIRouter, Depends, HTTPException, status, Query
from database import get_database
from auth import get_current_user_id
from groq import Groq
from schemas import SummaryReport, SummarySection
from bson import ObjectId
import os
import logging
import json

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

def validate_json_format(json_data: dict) -> tuple[bool, str]:
    """
    Validate JSON format matches required structure
    Returns: (is_valid, error_message)
    """
    required_fields = ["executive_summary", "key_points", "sections", "conclusions", "recommendations"]
    
    # Check all required fields exist
    for field in required_fields:
        if field not in json_data:
            return False, f"Missing required field: {field}"
    
    # Validate types
    if not isinstance(json_data.get("executive_summary"), str):
        return False, "executive_summary must be a string"
    
    if not isinstance(json_data.get("key_points"), list):
        return False, "key_points must be an array"
    
    if len(json_data.get("key_points", [])) < 3:
        return False, "key_points must have at least 3 items"
    
    if not isinstance(json_data.get("sections"), list):
        return False, "sections must be an array"
    
    for i, section in enumerate(json_data.get("sections", [])):
        if not isinstance(section, dict):
            return False, f"sections[{i}] must be an object"
        if "title" not in section or "content" not in section or "points" not in section:
            return False, f"sections[{i}] must have title, content, and points"
        if not isinstance(section.get("points"), list):
            return False, f"sections[{i}].points must be an array"
    
    if not isinstance(json_data.get("conclusions"), str):
        return False, "conclusions must be a string"
    
    if not isinstance(json_data.get("recommendations"), list):
        return False, "recommendations must be an array"
    
    return True, ""

def parse_and_validate_response(response_content: str) -> tuple[dict | None, str]:
    """
    Parse JSON response and validate format
    Returns: (json_data, error_message)
    """
    try:
        # Remove markdown code blocks if present
        cleaned_response = response_content.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]  # Remove ```json
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]  # Remove ```
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]  # Remove closing ```
        cleaned_response = cleaned_response.strip()
        
        # Parse JSON
        json_data = json.loads(cleaned_response)
        
        # Validate format
        is_valid, error_msg = validate_json_format(json_data)
        if not is_valid:
            return None, error_msg
        
        return json_data, ""
        
    except json.JSONDecodeError as e:
        return None, f"JSON parsing error: {str(e)}"
    except Exception as e:
        return None, f"Error validating format: {str(e)}"

@router.post("/workspace/{workspace_id}", response_model=SummaryReport)
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
    
    def create_prompt() -> str:
        """Create prompt for Groq API (100% English)"""
        return f"""You are an expert analyst and information synthesizer. Your task is to analyze the following conversations and create a well-structured summary report in JSON format.

Input data:
{truncated_content}

Requirements:
1. Analyze and synthesize content from all conversations
2. You MUST return ONLY valid JSON, no other text before or after
3. The JSON must follow this exact structure:
{{
  "executive_summary": "A comprehensive summary of all conversations in 2-3 paragraphs",
  "key_points": [
    "Key point 1 as a string",
    "Key point 2 as a string",
    "Key point 3 as a string"
  ],
  "sections": [
    {{
      "title": "Section title",
      "content": "Section content description",
      "points": [
        "Point 1",
        "Point 2"
      ]
    }}
  ],
  "conclusions": "Main conclusions from the analysis",
  "recommendations": [
    "Recommendation 1",
    "Recommendation 2"
  ]
}}
4. All fields are required
5. "key_points" must be an array of strings (at least 3 points)
6. "sections" must be an array of objects with title, content, and points
7. "recommendations" must be an array of strings (can be empty array if no recommendations)
8. Preserve the meaning and context of the original conversations
9. Use clear, professional English language

Return ONLY the JSON object, no markdown formatting, no code blocks, just the raw JSON:"""
    
    prompt = create_prompt()
    
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
    
    # Retry logic with max 5 attempts
    max_retries = 5
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info("=" * 80)
            logger.info(f"GROQ API REQUEST - Attempt {attempt}/{max_retries}")
            logger.info("=" * 80)
            
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
            logger.info(f"GROQ API RESPONSE - Attempt {attempt}/{max_retries}")
            logger.info("=" * 80)
            logger.info(f"Response length: {len(response_content)} characters")
            logger.info(f"Estimated response tokens: {estimate_tokens(response_content)}")
            logger.info("-" * 80)
            logger.info("RAW RESPONSE FROM GROQ:")
            logger.info("-" * 80)
            logger.info(response_content)
            logger.info("=" * 80)
            
            # Parse and validate JSON response
            json_data, error_msg = parse_and_validate_response(response_content)
            
            if json_data is None:
                # Format validation failed, will retry
                last_error = error_msg
                logger.warning(f"Attempt {attempt}/{max_retries} failed: {error_msg}")
                if attempt < max_retries:
                    logger.info(f"Retrying... (attempt {attempt + 1}/{max_retries})")
                    continue
                else:
                    # Max retries reached
                    logger.error(f"All {max_retries} attempts failed. Last error: {error_msg}")
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to get valid JSON response after {max_retries} attempts. Last error: {error_msg}"
                    )
            
            # Successfully parsed and validated
            logger.info("=" * 80)
            logger.info(f"VALID JSON FORMAT - Attempt {attempt}/{max_retries}")
            logger.info("=" * 80)
            
            # Validate and normalize data structure
            summary_report = SummaryReport(
                executive_summary=str(json_data.get("executive_summary", "")),
                key_points=[str(point) for point in json_data.get("key_points", [])],
                sections=[
                    SummarySection(
                        title=str(section.get("title", "")),
                        content=str(section.get("content", "")),
                        points=[str(point) for point in section.get("points", [])]
                    )
                    for section in json_data.get("sections", [])
                ],
                conclusions=str(json_data.get("conclusions", "")),
                recommendations=[str(rec) for rec in json_data.get("recommendations", [])]
            )
            
            logger.info(f"Executive Summary: {len(summary_report.executive_summary)} chars")
            logger.info(f"Key Points: {len(summary_report.key_points)} items")
            logger.info(f"Sections: {len(summary_report.sections)} items")
            logger.info(f"Recommendations: {len(summary_report.recommendations)} items")
            logger.info("=" * 80)
            
            return summary_report
            
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            last_error = str(e)
            logger.error(f"Attempt {attempt}/{max_retries} error: {str(e)}")
            if attempt < max_retries:
                logger.info(f"Retrying... (attempt {attempt + 1}/{max_retries})")
                continue
            else:
                # Max retries reached
                logger.error(f"All {max_retries} attempts failed. Last error: {last_error}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error calling Groq API after {max_retries} attempts: {last_error}"
                )

