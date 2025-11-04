from fastapi import APIRouter, Depends, HTTPException, status, Query
from database import get_database
from schemas import MessageCreate, MessageUpdate, MessageResponse
from auth import get_current_user_id
from bson import ObjectId

router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def create_message(
    message_data: MessageCreate,
    user_id: str = Depends(get_current_user_id)
):
    """Tạo message mới"""
    db = get_database()
    
    # Kiểm tra sender hợp lệ
    if message_data.sender not in ["AI", "You"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sender phải là 'AI' hoặc 'You'"
        )
    
    # Kiểm tra node tồn tại và thuộc về user
    if not ObjectId.is_valid(message_data.node_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node ID không hợp lệ"
        )
    
    node = await db.nodes.find_one({
        "_id": ObjectId(message_data.node_id),
        "user_id": user_id
    })
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node không tìm thấy"
        )
    
    message_dict = {
        "node_id": message_data.node_id,
        "sender": message_data.sender,
        "content": message_data.content
    }
    
    result = await db.messages.insert_one(message_dict)
    
    return MessageResponse(
        id=str(result.inserted_id),
        node_id=message_dict["node_id"],
        sender=message_dict["sender"],
        content=message_dict["content"]
    )

@router.get("", response_model=list[MessageResponse])
async def get_messages(
    node_id: str = Query(None, description="Lọc theo node_id"),
    user_id: str = Depends(get_current_user_id)
):
    """Lấy danh sách messages. Có thể lọc theo node_id"""
    db = get_database()
    
    query = {}
    if node_id:
        # Kiểm tra node tồn tại và thuộc về user
        if not ObjectId.is_valid(node_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Node ID không hợp lệ"
            )
        node = await db.nodes.find_one({
            "_id": ObjectId(node_id),
            "user_id": user_id
        })
        if not node:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Node không tìm thấy"
            )
        query["node_id"] = node_id
    
    messages = await db.messages.find(query).to_list(length=1000)
    
    return [
        MessageResponse(
            id=str(msg["_id"]),
            node_id=msg["node_id"],
            sender=msg["sender"],
            content=msg["content"]
        )
        for msg in messages
    ]

@router.get("/{message_id}", response_model=MessageResponse)
async def get_message(
    message_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Lấy thông tin message theo ID"""
    db = get_database()
    
    if not ObjectId.is_valid(message_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message ID không hợp lệ"
        )
    
    message = await db.messages.find_one({"_id": ObjectId(message_id)})
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message không tìm thấy"
        )
    
    # Kiểm tra node thuộc về user
    if not ObjectId.is_valid(message["node_id"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node ID không hợp lệ"
        )
    
    node = await db.nodes.find_one({
        "_id": ObjectId(message["node_id"]),
        "user_id": user_id
    })
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập message này"
        )
    
    return MessageResponse(
        id=str(message["_id"]),
        node_id=message["node_id"],
        sender=message["sender"],
        content=message["content"]
    )

@router.put("/{message_id}", response_model=MessageResponse)
async def update_message(
    message_id: str,
    message_data: MessageUpdate,
    user_id: str = Depends(get_current_user_id)
):
    """Cập nhật message"""
    db = get_database()
    
    if not ObjectId.is_valid(message_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message ID không hợp lệ"
        )
    
    # Kiểm tra message tồn tại
    message = await db.messages.find_one({"_id": ObjectId(message_id)})
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message không tìm thấy"
        )
    
    # Kiểm tra node thuộc về user
    if not ObjectId.is_valid(message["node_id"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node ID không hợp lệ"
        )
    
    node = await db.nodes.find_one({
        "_id": ObjectId(message["node_id"]),
        "user_id": user_id
    })
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền cập nhật message này"
        )
    
    # Kiểm tra sender hợp lệ nếu có
    if message_data.sender is not None and message_data.sender not in ["AI", "You"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sender phải là 'AI' hoặc 'You'"
        )
    
    # Cập nhật
    update_data = {}
    if message_data.sender is not None:
        update_data["sender"] = message_data.sender
    if message_data.content is not None:
        update_data["content"] = message_data.content
    
    if update_data:
        await db.messages.update_one(
            {"_id": ObjectId(message_id)},
            {"$set": update_data}
        )
    
    # Lấy lại message sau khi update
    updated_message = await db.messages.find_one({"_id": ObjectId(message_id)})
    
    return MessageResponse(
        id=str(updated_message["_id"]),
        node_id=updated_message["node_id"],
        sender=updated_message["sender"],
        content=updated_message["content"]
    )

@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Xóa message"""
    db = get_database()
    
    if not ObjectId.is_valid(message_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message ID không hợp lệ"
        )
    
    # Kiểm tra message tồn tại
    message = await db.messages.find_one({"_id": ObjectId(message_id)})
    
    if not message:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Message không tìm thấy"
        )
    
    # Kiểm tra node thuộc về user
    if not ObjectId.is_valid(message["node_id"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node ID không hợp lệ"
        )
    
    node = await db.nodes.find_one({
        "_id": ObjectId(message["node_id"]),
        "user_id": user_id
    })
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền xóa message này"
        )
    
    # Xóa message
    await db.messages.delete_one({"_id": ObjectId(message_id)})
    
    return None

