"""
Birla Opus Chatbot - Configuration Settings
"""
from pydantic_settings import BaseSettings
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Application
    APP_NAME: str = "Birla Opus Chatbot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENV: str = "development"

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/birla_opus"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # LLM - Using Vertex AI with Gemini
    LLM_PROVIDER: str = "vertex_ai"
    VERTEX_PROJECT_ID: Optional[str] = None
    VERTEX_LOCATION: str = "us-central1"
    LLM_MODEL: str = "gemini-2.5-flash"  # Vertex AI model name
    LLM_TEMPERATURE: float = 0.4  # Balanced: conversational but grounded
    LLM_MAX_TOKENS: int = 1024

    # Embeddings
    EMBEDDING_MODEL: str = "models/text-embedding-004"
    EMBEDDING_DIMENSIONS: int = 768

    # RAG Settings
    RAG_CHUNK_SIZE: int = 512
    RAG_CHUNK_OVERLAP: int = 50
    RAG_TOP_K: int = 5
    RAG_SIMILARITY_THRESHOLD: float = 0.7

    # Authentication
    JWT_SECRET: str = "birla-opus-chatbot-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    OTP_EXPIRY_MINUTES: int = 5
    OTP_LENGTH: int = 6

    # WhatsApp (Twilio - legacy, for backward compatibility)
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_WHATSAPP_NUMBER: Optional[str] = None

    # Meta WhatsApp Cloud API
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: str = "birla-opus-verify-token"
    WHATSAPP_APP_SECRET: Optional[str] = None

    # Supported Languages (Gemini 3 Flash supports these Indian languages)
    SUPPORTED_LANGUAGES: list = [
        "en",  # English
        "hi",  # Hindi
        "ta",  # Tamil
        "te",  # Telugu
        "kn",  # Kannada
        "ml",  # Malayalam
        "bn",  # Bengali
        "mr",  # Marathi
        "gu",  # Gujarati
        "pa",  # Punjabi
    ]

    # User Types
    USER_TYPES: list = [
        "sales",       # Sales Team
        "dealer",      # Dealers
        "contractor",  # Contractors/Painters
        "painter",     # Individual Painters
        "tester",      # Tester (access to all)
    ]

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 30

    # Storage
    KNOWLEDGE_BASE_PATH: str = "./knowledge_base"
    VECTOR_STORE_PATH: str = "./data/vector_store"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# User type prompts - specific context for each role
USER_TYPE_PROMPTS = {
    "sales": "ROLE: Sales Team. Help pitch PaintCraft, handle objections, close dealer sign-ups.",
    "dealer": "ROLE: Dealer. Help quote jobs, calculate materials, manage painters, handle complaints.",
    "painter": "ROLE: Painter/Contractor. Help with technique, products, Birla Opus ID cashback.",
    "tester": "Test user.",
    "contractor": "ROLE: Contractor. Help with technique, products, Birla Opus ID cashback.",
}

# Base prompt - PaintCraft business assistant with examples
BASE_SYSTEM_PROMPT = """You assist Birla Opus PaintCraft partners. Use the KNOWLEDGE BASE provided to give specific answers.

RULES:
1. Give SPECIFIC numbers from knowledge base - never say "check website"
2. Mirror user's language exactly
3. 2-3 lines max, no fluff
4. No names, greetings, or sign-offs

EXAMPLES OF GOOD ANSWERS:

Q: 2BHK interior kitna material lagega?
A: 1200 sqft area ke liye: 10-12L paint, 20-25kg putty, 4L primer. Product batao toh exact du.

Q: Mera cashback nahi aaya
A: App mein transaction history check karo. Sahi hai toh 1800-103-7171 pe call karo, 24hrs mein resolve hoga.

Q: Damp wall pe paint kaise karun?
A: Pehle leakage fix karo. ALLDRY waterproofing lagao, 48hr dry hone do. Phir primer+2 coat paint.

Q: Dealer ko kaise pitch karun?
A: "Aap paint bech rahe ho, service se 2-3x kama sakte ho. 25-35% margin, painters hum denge, training free."

Q: Customer bol raha rate zyada hai
A: "Local painter warranty nahi deta. Humare paas trained painters, genuine products, 1yr workmanship + product warranty. Peace of mind ka value hai."

Q: Gold tier ke liye kitna purchase?
A: Rs.5-10 lakh annual purchase. Benefits: 10% cashback, health insurance, priority job leads.

KNOWLEDGE REFERENCE:
- Interior rate: Rs.35-55/sqft (material+labor)
- Exterior rate: Rs.45-75/sqft
- Labor only: Interior Rs.18-25/sqft, Exterior Rs.22-35/sqft
- Coverage: Interior 120-140 sqft/L, Exterior 45-55 sqft/L
- Birla Opus ID tiers: Bronze (5%), Silver (7%), Gold (10%), Platinum (12%)
- Helpline: 1800-103-7171 (8AM-8PM)
"""
