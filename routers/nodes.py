from fastapi import APIRouter, Depends, HTTPException, status, Query
from database import get_database
from schemas import NodeCreate, NodeUpdate, NodeResponse
from auth import get_current_user_id
from bson import ObjectId

router = APIRouter(prefix="/nodes", tags=["nodes"])

@router.post("", response_model=NodeResponse, status_code=status.HTTP_201_CREATED)
async def create_node(
    node_data: NodeCreate,
    user_id: str = Depends(get_current_user_id)
):
    """Tạo node mới"""
    db = get_database()
    
    # Kiểm tra workspace tồn tại và thuộc về user
    if not ObjectId.is_valid(node_data.workspace_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace ID không hợp lệ"
        )
    
    workspace = await db.workspaces.find_one({
        "_id": ObjectId(node_data.workspace_id),
        "user_id": user_id
    })
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace không tìm thấy"
        )
    
    # Kiểm tra model_id hợp lệ (1-6)
    if node_data.model_id not in ["1", "2", "3", "4", "5", "6"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model ID không hợp lệ. Vui lòng chọn từ 1-6"
        )
    
    node_dict = {
        "user_id": user_id,
        "workspace_id": node_data.workspace_id,
        "name": node_data.name,
        "model_id": node_data.model_id
    }
    
    result = await db.nodes.insert_one(node_dict)
    
    return NodeResponse(
        id=str(result.inserted_id),
        user_id=node_dict["user_id"],
        workspace_id=node_dict["workspace_id"],
        name=node_dict["name"],
        model_id=node_dict["model_id"]
    )

@router.get("", response_model=list[NodeResponse])
async def get_nodes(
    workspace_id: str = Query(None, description="Lọc theo workspace_id"),
    user_id: str = Depends(get_current_user_id)
):
    """Lấy danh sách nodes. Có thể lọc theo workspace_id"""
    db = get_database()
    
    query = {"user_id": user_id}
    if workspace_id:
        query["workspace_id"] = workspace_id
        # Kiểm tra workspace thuộc về user
        if ObjectId.is_valid(workspace_id):
            workspace = await db.workspaces.find_one({
                "_id": ObjectId(workspace_id),
                "user_id": user_id
            })
            if not workspace:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Workspace không tìm thấy"
                )
    
    nodes = await db.nodes.find(query).sort("_id", 1).to_list(length=1000)
    
    return [
        NodeResponse(
            id=str(node["_id"]),
            user_id=node["user_id"],
            workspace_id=node["workspace_id"],
            name=node.get("name", ""),
            model_id=node.get("model_id", "1")
        )
        for node in nodes
    ]

@router.get("/{node_id}", response_model=NodeResponse)
async def get_node(
    node_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Lấy thông tin node theo ID"""
    db = get_database()
    
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
    
    return NodeResponse(
        id=str(node["_id"]),
        user_id=node["user_id"],
        workspace_id=node["workspace_id"],
        name=node.get("name", ""),
        model_id=node.get("model_id", "1")
    )

@router.put("/{node_id}", response_model=NodeResponse)
async def update_node(
    node_id: str,
    node_data: NodeUpdate,
    user_id: str = Depends(get_current_user_id)
):
    """Cập nhật node"""
    db = get_database()
    
    if not ObjectId.is_valid(node_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node ID không hợp lệ"
        )
    
    # Kiểm tra node tồn tại và thuộc về user
    node = await db.nodes.find_one({
        "_id": ObjectId(node_id),
        "user_id": user_id
    })
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node không tìm thấy"
        )
    
    # Cập nhật
    update_data = {}
    if node_data.workspace_id is not None:
        # Kiểm tra workspace mới tồn tại và thuộc về user
        if not ObjectId.is_valid(node_data.workspace_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Workspace ID không hợp lệ"
            )
        workspace = await db.workspaces.find_one({
            "_id": ObjectId(node_data.workspace_id),
            "user_id": user_id
        })
        if not workspace:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workspace không tìm thấy"
            )
        update_data["workspace_id"] = node_data.workspace_id
    
    if node_data.name is not None:
        update_data["name"] = node_data.name
    
    if node_data.model_id is not None:
        # Kiểm tra model_id hợp lệ (1-6)
        if node_data.model_id not in ["1", "2", "3", "4", "5", "6"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model ID không hợp lệ. Vui lòng chọn từ 1-6"
            )
        update_data["model_id"] = node_data.model_id
    
    if update_data:
        await db.nodes.update_one(
            {"_id": ObjectId(node_id)},
            {"$set": update_data}
        )
    
    # Lấy lại node sau khi update
    updated_node = await db.nodes.find_one({"_id": ObjectId(node_id)})
    
    return NodeResponse(
        id=str(updated_node["_id"]),
        user_id=updated_node["user_id"],
        workspace_id=updated_node["workspace_id"],
        name=updated_node.get("name", ""),
        model_id=updated_node.get("model_id", "1")
    )

@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_node(
    node_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Xóa node"""
    db = get_database()
    
    if not ObjectId.is_valid(node_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Node ID không hợp lệ"
        )
    
    # Kiểm tra node tồn tại và thuộc về user
    node = await db.nodes.find_one({
        "_id": ObjectId(node_id),
        "user_id": user_id
    })
    
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Node không tìm thấy"
        )
    
    # Xóa tất cả messages của node
    await db.messages.delete_many({"node_id": node_id})
    
    # Xóa node
    await db.nodes.delete_one({"_id": ObjectId(node_id)})
    
    return None

