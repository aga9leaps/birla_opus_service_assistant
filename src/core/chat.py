"""
Birla Opus Chatbot - Chat Service
LLM integration with Gemini for multi-language support
"""
import os
import time
from typing import Optional, List, Dict, Tuple
from datetime import datetime
import uuid
import json

from sqlalchemy.orm import Session

from config.settings import get_settings, BASE_SYSTEM_PROMPT, USER_TYPE_PROMPTS
from src.data.models import Conversation, Message, AuditLog
from src.core.rag import get_rag_service

settings = get_settings()


class ChatService:
    """Chat service with LLM integration."""

    def __init__(self, db: Session):
        self.db = db
        self.rag = get_rag_service()
        self._llm_client = None

    def _get_llm_client(self):
        """Get or initialize LLM client."""
        if self._llm_client is None:
            try:
                import google.generativeai as genai

                api_key = os.getenv("GEMINI_API_KEY") or settings.GEMINI_API_KEY
                if api_key:
                    genai.configure(api_key=api_key)
                    self._llm_client = genai.GenerativeModel(settings.LLM_MODEL)
                else:
                    print("Warning: GEMINI_API_KEY not set, using mock responses")
            except ImportError:
                print("Warning: google-generativeai not installed, using mock responses")

        return self._llm_client

    def get_or_create_conversation(
        self,
        user_id: str,
        session_id: str,
        channel: str = "web",
        language: str = "en"
    ) -> Conversation:
        """Get existing conversation or create new one."""
        conversation = self.db.query(Conversation).filter(
            Conversation.session_id == session_id,
            Conversation.is_active == True
        ).first()

        if not conversation:
            conversation = Conversation(
                user_id=uuid.UUID(user_id),
                session_id=session_id,
                channel=channel,
                language=language,
                is_active=True,
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)

        return conversation

    def process_message(
        self,
        conversation: Conversation,
        user_message: str,
        user_type: str,
        user_name: str = None,
        language: str = "en"
    ) -> Tuple[str, List[Dict], int]:
        """
        Process user message and generate response.
        Returns: (response_text, sources, processing_time_ms)
        """
        start_time = time.time()

        # Get current message count for sequence
        current_seq = conversation.message_count

        # Save user message
        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=user_message,
            language=language,
            sequence=current_seq,
        )
        self.db.add(user_msg)

        # Get RAG context
        context, sources = self.rag.get_context_for_query(
            user_message,
            user_type=user_type,
            max_tokens=2000
        )

        # Get conversation history
        history = self._get_conversation_history(conversation.id, limit=10)

        # Build prompt
        system_prompt = self._build_system_prompt(user_type, user_name, language)
        full_prompt = self._build_full_prompt(
            system_prompt, context, history, user_message, language
        )

        # Generate response
        response_text = self._generate_response(full_prompt, language)

        # Calculate processing time
        processing_time_ms = int((time.time() - start_time) * 1000)

        # Save assistant message
        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=response_text,
            language=language,
            sources=sources,
            processing_time_ms=processing_time_ms,
            sequence=current_seq + 1,
        )
        self.db.add(assistant_msg)

        # Update conversation
        conversation.message_count += 2
        conversation.updated_at = datetime.utcnow()

        self.db.commit()

        return response_text, sources, processing_time_ms

    def _build_system_prompt(self, user_type: str, user_name: str, language: str) -> str:
        """Build system prompt based on user type."""
        base = BASE_SYSTEM_PROMPT
        user_context = USER_TYPE_PROMPTS.get(user_type, "")
        return f"{base}\n\n{user_context}"

    def _build_full_prompt(
        self,
        system_prompt: str,
        context: str,
        history: List[Dict],
        user_message: str,
        language: str
    ) -> str:
        """Build complete prompt for LLM."""
        prompt_parts = [system_prompt]

        # RAG context is critical - put it prominently
        if context:
            prompt_parts.append(f"\n\n## KNOWLEDGE BASE (USE THIS DATA - DO NOT SAY 'CHECK WEBSITE'):\n{context}")

        prompt_parts.append(f"\n\n## USER QUESTION:\n{user_message}")

        if history:
            prompt_parts.append("\n\n## Recent conversation for context:")
            for msg in history[-4:]:  # Last 4 messages only
                role = "U" if msg["role"] == "user" else "A"
                prompt_parts.append(f"{role}: {msg['content'][:300]}")

        prompt_parts.append("\n\n## YOUR ANSWER (use specific numbers from knowledge base):")

        return "\n".join(prompt_parts)

    def _generate_response(self, prompt: str, language: str) -> str:
        """Generate response using LLM."""
        llm = self._get_llm_client()

        if llm:
            try:
                response = llm.generate_content(
                    prompt,
                    generation_config={
                        "temperature": settings.LLM_TEMPERATURE,
                        "max_output_tokens": settings.LLM_MAX_TOKENS,
                    }
                )
                return response.text
            except Exception as e:
                print(f"LLM Error: {e}")
                return self._get_fallback_response(language)
        else:
            return self._get_mock_response(prompt, language)

    def _get_conversation_history(self, conversation_id: uuid.UUID, limit: int = 10) -> List[Dict]:
        """Get recent conversation history."""
        # Order by sequence number to ensure correct message order
        messages = self.db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.sequence.asc()).all()

        # Take only the most recent messages
        recent_messages = messages[-limit:] if len(messages) > limit else messages

        history = []
        for msg in recent_messages:
            history.append({
                "role": msg.role,
                "content": msg.content,
            })

        return history

    def _get_fallback_response(self, language: str) -> str:
        """Fallback response when LLM fails."""
        responses = {
            "en": "I apologize, but I'm having trouble processing your request. Please try again or call our helpline at 1800-120-1234.",
            "hi": "माफ़ कीजिए, मुझे आपका अनुरोध प्रोसेस करने में समस्या हो रही है। कृपया दोबारा प्रयास करें या 1800-120-1234 पर कॉल करें।",
        }
        return responses.get(language, responses["en"])

    def _get_mock_response(self, prompt: str, language: str) -> str:
        """Generate mock response for demo when LLM not available."""
        # Extract user message from prompt for more accurate keyword matching
        user_message = ""
        if "## Current User Message:" in prompt:
            parts = prompt.split("## Current User Message:")
            if len(parts) > 1:
                user_message = parts[1].split("## Your Response:")[0].strip().lower()

        # Fallback to full prompt if user message not extracted
        check_text = user_message if user_message else prompt.lower()

        # PROCESS-FOCUSED responses (most important)
        if any(w in check_text for w in ["process", "how to", "kaise", "steps", "procedure", "tarika"]):
            return "Surface clean karein, primer lagayein (4-6 hrs dry), phir 2 coats paint (4 hrs gap). Sahi process se finish bhi acha aata hai aur paint bhi zyada chalta hai."

        elif any(w in check_text for w in ["primer", "praimar"]):
            return "Primer zaroori hai ji - paint adhesion better hota hai, coverage badhta hai. New wall pe especially must hai. Birla Opus primer use karein, 4-6 ghante dry hone dein."

        elif any(w in check_text for w in ["drying", "sukh", "dry time", "wait"]):
            return "Primer: 4-6 hours, Paint coats ke beech: 4 hours minimum. Humidity zyada ho toh thoda extra time dein. Jaldi coat karne se finish kharab hota hai."

        elif any(w in check_text for w in ["surface", "wall prep", "preparation", "tayyari"]):
            return "Pehle loose paint/dust nikaalein, cracks ko putty se bharein, sandpaper se smooth karein. Clean dry surface pe hi paint karein - yahi secret hai lasting finish ka."

        elif any(w in check_text for w in ["coat", "kitne coat", "layers"]):
            return "2 coats recommended hai proper coverage ke liye. Pehla coat halka, doosra full. Dark colors pe kabhi kabhi 3rd coat bhi lagta hai."

        # PRODUCT queries
        elif any(w in check_text for w in ["waterproof", "leakage", "seepage", "alldry", "damp"]):
            return "Waterproofing ke liye ALLDRY range best hai - wall, roof, terrace sab ke liye alag products. 12 saal tak warranty. Surface dry hona chahiye application se pehle."

        elif any(w in check_text for w in ["interior", "andar", "room", "bedroom", "living"]):
            return "Interior ke liye Calista ya Royale series dekhein - washable hai, stain resistant. Matt ya sheen finish available. Coverage around 120-140 sq ft/L."

        elif any(w in check_text for w in ["exterior", "bahar", "outside", "weather"]):
            return "Exterior ke liye True Vision ya Neo Star - UV resistant, anti-algal. 7+ saal chalta hai. Rainy season mein application avoid karein."

        elif any(w in check_text for w in ["texture", "design", "pattern"]):
            return "Texture finishes se walls ko premium look milta hai. Roller ya spray se application. PaintCraft wale professional finish dete hain."

        # BUSINESS queries
        elif any(w in check_text for w in ["cashback", "scheme", "loyalty", "program", "benefit"]):
            return "Painter loyalty mein 5-12% cashback milta hai purchase pe. App download karein, register karein - har transaction track hota hai."

        elif any(w in check_text for w in ["price", "cost", "rate", "kitna", "daam", "price list"]):
            return "Price location aur dealer pe depend karta hai ji. Product batayein toh approximate range bata sakta hoon, exact ke liye dealer se confirm karein."

        elif any(w in check_text for w in ["coverage", "kitna lagega", "calculation", "area"]):
            return "Roughly 100-140 sq ft/L for interior (2 coats). Wall area batayein, main calculate kar deta hoon kitna paint lagega."

        elif any(w in check_text for w in ["order", "stock", "delivery", "available"]):
            return "Stock aur delivery apne dealer ya ASM se check karein. Most products 24-48 hrs mein available ho jaate hain depot towns mein."

        # TROUBLESHOOTING
        elif any(w in check_text for w in ["problem", "issue", "peeling", "crack", "bubble", "flaking"]):
            return "Peeling/bubbles usually moisture ya improper surface prep se hota hai. Affected area scrape karein, dry hone dein, primer lagayein phir repaint. Photos bhejein toh better suggest kar sakta hoon."

        elif any(w in check_text for w in ["color", "colour", "shade", "rang"]):
            return "2300+ shades available hain. Dealer ke paas shade card dekhein ya app pe visualizer try karein. Tinting machine se custom shade bhi ban sakta hai."

        # GREETINGS - language adaptive
        elif any(g in check_text for g in ["namaste", "namaskar"]):
            return "Namaste ji! 🙏 Batayein kaise madad karun?"
        elif any(g in check_text for g in ["vanakkam"]):
            return "Vanakkam! 🙏 Enna udavi venum?"
        elif any(g in check_text for g in ["namaskara", "namaskaram"]):
            return "Namaskara! 🙏 Hegiddira? Paint bagge help beku?"
        elif any(g in check_text for g in ["hello", "hi", "hey"]):
            return "Hello! How can I help you today?"

        elif any(t in check_text for t in ["thanks", "thank", "dhanyawad", "shukriya", "nandri"]):
            return "Most welcome ji! 🙏 Aur kuch help chahiye toh batayein."

        # GUARDRAILS
        elif any(x in check_text for x in ["cricket", "movie", "politics", "election", "weather", "joke", "news"]):
            return "Ji main paint aur painting services ke baare mein hi help kar sakta hoon. Koi paint related sawaal ho toh zaroor poochein!"

        else:
            return "Ji batayein - products, process, ya schemes mein kaise help karun?"

    def submit_feedback(self, message_id: str, feedback: str, comment: str = None) -> bool:
        """Submit feedback for a message."""
        try:
            message = self.db.query(Message).filter(
                Message.id == uuid.UUID(message_id)
            ).first()

            if message:
                message.feedback = feedback
                message.feedback_comment = comment
                self.db.commit()
                return True
        except Exception as e:
            print(f"Feedback error: {e}")

        return False

    def end_conversation(self, conversation_id: str) -> bool:
        """End a conversation session."""
        try:
            conversation = self.db.query(Conversation).filter(
                Conversation.id == uuid.UUID(conversation_id)
            ).first()

            if conversation:
                conversation.is_active = False
                conversation.ended_at = datetime.utcnow()
                self.db.commit()
                return True
        except Exception as e:
            print(f"End conversation error: {e}")

        return False
