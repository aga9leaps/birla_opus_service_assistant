"""
Birla Opus Chatbot - Authentication Service
OTP-based authentication with user type validation
"""
import random
import string
from datetime import datetime, timedelta
from typing import Optional, Tuple
import jwt
from sqlalchemy.orm import Session
import uuid

from config.settings import get_settings, USER_TYPE_PROMPTS
from src.data.models import User, OTPRequest, UserType, AuditLog

settings = get_settings()


class AuthService:
    """Authentication service with OTP verification."""

    def __init__(self, db: Session):
        self.db = db

    def generate_otp(self) -> str:
        """Generate a random OTP code."""
        return ''.join(random.choices(string.digits, k=settings.OTP_LENGTH))

    def request_otp(self, phone_number: str) -> Tuple[bool, str, Optional[str]]:
        """
        Request OTP for a phone number.
        Returns: (success, message, otp_for_demo)

        In production, OTP would be sent via SMS.
        For demo, we return the OTP in response.
        """
        # Normalize phone number
        phone_number = self._normalize_phone(phone_number)

        # Check if user exists and is approved
        user = self.db.query(User).filter(
            User.phone_number == phone_number,
            User.is_active == True
        ).first()

        if not user:
            self._log_audit("otp_request_denied", "auth", phone_number=phone_number,
                          details={"reason": "User not found or not approved"})
            return False, "Phone number not registered. Please contact admin.", None

        # Generate OTP
        otp_code = self.generate_otp()
        expires_at = datetime.utcnow() + timedelta(minutes=settings.OTP_EXPIRY_MINUTES)

        # Invalidate previous OTPs
        self.db.query(OTPRequest).filter(
            OTPRequest.user_id == user.id,
            OTPRequest.is_verified == False
        ).delete()

        # Create new OTP request
        otp_request = OTPRequest(
            user_id=user.id,
            phone_number=phone_number,
            otp_code=otp_code,
            expires_at=expires_at
        )
        self.db.add(otp_request)
        self.db.commit()

        self._log_audit("otp_requested", "auth", user_id=user.id,
                       phone_number=phone_number, user_type=user.user_type.value)

        # In production, send SMS here
        # For demo, return OTP in response
        return True, f"OTP sent to {phone_number[-4:].rjust(len(phone_number), '*')}", otp_code

    def verify_otp(self, phone_number: str, otp_code: str) -> Tuple[bool, str, Optional[str]]:
        """
        Verify OTP and generate JWT token.
        Returns: (success, message, jwt_token)
        """
        phone_number = self._normalize_phone(phone_number)

        # Find user
        user = self.db.query(User).filter(
            User.phone_number == phone_number,
            User.is_active == True
        ).first()

        if not user:
            return False, "Invalid phone number", None

        # Find valid OTP request
        otp_request = self.db.query(OTPRequest).filter(
            OTPRequest.user_id == user.id,
            OTPRequest.otp_code == otp_code,
            OTPRequest.is_verified == False,
            OTPRequest.expires_at > datetime.utcnow()
        ).first()

        if not otp_request:
            # Check if OTP exists but expired or wrong
            existing = self.db.query(OTPRequest).filter(
                OTPRequest.user_id == user.id,
                OTPRequest.is_verified == False
            ).first()

            if existing:
                existing.attempts += 1
                self.db.commit()

                if existing.attempts >= 3:
                    self._log_audit("otp_blocked", "auth", user_id=user.id,
                                   phone_number=phone_number,
                                   details={"reason": "Too many attempts"})
                    return False, "Too many attempts. Please request new OTP.", None

            return False, "Invalid or expired OTP", None

        # Mark OTP as verified
        otp_request.is_verified = True
        otp_request.verified_at = datetime.utcnow()

        # Update user
        user.is_verified = True
        user.last_login = datetime.utcnow()

        self.db.commit()

        # Generate JWT token
        token = self._generate_token(user)

        self._log_audit("login_success", "auth", user_id=user.id,
                       phone_number=phone_number, user_type=user.user_type.value)

        return True, f"Welcome, {user.name or 'User'}! ({user.user_type.value})", token

    def validate_token(self, token: str) -> Tuple[bool, Optional[dict]]:
        """
        Validate JWT token and return user info.
        Returns: (valid, user_info)
        """
        try:
            # PyJWT automatically validates exp when it's a Unix timestamp
            payload = jwt.decode(
                token,
                settings.JWT_SECRET,
                algorithms=[settings.JWT_ALGORITHM],
                options={"verify_exp": True}
            )
            return True, payload
        except jwt.ExpiredSignatureError:
            return False, None
        except (jwt.InvalidTokenError, jwt.DecodeError, ValueError):
            return False, None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == uuid.UUID(user_id)).first()

    def get_user_system_prompt(self, user_type: str) -> str:
        """Get user-type specific system prompt."""
        return USER_TYPE_PROMPTS.get(user_type, USER_TYPE_PROMPTS["painter"])

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number format."""
        # Remove spaces and special chars
        phone = ''.join(filter(str.isdigit, phone))
        # Add country code if not present
        if len(phone) == 10:
            phone = "91" + phone
        return phone

    def _generate_token(self, user: User) -> str:
        """Generate JWT token for user."""
        exp_time = datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRY_HOURS)
        payload = {
            "user_id": str(user.id),
            "phone": user.phone_number,
            "user_type": user.user_type.value,
            "name": user.name,
            "dealer_code": user.dealer_code,
            "contractor_id": user.contractor_id,
            "employee_id": user.employee_id,
            "region": user.region,
            "language": user.language_preference,
            "exp": int(exp_time.timestamp())  # Unix timestamp for JWT standard
        }
        return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

    def _log_audit(self, event_type: str, category: str, user_id=None,
                   phone_number=None, user_type=None, details=None):
        """Log audit event."""
        audit = AuditLog(
            event_type=event_type,
            event_category=category,
            user_id=user_id,
            user_phone=phone_number,
            user_type=user_type,
            details=details or {}
        )
        self.db.add(audit)
        self.db.commit()


def seed_demo_users(db: Session):
    """Seed demo users for testing."""
    demo_users = [
        {
            "phone_number": "919876543210",
            "user_type": UserType.SALES,
            "name": "Rahul Sharma",
            "employee_id": "EMP001",
            "region": "North",
        },
        {
            "phone_number": "919876543211",
            "user_type": UserType.DEALER,
            "name": "Paint World",
            "dealer_code": "DLR001",
            "region": "Delhi",
        },
        {
            "phone_number": "919876543212",
            "user_type": UserType.CONTRACTOR,
            "name": "Ravi Kumar",
            "contractor_id": "CON001",
            "region": "Mumbai",
        },
        {
            "phone_number": "919876543213",
            "user_type": UserType.PAINTER,
            "name": "Suresh Painter",
            "region": "Bangalore",
        },
        {
            "phone_number": "919876543214",
            "user_type": UserType.TESTER,
            "name": "Test User",
            "region": "All",
        },
        # Ravindra Manvi - Tester
        {
            "phone_number": "919611045139",
            "user_type": UserType.TESTER,
            "name": "Ravindra Manvi",
            "region": "All",
        },
        # Add a common test number
        {
            "phone_number": "911234567890",
            "user_type": UserType.TESTER,
            "name": "Demo Tester",
            "region": "All",
        },
        # Anand Ganesan - Testing
        {
            "phone_number": "919900418709",
            "user_type": UserType.TESTER,
            "name": "Anand Ganesan",
            "region": "All",
        },
    ]

    for user_data in demo_users:
        existing = db.query(User).filter(User.phone_number == user_data["phone_number"]).first()
        if not existing:
            user = User(**user_data, is_active=True)
            db.add(user)

    db.commit()
    print(f"Seeded {len(demo_users)} demo users")
