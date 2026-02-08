"""
Unit Tests for Production Security (Phase 5)

Verifies that ReadOnlySession strictly forbids write operations.
"""

import pytest
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.production.security import ReadOnlySession

Base = declarative_base()

class MockModel(Base):
    """Simple model for testing."""
    __tablename__ = "mock_items"
    id = Column(Integer, primary_key=True)
    name = Column(String)

@pytest.fixture
def memory_db():
    """Create an in-memory DB with schema."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine

def test_readonly_session_blocks_insert(memory_db):
    """Verify that ReadOnlySession raises PermissionError on insert."""
    # Create session factory using ReadOnlySession
    Session = sessionmaker(bind=memory_db, class_=ReadOnlySession)
    session = Session()
    
    # Attempt to add an object
    item = MockModel(name="forbidden_write")
    session.add(item)
    
    # Verify flush raises error
    with pytest.raises(PermissionError, match="Generate-Safety Violation"):
        session.flush()

def test_readonly_session_blocks_update(memory_db):
    """Verify that update fails too."""
    # 1. Setup data using a normal session first
    NormalSession = sessionmaker(bind=memory_db)
    normal_session = NormalSession()
    item = MockModel(name="initial")
    normal_session.add(item)
    normal_session.commit()
    item_id = item.id
    normal_session.close()
    
    # 2. Try to update using ReadOnlySession
    ReadOnly = sessionmaker(bind=memory_db, class_=ReadOnlySession)
    ro_session = ReadOnly()
    
    fetched_item = ro_session.get(MockModel, item_id)
    fetched_item.name = "hacked"
    
    # Verify flush raises error
    with pytest.raises(PermissionError, match="Generate-Safety Violation"):
        ro_session.flush()

def test_readonly_session_blocks_delete(memory_db):
    """Verify that delete fails too."""
    # 1. Setup data
    NormalSession = sessionmaker(bind=memory_db)
    normal_session = NormalSession()
    item = MockModel(name="to_delete")
    normal_session.add(item)
    normal_session.commit()
    item_id = item.id
    normal_session.close()
    
    # 2. Try to delete
    ReadOnly = sessionmaker(bind=memory_db, class_=ReadOnlySession)
    ro_session = ReadOnly()
    
    fetched_item = ro_session.get(MockModel, item_id)
    ro_session.delete(fetched_item)
    
    # Verify flush raises error
    with pytest.raises(PermissionError, match="Generate-Safety Violation"):
        ro_session.flush()
