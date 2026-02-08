import os
import sys
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Force reload of .env
load_dotenv(override=True)

def verify_connection():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL not found in .env")
        sys.exit(1)
        
    print(f"🔄 Connecting to: {db_url.split('@')[-1]}") # Print only host for privacy
    
    try:
        engine = create_engine(db_url)
        with engine.connect() as conn:
            # 1. Basic Connection Test
            conn.execute(text("SELECT 1"))
            print("✅ Connection Successful!")
            
            # 2. Schema Check
            result = conn.execute(text("SELECT count(*) FROM curricula"))
            count = result.scalar()
            print(f"✅ Schema Verified. Found {count} curricula.")
            
    except Exception as e:
        print(f"\n❌ CONNECTION FAILED: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    verify_connection()
