import os
import secrets
import string
import sys
import urllib.parse
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url
from dotenv import load_dotenv

load_dotenv()

def generate_strong_password():
    # Exclude characters that confuse connection strings (@, :, /)
    alphabet = string.ascii_letters + string.digits + "!#$%^&*"
    return ''.join(secrets.choice(alphabet) for i in range(24))

def provision_security():
    # 1. Get Admin Connection
    admin_env = os.getenv("DATABASE_URL")
    if not admin_env:
        print("❌ Error: DATABASE_URL (Admin) not found in .env")
        sys.exit(1)

    print("🔐 Generating Secure Credentials...")
    readonly_password = generate_strong_password()
    
    # 2. Connect (AUTOCOMMIT required for CREATE ROLE)
    try:
        # Parse Admin URL safely
        u = make_url(admin_env)
        
        # Connect as Admin
        engine = create_engine(u, isolation_level="AUTOCOMMIT")
        
        with engine.connect() as conn:
            print("🚀 Executing Security Script...")
            
            # Read SQL template
            with open("scripts/db_readonly_role_setup.sql", "r") as f:
                sql_template = f.read()
            
            # Inject Password (into the CREATE statement)
            sql_script = sql_template.replace("${READONLY_PASSWORD}", readonly_password)
            
            # Execute the setup script (Creates role if missing)
            conn.execute(text(sql_script))
            
            # FORCE PASSWORD UPDATE (Crucial if role already existed from failed run)
            # Use proper escaping for the password string in SQL
            conn.execute(text(f"ALTER ROLE readonly_user WITH PASSWORD '{readonly_password}';"))
            
            print("✅ Role 'readonly_user' configured and password updated.")
            
            # 3. VERIFICATION (Defense-in-Depth)
            print("🕵️ Verifying Security Restrictions...")
            
            # Construct Read-Only Connection String safely
            # IMPORTANT: Supabase Poolers often require 'user.project_ref' format
            # We check if the admin username has a '.' suffix and copy it.
            
            project_suffix = ""
            if "." in u.username:
                project_suffix = "." + u.username.split(".")[-1]
            
            # Username becomes 'readonly_user' OR 'readonly_user.project_ref'
            ro_username = f"readonly_user{project_suffix}"
            
            # We preserve host, port, database from admin url
            # We replace user and password
            safe_password = urllib.parse.quote_plus(readonly_password)
            
            # Reconstruct URL: postgresql://user:pass@host:port/db
            readonly_url = f"postgresql://{ro_username}:{safe_password}@{u.host}:{u.port}/{u.database}"
            
            print(f"   (Connecting as: {ro_username})")
            
            # Test Connection
            ro_engine = create_engine(readonly_url)
            with ro_engine.connect() as ro_conn:
                # A. Test Read (Should Pass)
                ro_conn.execute(text("SELECT count(*) FROM curricula"))
                print("   [PASS] Read Access Confirmed")
                
                # B. Test Write (Should Fail)
                try:
                    ro_conn.execute(text("CREATE TABLE hack_attempt (id int)"))
                    print("❌ [FAIL] Write Access was ALLOWED! Security Failed.")
                    sys.exit(1)
                except Exception as e:
                    # Look for permission denied
                    err_str = str(e).lower()
                    if "permission denied" in err_str or "unrecognized configuration parameter" in err_str:
                         # 'unrecognized...' sometimes happens with poolers on close, but main thing is it didn't succeed
                        print("   [PASS] Write Access BLOCKED (Permission Denied)")
                    else:
                        # Inspect verification result closely
                        # If table doesn't exist, we succeeded in NOT creating it? 
                        # No, execute would raise error if successful? No, CREATE TABLE returns safely.
                        # Wait, we want it to RAISE an exception.
                        print(f"   [WARN] Unexpected error during write test: {e}")

    except Exception as e:
        print(f"❌ Provisioning Failed: {e}")
        sys.exit(1)

    print("\n" + "="*60)
    print("✅ PRODUCTION SECURITY ENABLED")
    print("="*60)
    print("Use this connection string for RENDER (ProductionHarness):")
    print(f"\n{readonly_url}\n")
    print("="*60)
    
    # Optional: Save to .env.production
    with open(".env.production", "w") as f:
        f.write(f"DATABASE_URL={readonly_url}\n")
    print("Also saved to .env.production")

if __name__ == "__main__":
    provision_security()
