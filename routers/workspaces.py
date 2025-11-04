from fastapi import APIRouter, Depends, HTTPException, status
from database import get_database
from schemas import WorkspaceCreate, WorkspaceUpdate, WorkspaceResponse
from auth import get_current_user_id
from bson import ObjectId

router = APIRouter(prefix="/workspaces", tags=["workspaces"])

@router.post("", response_model=WorkspaceResponse, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    workspace_data: WorkspaceCreate,
    user_id: str = Depends(get_current_user_id)
):
    """Tạo workspace mới"""
    db = get_database()
    
    workspace_dict = {
        "user_id": user_id,
        "name": workspace_data.name
    }
    
    result = await db.workspaces.insert_one(workspace_dict)
    
    return WorkspaceResponse(
        id=str(result.inserted_id),
        user_id=workspace_dict["user_id"],
        name=workspace_dict["name"]
    )

@router.get("", response_model=list[WorkspaceResponse])
async def get_workspaces(user_id: str = Depends(get_current_user_id)):
    """Lấy danh sách workspaces của user hiện tại"""
    db = get_database()
    
    workspaces = await db.workspaces.find({"user_id": user_id}).to_list(length=100)
    
    return [
        WorkspaceResponse(
            id=str(ws["_id"]),
            user_id=ws["user_id"],
            name=ws.get("name", "")
        )
        for ws in workspaces
    ]

@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Lấy thông tin workspace theo ID"""
    db = get_database()
    
    if not ObjectId.is_valid(workspace_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workspace ID không hợp lệ"
        )
    
    workspace = await db.workspaces.find_one({
        "_id": ObjectId(workspace_id),
        "user_id": user_id
    })
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace không tìm thấy"
        )
    
    return WorkspaceResponse(
        id=str(workspace["_id"]),
        user_id=workspace["user_id"],
        name=workspace.get("name", "")
    )

@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def update_workspace(
    workspace_id: str,
    workspace_data: WorkspaceUpdate,
    user_id: str = Depends(get_current_user_id)
):
    """Cập nhật workspace"""
    db = get_database()
    
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
    
    # Cập nhật
    update_data = {}
    if workspace_data.name is not None:
        update_data["name"] = workspace_data.name
    
    if update_data:
        await db.workspaces.update_one(
            {"_id": ObjectId(workspace_id)},
            {"$set": update_data}
        )
    
    # Lấy lại workspace sau khi update
    updated_workspace = await db.workspaces.find_one({"_id": ObjectId(workspace_id)})
    
    return WorkspaceResponse(
        id=str(updated_workspace["_id"]),
        user_id=updated_workspace["user_id"],
        name=updated_workspace.get("name", "")
    )

@router.delete("/{workspace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workspace(
    workspace_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """Xóa workspace"""
    db = get_database()
    
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
    
    # Xóa tất cả nodes thuộc workspace này trước
    nodes = await db.nodes.find({"workspace_id": workspace_id}).to_list(length=1000)
    node_ids = [str(node["_id"]) for node in nodes]
    
    # Xóa tất cả messages của các nodes
    if node_ids:
        await db.messages.delete_many({"node_id": {"$in": node_ids}})
    
    # Xóa tất cả nodes
    await db.nodes.delete_many({"workspace_id": workspace_id})
    
    # Xóa workspace
    await db.workspaces.delete_one({"_id": ObjectId(workspace_id)})
    
    return None

