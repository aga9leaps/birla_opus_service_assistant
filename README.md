# Birla Opus Chatbot

AI-powered chatbot for Birla Opus painting services with WhatsApp and Web support.

## Features

- **OTP-based Authentication** - Secure login with pre-approved phone numbers
- **Multi-Language Support** - Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, English
- **User Type Specific Responses** - Sales, Dealer, Contractor, Painter, Tester
- **RAG-powered Knowledge Base** - Products, processes, pricing, schemes
- **WhatsApp Integration Ready** - Twilio/Meta Cloud API support
- **Web Chat Widget** - Embeddable responsive chat interface

## Tech Stack

- **Backend:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL
- **Cache:** Redis
- **LLM:** Google Gemini 3 Flash (multi-language)
- **Container:** Docker

## Quick Start

### 1. Clone and Setup

```bash
cd /home/aga/marcus3-v1/projects/birla-opus-chatbot

# Create environment file
cp .env.example .env

# Add your Gemini API key to .env
# GEMINI_API_KEY=your-key-here
```

### 2. Run with Docker

```bash
cd docker
docker-compose up -d
```

### 3. Access the Application

- **Web Chat:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Health Check:** http://localhost:8000/api/v1/health

## Demo Users

| Phone Number | User Type | Name |
|--------------|-----------|------|
| 9876543210 | Sales | Rahul Sharma |
| 9876543211 | Dealer | Paint World |
| 9876543212 | Contractor | Ravi Kumar |
| 9876543213 | Painter | Suresh Painter |
| 1234567890 | Tester | Demo Tester |

For demo, OTP is returned in the API response.

## API Usage

### 1. Request OTP

```bash
curl -X POST http://localhost:8000/api/v1/auth/request-otp \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "919876543210"}'
```

Response:
```json
{
  "success": true,
  "message": "OTP sent to ******3210",
  "demo_otp": "123456"
}
```

### 2. Verify OTP

```bash
curl -X POST http://localhost:8000/api/v1/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{"phone_number": "919876543210", "otp_code": "123456"}'
```

Response:
```json
{
  "success": true,
  "message": "Welcome, Rahul Sharma! (sales)",
  "access_token": "eyJ...",
  "token_type": "bearer"
}
```

### 3. Send Chat Message

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "X-Session-ID: sess_123" \
  -d '{"message": "What is the price of interior paint?", "language": "en"}'
```

Response:
```json
{
  "message_id": "uuid",
  "response": "Based on the Birla Opus price list...",
  "sources": [...],
  "language": "en",
  "processing_time_ms": 1234
}
```

## Project Structure

```
birla-opus-chatbot/
├── config/
│   └── settings.py          # Configuration
├── src/
│   ├── api/
│   │   ├── main.py          # FastAPI app
│   │   └── routes.py        # API endpoints
│   ├── core/
│   │   ├── auth.py          # OTP authentication
│   │   ├── chat.py          # Chat service
│   │   └── rag.py           # Knowledge retrieval
│   └── data/
│       ├── models.py        # Database models
│       └── database.py      # DB connection
├── knowledge_base/          # Markdown knowledge files
├── web/
│   └── index.html           # Web chat widget
├── docker/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── nginx.conf
├── tests/
├── requirements.txt
└── README.md
```

## Knowledge Base

The knowledge base contains comprehensive information about:

- **Products** - Interior, Exterior, Waterproofing, Textures
- **Processes** - Application, surface preparation, dealer onboarding
- **Pricing** - Product prices and pack sizes
- **Schemes** - Dealer and contractor schemes
- **FAQs** - Common questions and answers
- **Certifications** - ISO, Green Pro, BIS standards
- **Testimonials** - Customer and dealer success stories

## Adding New Users

```bash
curl -X POST http://localhost:8000/api/v1/admin/users \
  -H "Content-Type: application/json" \
  -d '{
    "phone_number": "919999999999",
    "user_type": "dealer",
    "name": "New Dealer",
    "dealer_code": "DLR002",
    "region": "Mumbai"
  }'
```

## WhatsApp Integration

### Twilio Setup
1. Get Twilio WhatsApp sandbox number
2. Set environment variables in `.env`
3. Configure webhook URL: `https://your-domain/api/v1/webhook/whatsapp`

### Meta Cloud API Setup
1. Create Meta Business app
2. Configure WhatsApp Business API
3. Set webhook URL and verify token
4. Configure environment variables

## Development

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (or use Docker)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16
docker run -d -p 6379:6379 redis:7

# Run the application
python -m uvicorn src.api.main:app --reload
```

### Running Tests

```bash
pytest tests/ -v --cov=src
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| DATABASE_URL | PostgreSQL connection | postgresql://... |
| REDIS_URL | Redis connection | redis://localhost:6379/0 |
| GEMINI_API_KEY | Google Gemini API key | - |
| JWT_SECRET | JWT signing secret | - |
| DEBUG | Debug mode | true |

## License

Internal use only - Aditya Birla Group

## Contact

- **Support:** opuscare@adityabirla.com
- **Helpline:** 1800-120-1234
