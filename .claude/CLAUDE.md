# Birla Opus Chatbot - Claude Context

**Project:** Birla Opus AI Chatbot
**Stage:** MVP
**Methodology:** Marcus3 v1.0
**Created:** January 2026

---

## Project Overview

AI-powered chatbot for Birla Opus painting services (Aditya Birla Group).

**Target Users:**
- Sales Team - Lead management, dealer support
- Dealers - Orders, schemes, credit terms
- Contractors - Cashback, training, technical guidance
- Painters - Product usage, application tips

**Channels:**
- Web Widget (responsive chat interface)
- REST API (programmatic access)
- WhatsApp (via Twilio/Meta - planned)

---

## Tech Stack

- **Backend:** FastAPI (Python 3.11)
- **Database:** PostgreSQL + pgvector (optional)
- **Cache:** Redis
- **LLM:** Google Gemini 3 Flash (multi-language)
- **Container:** Docker

---

## Key Files

```
config/settings.py       - Configuration and prompts
src/api/main.py         - FastAPI application
src/api/routes.py       - API endpoints
src/core/auth.py        - OTP authentication
src/core/chat.py        - LLM chat service
src/core/rag.py         - Knowledge retrieval
src/data/models.py      - Database models
knowledge_base/*.md     - RAG knowledge files
web/index.html          - Web chat widget
```

---

## Running the Project

```bash
# With Docker
cd docker && docker-compose up -d

# Local development
pip install -r requirements.txt
python -m uvicorn src.api.main:app --reload
```

---

## Demo Users

| Phone | Type | OTP |
|-------|------|-----|
| 9876543210 | Sales | Returned in API response |
| 9876543211 | Dealer | |
| 9876543212 | Contractor | |
| 9876543213 | Painter | |
| 1234567890 | Tester | |

---

## API Endpoints

- `POST /api/v1/auth/request-otp` - Request OTP
- `POST /api/v1/auth/verify-otp` - Verify and get token
- `POST /api/v1/chat` - Send message
- `POST /api/v1/chat/feedback` - Submit feedback
- `POST /api/v1/admin/users` - Create user (admin)

---

## Current Focus

- [x] Basic API structure
- [x] OTP authentication
- [x] Knowledge base creation
- [x] RAG retrieval
- [x] Web chat widget
- [ ] Gemini API integration
- [ ] WhatsApp integration
- [ ] Production deployment

---

## Commands

```bash
# Run tests
pytest tests/ -v

# Format code
ruff format .

# Lint
ruff check .
```

---

**Marcus3 v1.0 | MVP Stage**
