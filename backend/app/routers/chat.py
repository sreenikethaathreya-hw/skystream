from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.schemas.chat import ChatHistoryOut, ChatMessageIn, ChatSessionOut, ChatTurnOut
from app.services import chat_service
from app.services.user_service import CurrentUser

router = APIRouter(prefix="/api/chat", tags=["chat"], dependencies=[Depends(get_current_user)])


@router.post("/sessions", response_model=ChatSessionOut, status_code=201)
async def create_session(user: CurrentUser = Depends(get_current_user)) -> ChatSessionOut:
    return await chat_service.create_session(user)


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(user: CurrentUser = Depends(get_current_user)) -> list[ChatSessionOut]:
    return await chat_service.list_sessions(user)


@router.get("/sessions/{session_id}", response_model=ChatHistoryOut)
async def get_session(session_id: str, user: CurrentUser = Depends(get_current_user)) -> ChatHistoryOut:
    return await chat_service.get_history(user, session_id)


@router.post("/sessions/{session_id}/messages", response_model=ChatTurnOut)
async def send_message(
    session_id: str,
    body: ChatMessageIn,
    db: AsyncSession = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> ChatTurnOut:
    return await chat_service.send_message(db, user, session_id, body)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(session_id: str, user: CurrentUser = Depends(get_current_user)) -> None:
    await chat_service.delete_session(user, session_id)
