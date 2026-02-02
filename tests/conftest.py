"""
Birla Opus Chatbot - Test Configuration
"""
import pytest
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Set test environment
os.environ["ENV"] = "test"
os.environ["DEBUG"] = "true"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["JWT_SECRET"] = "test-secret-key"

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.data.models import Base, User, UserType
from src.data.database import get_db


# Test database setup
TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    # Create tables
    Base.metadata.create_all(bind=engine)

    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_user(db_session):
    """Create a test user."""
    user = User(
        phone_number="911234567890",
        user_type=UserType.TESTER,
        name="Test User",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def demo_users(db_session):
    """Create all demo users."""
    users = [
        User(
            phone_number="919876543210",
            user_type=UserType.SALES,
            name="Rahul Sharma",
            employee_id="EMP001",
            region="North",
            is_active=True,
        ),
        User(
            phone_number="919876543211",
            user_type=UserType.DEALER,
            name="Paint World",
            dealer_code="DLR001",
            region="Delhi",
            is_active=True,
        ),
        User(
            phone_number="919876543212",
            user_type=UserType.CONTRACTOR,
            name="Ravi Kumar",
            contractor_id="CON001",
            region="Mumbai",
            is_active=True,
        ),
        User(
            phone_number="919876543213",
            user_type=UserType.PAINTER,
            name="Suresh Painter",
            region="Bangalore",
            is_active=True,
        ),
    ]

    for user in users:
        db_session.add(user)

    db_session.commit()
    return users


@pytest.fixture
def knowledge_base_path():
    """Return path to knowledge base."""
    return str(project_root / "knowledge_base")
