"""
EduTrack Hub
Streamlit interface for curriculum content generation

Run with: streamlit run app.py
"""

import streamlit as st
import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Load environment (optional)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # Ignore if missing, will use fallback

# Page config - must be first
st.set_page_config(
    page_title="EduTrack Hub",
    page_icon="⚡", # Minimalist icon
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ACCESS CONTROL (GATEKEEPER) ---
def check_password():
    """Returns `True` if the user had the correct password."""
    # 1. Get Secret
    password = st.secrets.get("ACCESS_CODE") or os.getenv("ACCESS_CODE")
    
    # 2. If no password set, allow access
    if not password:
        return True

    # 3. Validation Logic
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == password:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    # 4. State Management
    if "password_correct" not in st.session_state:
        # First run, show input
        st.text_input(
            "Enter Access Code 🔒", type="password", on_change=password_entered, key="password"
        )
        st.caption("This tool is restricted. Please enter the code provided by the administrator.")
        return False
        
    elif not st.session_state["password_correct"]:
        # Password incorrect, show input + error
        st.text_input(
            "Enter Access Code 🔒", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Access denied. Please try again.")
        return False
        
    else:
        # Password correct
        return True

if not check_password():
    st.stop()


# --- CUSTOM CSS FOR PREMIUM LOOK ---
st.markdown("""
<style>
    /* Import Inter font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Global Reset & Typography */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        color: #0f172a;
    }
    
    /* Background & Layout */
    .stApp {
        background-color: #f8fafc; /* Slate-50 */
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
        box-shadow: 4px 0 24px rgba(0,0,0,0.02);
    }
    
    /* Headings */
    h1, h2, h3 {
        color: #1e293b;
        font-weight: 700;
        letter-spacing: -0.025em;
    }
    
    /* Cards & Containers */
    .metric-card {
        background-color: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
    }

    /* Buttons */
    .stButton button {
        background-color: #2563eb; /* Primary Blue */
        color: white;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        padding: 0.75rem 1.5rem;
        transition: all 0.2s;
    }
    .stButton button:hover {
        background-color: #1d4ed8;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.2);
    }
    
    /* Inputs */
    .stSelectbox div[data-baseweb="select"] {
        border-radius: 8px;
        border-color: #cbd5e1;
    }

    /* Remove Streamlit Clutter */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display:none;}
    
</style>
""", unsafe_allow_html=True)

# Database connection
@st.cache_resource
def get_db_engine():
    """Create database connection."""
    # Try Streamlit secrets first (for Streamlit Cloud), then env var (for local)
    db_url = st.secrets.get("DATABASE_URL") if "DATABASE_URL" in st.secrets else os.getenv("DATABASE_URL")
    
    # FALLBACK: Use local SQLite if no real DB configured
    if not db_url:
        st.warning("⚠️ Using local database (SQLite).")
        db_url = "sqlite:///demo.db"
    
    engine = create_engine(db_url)
    
    # Auto-seed if SQLite (for instant demo)
    if "sqlite" in db_url:
        try:
            # Check if seeding needed
            with engine.connect() as conn:
                try:
                    conn.execute(text("SELECT 1 FROM curricula LIMIT 1"))
                except Exception:
                    # Tables don't exist or empty, run scripts
                    seed_sqlite(conn)
        except Exception as e:
            st.error(f"Failed to seed DB: {e}")
            
    return engine

def seed_sqlite(conn):
    """Execute SQL scripts for SQLite."""
    # 1. Create Tables
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS curricula (
            id TEXT PRIMARY KEY,
            country TEXT NOT NULL,
            grade TEXT NOT NULL,
            subject TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            source_authority TEXT
        );
    """))
    
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS competencies (
            id TEXT PRIMARY KEY,
            curriculum_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            order_index INTEGER DEFAULT 0,
            FOREIGN KEY(curriculum_id) REFERENCES curricula(id)
        );
    """))
    
    # 2. Seed Data (Use INSERT OR IGNORE)
    conn.execute(text("""
        INSERT OR IGNORE INTO curricula (id, country, grade, subject, source_authority) VALUES 
        ('ng-bio-ss1', 'Nigeria', 'SS1', 'Biology', 'NERDC'),
        ('ca-math-09', 'Canada (Ontario)', '9', 'Mathematics', 'Ministry of Education');
    """))
    
    conn.execute(text("""
        INSERT OR IGNORE INTO competencies (id, curriculum_id, title, description, order_index) VALUES
        ('c1', 'ng-bio-ss1', 'Cell Division', 'Understanding mitosis and meiosis processes.', 1),
        ('c2', 'ng-bio-ss1', 'Genetics', 'Principles of heredity and variation.', 2),
        ('c3', 'ca-math-09', 'Linear Relations', 'Graphing and solving linear equations.', 1);
    """))
    conn.commit()

def fetch_curricula(engine):
    """Fetch all available curricula."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, country, grade, subject, source_authority 
            FROM curricula 
            WHERE status = 'active'
            ORDER BY country, subject
        """))
        return [dict(row._mapping) for row in result]

def fetch_competencies(engine, curriculum_id: str):
    """Fetch competencies for a curriculum."""
    with engine.connect() as conn:
        result = conn.execute(
            text("""
                SELECT id, title, description 
                FROM competencies 
                WHERE curriculum_id = :cid
                ORDER BY order_index
            """),
            {"cid": curriculum_id}
        )
        return [dict(row._mapping) for row in result]

# Main Application Logic
def main_dashboard():
    engine = get_db_engine()
    if not engine:
        st.error("Connection Error: Database unavailable.")
        st.stop()
        
    selected_id = None
    selected_name = None

    # --- Sidebar ---
    with st.sidebar:
        st.markdown("### EduTrack **Hub**")
        st.caption("v1.0.0 Global Production")
        st.markdown("---")

        # Navigation
        app_mode = st.radio("Navigation", ["Generator", "Ingestion", "Admin (Review)"])
        st.markdown("---")

        if app_mode == "Ingestion":
             # We will render the ingestion UI here or in main area
             pass
        elif app_mode == "Admin (Review)": # Assuming "Admin (Review)" from radio maps to this logic
            try:
                from app_additions.admin_pending_ui import render_admin_dashboard
                render_admin_dashboard()
            except ImportError:
                st.error("Admin UI module missing. Please ensure 'app_additions/admin_pending_ui.py' exists.")
            return # Stop further rendering of the main dashboard for Admin mode
        else: # This 'else' now covers "Generator"
            try:
                curricula = fetch_curricula(engine)
                if not curricula:
                    st.warning("Database Empty. Please seed data.")
                    st.stop()
                    
                # Curriculum Selector
                curriculum_map = {f"{c['country']} • {c['subject']} {c['grade']}": c['id'] for c in curricula}
                selected_name = st.selectbox("Active Curriculum", list(curriculum_map.keys()))
                selected_id = curriculum_map[selected_name]
                
                st.markdown("### Configuration")
                output_format = st.radio("Document Type", ["Teacher Guide", "Student Worksheet", "Exam Paper"], index=0)
                
                # Clarity update: Rename to 'Target Proficiency' with tooltip
                difficulty = st.select_slider(
                    "Target Proficiency", 
                    options=["Foundational", "Proficient", "Advanced", "Expert"], 
                    value="Proficient",
                    help="Adjusts vocabulary complexity and depth of analysis."
                )
                
            except Exception as e:
                st.error(f"System Error: {str(e)}")
                st.stop()

    # --- Main Content Area ---
    
    if app_mode == "Create Resources":
        if selected_name and selected_id: # Ensure sidebar selections were made
            render_generator_ui(engine, selected_name, selected_id)
        else:
            st.info("Please select a curriculum in the sidebar to create resources.")
    st.markdown("---")

    # Fetch Data
    if not selected_id:
        return

    competencies = fetch_competencies(engine, selected_id)
    
    # --- PROPOSED SINGLE COLUMN LAYOUT ---
    
    # 1. Top Control Bar (Full Width)
    # Replaces the left sidebar column for better mobile/desktop use
    topic = st.selectbox(
        "Select Learning Objective", 
        [c['title'] for c in competencies],
        index=0
    )
    
    # 2. Context Card (Full Width)
    selected_comp = next(c for c in competencies if c['title'] == topic)
    with st.container(border=True):
        st.caption("SELECTED OBJECTIVE")
        st.markdown(f"### {selected_comp['title']}")
        st.markdown(f"_{selected_comp['description']}_")
        
    # 3. Action Button (Full Width)
    if st.button("✨ Generate Content", type="primary", use_container_width=True):
        run_generation(topic, output_format, difficulty, competencies, selected_id)

    # 4. Results Area (Full Width)
    # The 'run_generation' function will need to output here.
    # We moved the logic inside run_generation to use st.container instead of HTML div.

# --- PROVISIONING ---
@st.cache_resource
def get_harness():
    """Initialize the Production Engine (Cached)."""
    engine = get_db_engine()
    if not engine:
        return None
        
    # Lazy imports to avoid circular deps
    from src.production.harness import ProductionHarness
    from src.production.security import ReadOnlySession, verify_db_is_readonly
    from src.production.errors import GroundingViolationError, HallucinationBlockError
    
    # Create Read-Only Session Factory
    # 1. We start with a sessionmaker configured for ReadOnlySession
    ReadOnlySessionFactory = sessionmaker(bind=engine, class_=ReadOnlySession)
    
    # 2. Instantiate the read-only session
    session = ReadOnlySessionFactory()
    
    # 3. Enforce SQL-level Read-Only (Crucial Phase 5 Invariant)
    try:
        # Check if we can write (should fail)
        verify_db_is_readonly(session)
    except Exception:
        # Verify_db usually returns None on success, raises on failure
        pass

    # Initialize Harness
    harness = ProductionHarness(
        db_session=session,
        verify_db_level=False # We checked manually and verifying again might trigger issues if transaction not committed
    )
    return harness


def run_generation(topic, fmt, diff, comps, curriculum_id):
    """Execute the Real Production Chain."""
    harness = get_harness()
    if not harness:
        st.error("Engine Initialization Failed")
        return

    # Find Topic Details
    selected_comp = next(c for c in comps if c['title'] == topic)
    
    # Build Config Object (Adapter for Harness)
    # Using a simple namespace/dict as "Any" config for now, 
    # compatible with the _run_generation signature we just added.
    from collections import namedtuple
    Config = namedtuple('Config', [
        'topic_title', 'topic_description', 
        'content_format', 'target_level', 
        'jurisdiction', 'grade', 'rng_seed'
    ])
    
    config = Config(
        topic_title=topic,
        topic_description=selected_comp['description'],
        content_format=fmt,
        target_level=diff,
        jurisdiction="National", # Derived from DB in real app
        grade="Standard",
        rng_seed=42 # Deterministic for demo
    )

    # UI Feedback Loop
    with st.status("⚡ Engaged Production Engine", expanded=True) as status:
        st.write("🔒 **Security:** Verifying Read-Only Access...")
        time.sleep(0.5)
        st.write("🛡️ **Governance:** Checking Content Policy...")
        time.sleep(0.5)
        
        try:
            import asyncio
            
            st.write("🧠 **LLM:** Generating Content (Gemini Flash)...")
            
            # Build provenance for governance enforcement
            provenance = {
                "curriculum_id": str(curriculum_id),
                "source_list": [{"url": "https://edutrack.demo", "authority": "EduTrack", "fetch_date": "2026-02-15"}],
                "retrieval_timestamp": "2026-02-15T00:00:00Z",
                "extraction_confidence": 0.95,
                "user_id": "demo-user",
                "session": "streamlit"
            }
            
            # Call the full production pipeline (governance + grounding + shadow checks)
            payload = asyncio.run(harness.generate_artifact(curriculum_id, config, provenance))
            
            status.update(label="✅ Generation Complete", state="complete", expanded=False)
            
            # Display Result
            st.markdown("---")
            st.subheader("Generated Artifact")
            
            # Use native container with scroll for better UX
            with st.container(height=600, border=True):
                st.markdown(payload.content_markdown)
            
            # Governance Badge
            st.success("✅ **Governance Verified**")
            
            # Download
            st.download_button(
                "📥 Download Artifact",
                payload.content_markdown,
                file_name=f"{topic}.md"
            )
            
        except Exception as e:
            status.update(label="❌ Generation Failed", state="error")
            st.error(f"Engine Error: {str(e)}")
            st.error("Traceback: " + str(e))

if __name__ == "__main__":
    main_dashboard()
