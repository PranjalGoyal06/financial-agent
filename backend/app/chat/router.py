from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db import get_session
from app.models import ChatSessionModel, ChatMessageModel
from app.schemas import ChatSessionListResponse, ChatSessionResponse, ChatMessageResponse, ChatSessionUpdateRequest
from app.config import settings
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.get("/sessions", response_model=ChatSessionListResponse)
async def list_sessions(session: AsyncSession = Depends(get_session)):
    stmt = (
        select(ChatSessionModel)
        .where(ChatSessionModel.user_id == settings.default_user_id)
        .order_by(ChatSessionModel.created_at.desc())
    )
    result = await session.execute(stmt)
    sessions = result.scalars().all()
    
    return ChatSessionListResponse(
        sessions=[
            ChatSessionResponse(
                id=s.id,
                title=s.title,
                created_at=s.created_at.isoformat(),
                updated_at=s.updated_at.isoformat(),
                messages=[]
            ) for s in sessions
        ]
    )


@router.post("/sessions", response_model=ChatSessionResponse)
async def create_session(session: AsyncSession = Depends(get_session)):
    new_session = ChatSessionModel(
        id=str(uuid.uuid4()),
        user_id=settings.default_user_id,
        title="New Chat",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    session.add(new_session)
    await session.commit()
    
    return ChatSessionResponse(
        id=new_session.id,
        title=new_session.title,
        created_at=new_session.created_at.isoformat(),
        updated_at=new_session.updated_at.isoformat(),
        messages=[]
    )


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
async def get_session_detail(session_id: str, session: AsyncSession = Depends(get_session)):
    stmt = select(ChatSessionModel).where(
        ChatSessionModel.id == session_id,
        ChatSessionModel.user_id == settings.default_user_id
    )
    result = await session.execute(stmt)
    chat_session = result.scalar_one_or_none()
    
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    msg_stmt = (
        select(ChatMessageModel)
        .where(ChatMessageModel.session_id == session_id)
        .order_by(ChatMessageModel.created_at.asc())
    )
    msg_result = await session.execute(msg_stmt)
    messages = msg_result.scalars().all()
    
    return ChatSessionResponse(
        id=chat_session.id,
        title=chat_session.title,
        created_at=chat_session.created_at.isoformat(),
        updated_at=chat_session.updated_at.isoformat(),
        messages=[
            ChatMessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                thinking=m.thinking,
                tool_calls=m.tool_calls,
                tool_call_id=m.tool_call_id,
                tool_name=m.tool_name,
                created_at=m.created_at.isoformat()
            ) for m in messages
        ]
    )


@router.patch("/sessions/{session_id}", response_model=ChatSessionResponse)
async def update_session(
    session_id: str, 
    update_data: ChatSessionUpdateRequest, 
    session: AsyncSession = Depends(get_session)
):
    stmt = select(ChatSessionModel).where(
        ChatSessionModel.id == session_id,
        ChatSessionModel.user_id == settings.default_user_id
    )
    result = await session.execute(stmt)
    chat_session = result.scalar_one_or_none()
    
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    chat_session.title = update_data.title
    chat_session.updated_at = datetime.now(timezone.utc)
    await session.commit()
    
    return ChatSessionResponse(
        id=chat_session.id,
        title=chat_session.title,
        created_at=chat_session.created_at.isoformat(),
        updated_at=chat_session.updated_at.isoformat(),
        messages=[]
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: str, 
    session: AsyncSession = Depends(get_session)
):
    stmt = select(ChatSessionModel).where(
        ChatSessionModel.id == session_id,
        ChatSessionModel.user_id == settings.default_user_id
    )
    result = await session.execute(stmt)
    chat_session = result.scalar_one_or_none()
    
    if not chat_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    # Delete associated messages
    msg_stmt = select(ChatMessageModel).where(ChatMessageModel.session_id == session_id)
    msg_result = await session.execute(msg_stmt)
    for m in msg_result.scalars().all():
        await session.delete(m)
        
    await session.delete(chat_session)
    await session.commit()
    return None
