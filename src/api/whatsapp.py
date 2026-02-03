"""
Birla Opus Chatbot - WhatsApp Webhook Handler
Conversational onboarding, crisp responses
"""
import os
import hmac
import hashlib
import httpx
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
import uuid

from src.data.database import get_db
from src.data.models import User, UserType
from src.core.chat import ChatService
from config.settings import get_settings

settings = get_settings()
router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# Meta WhatsApp API Configuration
WHATSAPP_API_URL = "https://graph.facebook.com/v18.0"
WHATSAPP_PHONE_NUMBER_ID = settings.WHATSAPP_PHONE_NUMBER_ID or ""
WHATSAPP_ACCESS_TOKEN = settings.WHATSAPP_ACCESS_TOKEN or ""
WHATSAPP_VERIFY_TOKEN = settings.WHATSAPP_VERIFY_TOKEN or "birla-opus-verify-token"
WHATSAPP_APP_SECRET = settings.WHATSAPP_APP_SECRET or ""

# Onboarding state: phone -> {"state": "awaiting_type" | "awaiting_language", "type": UserType}
onboarding_state = {}


# ============================================================================
# Webhook Endpoints
# ============================================================================

@router.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
):
    """Meta webhook verification."""
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        print("Webhook verified")
        return int(hub_challenge) if hub_challenge else "OK"
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def handle_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle incoming WhatsApp messages."""
    body = await request.body()
    body_json = await request.json()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if WHATSAPP_APP_SECRET and not verify_signature(body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        if body_json.get("object") == "whatsapp_business_account":
            for entry in body_json.get("entry", []):
                for change in entry.get("changes", []):
                    if change.get("field") == "messages":
                        await process_messages(change.get("value", {}), db)
        return {"status": "ok"}
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error"}


async def process_messages(value: dict, db: Session):
    """Process incoming messages."""
    messages = value.get("messages", [])
    contacts = value.get("contacts", [])

    for message in messages:
        phone = message.get("from", "")
        msg_type = message.get("type", "")
        msg_id = message.get("id", "")

        # Get sender name
        sender_name = None
        for contact in contacts:
            if contact.get("wa_id") == phone:
                sender_name = contact.get("profile", {}).get("name")
                break

        print(f"Message from {phone}: type={msg_type}")

        # Extract text
        text = ""
        if msg_type == "text":
            text = message.get("text", {}).get("body", "")
        elif msg_type == "interactive":
            interactive = message.get("interactive", {})
            if interactive.get("type") == "button_reply":
                text = interactive.get("button_reply", {}).get("title", "")
            elif interactive.get("type") == "list_reply":
                text = interactive.get("list_reply", {}).get("title", "")
        else:
            await send_message(phone, "Text only please.")
            await mark_read(msg_id)
            continue

        if text:
            await handle_message(phone, text.strip(), sender_name, db)

        await mark_read(msg_id)


async def handle_message(phone: str, text: str, sender_name: str, db: Session):
    """Route message based on user state."""
    normalized = normalize_phone(phone)
    text_lower = text.lower().strip()

    # Check onboarding state
    state = onboarding_state.get(normalized)

    if state:
        if state["state"] == "awaiting_type":
            await handle_type_selection(phone, normalized, text_lower, sender_name, db)
            return
        elif state["state"] == "awaiting_language":
            await handle_language_selection(phone, normalized, text_lower, sender_name, db)
            return

    # Check if registered
    user = db.query(User).filter(
        User.phone_number == normalized,
        User.is_active == True
    ).first()

    if not user:
        # New user - start onboarding
        onboarding_state[normalized] = {"state": "awaiting_type"}
        await send_message(phone, "Birla Opus PaintCraft assistant. Are you a dealer, painter, or sales team?")
        return

    # Registered user - process message
    await process_chat(phone, text, user, sender_name, db)


async def handle_type_selection(phone: str, normalized: str, text: str, sender_name: str, db: Session):
    """Parse user type from response."""
    user_type = None

    # Dealer
    if any(w in text for w in ["dealer", "shop", "store", "dukan", "dukaan"]):
        user_type = UserType.DEALER
    # Painter
    elif any(w in text for w in ["painter", "paint karta", "painting", "mistri"]):
        user_type = UserType.PAINTER
    # Contractor
    elif any(w in text for w in ["contractor", "thekedar", "thekedaar"]):
        user_type = UserType.PAINTER  # Same as painter for now
    # Sales
    elif any(w in text for w in ["sales", "employee", "staff", "birla", "team"]):
        user_type = UserType.SALES

    if user_type:
        onboarding_state[normalized] = {"state": "awaiting_language", "type": user_type}
        await send_message(phone, "Got it. Hindi, English, or your regional language?")
    else:
        await send_message(phone, "Dealer, painter, contractor, or sales? Pick one.")


async def handle_language_selection(phone: str, normalized: str, text: str, sender_name: str, db: Session):
    """Parse language preference and complete registration."""
    lang = "en"  # default

    # Hindi
    if any(w in text for w in ["hindi", "हिंदी", "हिन्दी"]):
        lang = "hi"
    # Tamil
    elif any(w in text for w in ["tamil", "தமிழ்"]):
        lang = "ta"
    # Telugu
    elif any(w in text for w in ["telugu", "తెలుగు"]):
        lang = "te"
    # Kannada
    elif any(w in text for w in ["kannada", "ಕನ್ನಡ"]):
        lang = "kn"
    # Bengali
    elif any(w in text for w in ["bengali", "bangla", "বাংলা"]):
        lang = "bn"
    # Marathi
    elif any(w in text for w in ["marathi", "मराठी"]):
        lang = "mr"
    # Gujarati
    elif any(w in text for w in ["gujarati", "ગુજરાતી"]):
        lang = "gu"
    # English (default if mentioned or anything else)
    elif any(w in text for w in ["english", "eng"]):
        lang = "en"

    # Create user
    state = onboarding_state.get(normalized, {})
    user_type = state.get("type", UserType.DEALER)

    user = User(
        phone_number=normalized,
        name=sender_name or "User",
        user_type=user_type,
        language_preference=lang,
        is_active=True,
        is_verified=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Clear state
    del onboarding_state[normalized]

    # Welcome - role specific
    type_name = {UserType.DEALER: "dealer", UserType.PAINTER: "painter", UserType.SALES: "sales"}.get(user_type, "partner")
    if lang == "hi":
        await send_message(phone, f"Setup done. Painting services mein kya help chahiye?")
    else:
        await send_message(phone, f"Setup done. What do you need help with for painting services?")

    print(f"Created user: {normalized} as {user_type.value}, lang={lang}")


async def process_chat(phone: str, text: str, user: User, sender_name: str, db: Session):
    """Process chat message through LLM."""
    chat_service = ChatService(db)
    session_id = f"wa_{user.phone_number}"

    conversation = chat_service.get_or_create_conversation(
        user_id=str(user.id),
        session_id=session_id,
        channel="whatsapp",
        language=user.language_preference or "en"
    )

    response, sources, time_ms = chat_service.process_message(
        conversation=conversation,
        user_message=text,
        user_type=user.user_type.value,
        user_name=sender_name or user.name,
        language=user.language_preference or "en"
    )

    await send_message(phone, response)
    print(f"Responded to {phone} in {time_ms}ms")


# ============================================================================
# WhatsApp API
# ============================================================================

async def send_message(to: str, text: str):
    """Send text message."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        print(f"[Mock] To {to}: {text[:100]}")
        return

    url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    # Split long messages
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]

    async with httpx.AsyncClient() as client:
        for chunk in chunks:
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {"body": chunk}
            }
            try:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
            except Exception as e:
                print(f"Send failed: {e}")


async def mark_read(message_id: str):
    """Mark message as read."""
    if not WHATSAPP_ACCESS_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
        return

    url = f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json={
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id
            }, headers=headers)
        except:
            pass


# ============================================================================
# Helpers
# ============================================================================

def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify webhook signature."""
    if not WHATSAPP_APP_SECRET:
        return True
    if not signature.startswith("sha256="):
        return False
    expected = hmac.new(WHATSAPP_APP_SECRET.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature[7:], expected)


def normalize_phone(phone: str) -> str:
    """Normalize phone number."""
    phone = "".join(filter(str.isdigit, phone))
    if len(phone) == 10:
        phone = "91" + phone
    return phone
