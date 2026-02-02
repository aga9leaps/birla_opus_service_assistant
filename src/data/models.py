"""
Birla Opus Chatbot - Database Models
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
from sqlalchemy import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
import uuid
import enum


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36) for SQLite.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return value
        else:
            if isinstance(value, uuid.UUID):
                return str(value)
            else:
                return str(uuid.UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


Base = declarative_base()


class UserType(str, enum.Enum):
    """User type enumeration."""
    SALES = "sales"
    DEALER = "dealer"
    CONTRACTOR = "contractor"
    PAINTER = "painter"
    TESTER = "tester"


class User(Base):
    """Approved users for OTP authentication."""
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    phone_number = Column(String(15), unique=True, nullable=False, index=True)
    user_type = Column(SQLEnum(UserType), nullable=False)
    name = Column(String(255), nullable=True)
    email = Column(String(255), nullable=True)

    # Additional info based on user type
    dealer_code = Column(String(50), nullable=True)  # For dealers
    contractor_id = Column(String(50), nullable=True)  # For contractors
    employee_id = Column(String(50), nullable=True)  # For sales team
    region = Column(String(100), nullable=True)

    # Status
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)

    # Metadata
    language_preference = Column(String(10), default="en")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    conversations = relationship("Conversation", back_populates="user")
    otp_requests = relationship("OTPRequest", back_populates="user")


class OTPRequest(Base):
    """OTP verification requests."""
    __tablename__ = "otp_requests"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    phone_number = Column(String(15), nullable=False)
    otp_code = Column(String(10), nullable=False)

    # Status
    is_verified = Column(Boolean, default=False)
    attempts = Column(Integer, default=0)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="otp_requests")


class Conversation(Base):
    """Chat conversations."""
    __tablename__ = "conversations"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False)
    session_id = Column(String(255), nullable=False, index=True)

    # Channel
    channel = Column(String(50), nullable=False)  # 'web', 'whatsapp'

    # Context
    user_context = Column(JSON, default={})
    language = Column(String(10), default="en")

    # Status
    is_active = Column(Boolean, default=True)
    message_count = Column(Integer, default=0)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    ended_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation")


class Message(Base):
    """Individual chat messages."""
    __tablename__ = "messages"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(GUID(), ForeignKey("conversations.id"), nullable=False)
    sequence = Column(Integer, nullable=False, default=0)  # Order within conversation

    # Content
    role = Column(String(20), nullable=False)  # 'user', 'assistant'
    content = Column(Text, nullable=False)
    language = Column(String(10), default="en")

    # RAG Info
    sources = Column(JSON, default=[])  # Retrieved document references

    # Feedback
    feedback = Column(String(20), nullable=True)  # 'positive', 'negative'
    feedback_comment = Column(Text, nullable=True)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    processing_time_ms = Column(Integer, nullable=True)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")


class AuditLog(Base):
    """Audit trail for compliance."""
    __tablename__ = "audit_logs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    # Event
    event_type = Column(String(100), nullable=False)
    event_category = Column(String(50), nullable=False)

    # Actor
    user_id = Column(GUID(), nullable=True)
    user_phone = Column(String(15), nullable=True)
    user_type = Column(String(50), nullable=True)
    ip_address = Column(String(45), nullable=True)

    # Details
    details = Column(JSON, default={})

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Pydantic models for API
from pydantic import BaseModel, Field
from typing import List


class UserCreate(BaseModel):
    """Schema for creating a new user."""
    phone_number: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")
    user_type: UserType
    name: Optional[str] = None
    email: Optional[str] = None
    dealer_code: Optional[str] = None
    contractor_id: Optional[str] = None
    employee_id: Optional[str] = None
    region: Optional[str] = None


class OTPRequestCreate(BaseModel):
    """Schema for OTP request."""
    phone_number: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")


class OTPVerify(BaseModel):
    """Schema for OTP verification."""
    phone_number: str = Field(..., pattern=r"^\+?[0-9]{10,15}$")
    otp_code: str = Field(..., min_length=4, max_length=10)


class ChatMessage(BaseModel):
    """Schema for chat message."""
    message: str = Field(..., min_length=1, max_length=4000)
    language: Optional[str] = "en"


class ChatResponse(BaseModel):
    """Schema for chat response."""
    message_id: str
    response: str
    sources: List[dict] = []
    language: str
    processing_time_ms: int


class FeedbackSubmit(BaseModel):
    """Schema for feedback submission."""
    message_id: str
    feedback: str = Field(..., pattern=r"^(positive|negative)$")
    comment: Optional[str] = None
