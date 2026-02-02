"""
Birla Opus Chatbot - FastAPI Application
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import time
import os

from config.settings import get_settings
from src.data.database import init_db, get_db_context
from src.core.auth import seed_demo_users
from src.api.routes import router
from src.api.whatsapp import router as whatsapp_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("Starting Birla Opus Chatbot...")

    # Initialize database
    print("Initializing database...")
    init_db()

    # Seed demo users
    print("Seeding demo users...")
    with get_db_context() as db:
        seed_demo_users(db)

    # Initialize RAG
    print("Loading knowledge base...")
    from src.core.rag import get_rag_service
    rag = get_rag_service()
    print(f"Loaded {len(rag.chunks)} knowledge chunks")

    print("Birla Opus Chatbot ready!")

    yield

    # Shutdown
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Birla Opus Chatbot API",
    description="""
    AI-powered chatbot for Birla Opus painting services.

    ## Features
    - OTP-based authentication
    - Multi-language support (Hindi, English, Regional)
    - User type-specific responses (Sales, Dealer, Contractor, Painter)
    - RAG-powered knowledge retrieval
    - WhatsApp integration ready

    ## Authentication
    1. Request OTP with phone number
    2. Verify OTP to get access token
    3. Include token in Authorization header for all requests

    ## Demo Users
    - Sales: 919876543210
    - Dealer: 919876543211
    - Contractor: 919876543212
    - Painter: 919876543213
    - Tester: 911234567890

    For demo, OTP is returned in response.
    """,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    # Add ngrok bypass header
    response.headers["ngrok-skip-browser-warning"] = "true"
    return response


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc) if settings.DEBUG else "An error occurred"
        }
    )


# Include routes
app.include_router(router, prefix=settings.API_PREFIX)
app.include_router(whatsapp_router, prefix=settings.API_PREFIX)


# Root endpoint
@app.get("/")
async def root():
    return {
        "service": "Birla Opus Chatbot",
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
        "api_prefix": settings.API_PREFIX,
    }


# Serve static files for web widget (if available)
static_path = os.path.join(os.path.dirname(__file__), "../../web/static")
if os.path.exists(static_path):
    app.mount("/static", StaticFiles(directory=static_path), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG,
    )
