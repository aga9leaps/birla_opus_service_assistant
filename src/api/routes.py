"""
Birla Opus Chatbot - API Routes
"""
from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from src.data.database import get_db
from src.data.models import (
    OTPRequestCreate, OTPVerify, ChatMessage, ChatResponse,
    FeedbackSubmit, UserCreate, User, UserType
)
from src.core.auth import AuthService
from src.core.chat import ChatService
from config.settings import get_settings

settings = get_settings()

router = APIRouter()


# ============================================================================
# Health Check
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "birla-opus-chatbot"}


# ============================================================================
# Authentication Routes
# ============================================================================

@router.post("/auth/request-otp")
async def request_otp(
    request: OTPRequestCreate,
    db: Session = Depends(get_db)
):
    """
    Request OTP for phone number.
    Phone must be pre-approved in the system.
    """
    auth_service = AuthService(db)
    success, message, otp = auth_service.request_otp(request.phone_number)

    if not success:
        raise HTTPException(status_code=403, detail=message)

    response = {"success": True, "message": message}

    # For demo/testing, include OTP in response
    if settings.DEBUG and otp:
        response["demo_otp"] = otp

    return response


@router.post("/auth/verify-otp")
async def verify_otp(
    request: OTPVerify,
    db: Session = Depends(get_db)
):
    """
    Verify OTP and get access token.
    """
    auth_service = AuthService(db)
    success, message, token = auth_service.verify_otp(request.phone_number, request.otp_code)

    if not success:
        raise HTTPException(status_code=401, detail=message)

    return {
        "success": True,
        "message": message,
        "access_token": token,
        "token_type": "bearer"
    }


@router.get("/auth/me")
async def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Get current user info from token."""
    token = authorization.replace("Bearer ", "")
    auth_service = AuthService(db)

    valid, user_info = auth_service.validate_token(token)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return user_info


# ============================================================================
# Chat Routes
# ============================================================================

@router.post("/chat", response_model=ChatResponse)
async def send_message(
    message: ChatMessage,
    authorization: str = Header(...),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    db: Session = Depends(get_db)
):
    """
    Send a message and get chatbot response.
    Requires authentication.
    """
    # Validate token
    token = authorization.replace("Bearer ", "")
    auth_service = AuthService(db)

    valid, user_info = auth_service.validate_token(token)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Get or create session
    session_id = x_session_id or str(uuid.uuid4())

    # Process message
    chat_service = ChatService(db)

    conversation = chat_service.get_or_create_conversation(
        user_id=user_info["user_id"],
        session_id=session_id,
        channel="api",
        language=message.language or user_info.get("language", "en")
    )

    response_text, sources, processing_time = chat_service.process_message(
        conversation=conversation,
        user_message=message.message,
        user_type=user_info["user_type"],
        user_name=user_info.get("name"),
        language=message.language or "en"
    )

    # Get last message ID
    from src.data.models import Message
    last_message = db.query(Message).filter(
        Message.conversation_id == conversation.id,
        Message.role == "assistant"
    ).order_by(Message.created_at.desc()).first()

    return ChatResponse(
        message_id=str(last_message.id) if last_message else str(uuid.uuid4()),
        response=response_text,
        sources=sources,
        language=message.language or "en",
        processing_time_ms=processing_time
    )


@router.post("/chat/feedback")
async def submit_feedback(
    feedback: FeedbackSubmit,
    authorization: str = Header(...),
    db: Session = Depends(get_db)
):
    """Submit feedback for a message."""
    # Validate token
    token = authorization.replace("Bearer ", "")
    auth_service = AuthService(db)

    valid, _ = auth_service.validate_token(token)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    chat_service = ChatService(db)
    success = chat_service.submit_feedback(
        feedback.message_id,
        feedback.feedback,
        feedback.comment
    )

    if not success:
        raise HTTPException(status_code=400, detail="Failed to submit feedback")

    return {"success": True, "message": "Feedback submitted"}


@router.post("/chat/end")
async def end_conversation(
    authorization: str = Header(...),
    x_session_id: str = Header(..., alias="X-Session-ID"),
    db: Session = Depends(get_db)
):
    """End current conversation session."""
    token = authorization.replace("Bearer ", "")
    auth_service = AuthService(db)

    valid, user_info = auth_service.validate_token(token)
    if not valid:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Find conversation
    from src.data.models import Conversation
    conversation = db.query(Conversation).filter(
        Conversation.session_id == x_session_id,
        Conversation.user_id == uuid.UUID(user_info["user_id"])
    ).first()

    if conversation:
        chat_service = ChatService(db)
        chat_service.end_conversation(str(conversation.id))

    return {"success": True, "message": "Conversation ended"}


# ============================================================================
# Admin Routes (for demo/testing)
# ============================================================================

@router.post("/admin/users", tags=["admin"])
async def create_user(
    user: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new approved user (admin endpoint).
    In production, this would require admin authentication.
    """
    # Check if user exists
    existing = db.query(User).filter(User.phone_number == user.phone_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")

    # Create user
    new_user = User(
        phone_number=user.phone_number,
        user_type=user.user_type,
        name=user.name,
        email=user.email,
        dealer_code=user.dealer_code,
        contractor_id=user.contractor_id,
        employee_id=user.employee_id,
        region=user.region,
        is_active=True
    )
    db.add(new_user)
    db.commit()

    return {
        "success": True,
        "user_id": str(new_user.id),
        "message": f"User created: {user.phone_number} ({user.user_type.value})"
    }


@router.get("/admin/users", tags=["admin"])
async def list_users(
    db: Session = Depends(get_db)
):
    """List all users (admin endpoint)."""
    users = db.query(User).all()
    return {
        "count": len(users),
        "users": [
            {
                "id": str(u.id),
                "phone": u.phone_number,
                "name": u.name,
                "type": u.user_type.value,
                "active": u.is_active,
            }
            for u in users
        ]
    }


# ============================================================================
# WhatsApp Webhook - Moved to src/api/whatsapp.py
# ============================================================================
# The WhatsApp webhook is now implemented in whatsapp.py with full Meta Cloud API support
