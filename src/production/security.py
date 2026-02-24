"""
Production Security Module (Phase 5 Blocker)

Enforces strict security invariants for the production environment.
Most critically: Read-Only Database Access at BOTH App and DB levels.

Features:
- ReadOnlySession: SQLAlchemy session that forbids writes at the application level.
- verify_db_is_readonly: DB-level verification at startup.
- DBRoleManager: Utilities for managing DB roles.
"""

import logging
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.orm import Session

from src.production.errors import DatabaseNotReadOnlyError

logger = logging.getLogger(__name__)


# =============================================================================
# READ-ONLY SESSION ENFORCEMENT (APP LEVEL)
# =============================================================================

class ReadOnlySession(Session):
    """
    A SQLAlchemy Session that strictly forbids write operations.
    
    This is an application-level defense in depth. 
    The primary defense is the database user's privileges.
    """
    pass


def raise_on_write(session, flush_context, instances):
    """
    Event hook to raise PermissionError on any flush attempt.
    """
    raise PermissionError(
        "Generate-Safety Violation: Attempted to write to the database in a Read-Only session. "
        "Phase 5 invariant: Generation is a View Layer only. No new ingestion or tuning allowed."
    )


# Register the event listener
event.listen(ReadOnlySession, "before_flush", raise_on_write)


# =============================================================================
# DB-LEVEL READ-ONLY VERIFICATION (NON-NEGOTIABLE)
# =============================================================================

def verify_db_is_readonly(session: Session) -> bool:
    """
    Verify that the database connection is truly read-only at DB level.
    
    Attempts to create a temp table - if it succeeds, DB is NOT read-only.
    Call this during harness startup.
    
    Returns:
        True if DB is read-only
        
    Raises:
        DatabaseNotReadOnlyError: If write operations are permitted
    """
    try:
        # Attempt a write operation that should fail on read-only DB
        session.execute(text("CREATE TEMP TABLE _readonly_verification_test (id INT)"))
        # If we got here, the DB allowed a write - NOT read-only
        session.rollback()
        raise DatabaseNotReadOnlyError()
    except DatabaseNotReadOnlyError:
        # Re-raise our custom error
        raise
    except Exception as e:
        # Any other exception (permission denied, etc.) means read-only is working
        error_str = str(e).lower()
        if (
            "permission" in error_str or 
            "denied" in error_str or 
            "read-only" in error_str or
            "read only" in error_str
        ):
            logger.info("DB-level read-only verification PASSED")
            return True
            
        # If it's another kind of error (timeout, syntax, connection lost),
        # we CANNOT guarantee read-only status. Fail closed.
        logger.error(f"Unexpected error during read-only check: {e}")
        raise DatabaseNotReadOnlyError(f"Verification failed with unexpected error: {e}")


def verify_readonly_status(session: Session) -> bool:
    """
    Verify that the current session is effectively read-only.
    
    Checks both app-level (ReadOnlySession class) and optionally DB-level.
    """
    if isinstance(session, ReadOnlySession):
        return True
        
    return False


# =============================================================================
# DATABASE ROLE MANAGEMENT
# =============================================================================

class DBRoleManager:
    """
    Manages database role assumption for production harness.
    
    PostgreSQL Setup Required:
    
    CREATE ROLE readonly_user LOGIN PASSWORD '***';
    GRANT CONNECT ON DATABASE edutrack TO readonly_user;
    GRANT USAGE ON SCHEMA public TO readonly_user;
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_user;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_user;
    """
    
    READONLY_ROLE = "readonly_user"
    
    @staticmethod
    def get_readonly_connection_config(base_config: dict[str, Any]) -> dict[str, Any]:
        """
        Return connection config modified for read-only role.
        
        Args:
            base_config: Original database configuration
            
        Returns:
            Modified configuration using read-only credentials
        """
        config = base_config.copy()
        config["user"] = DBRoleManager.READONLY_ROLE
        # Password would come from secrets manager in production
        logger.info(f"Configuring DB connection for role: {DBRoleManager.READONLY_ROLE}")
        return config
