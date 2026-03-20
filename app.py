"""
EduTrack Hub
Streamlit interface for curriculum content generation

Run with: streamlit run app.py
"""

import streamlit as st
import os
from sqlalchemy import create_engine, text

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
    try:
        password = st.secrets.get("ACCESS_CODE") or os.getenv("ACCESS_CODE")
    except Exception:
        password = os.getenv("ACCESS_CODE")
    
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
            country_code TEXT,
            jurisdiction_level TEXT,
            jurisdiction_name TEXT,
            grade TEXT NOT NULL,
            subject TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            confidence_score REAL,
            source_url TEXT,
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
    
    # 2. Seed Data (Use INSERT OR IGNORE) — Real curriculum framework language
    conn.execute(text("""
        INSERT OR IGNORE INTO curricula (
            id, country, country_code, jurisdiction_level, jurisdiction_name, 
            grade, subject, source_authority
        ) VALUES 
        ('ng-bio-ss1', 'Nigeria', 'NG', 'National', 'NERDC', 'SS1', 'Biology', 'NERDC'),
        ('ca-math-09', 'Canada', 'CA', 'Provincial', 'Ontario Ministry of Education', '9', 'Mathematics', 'Ministry of Education'),
        ('uk-sci-ks3', 'United Kingdom', 'GB', 'National', 'Department for Education', 'KS3', 'Science', 'DfE'),
        ('gh-ict-jhs2', 'Ghana', 'GH', 'National', 'NaCCA', 'JHS 2', 'ICT', 'NaCCA'),
        ('ke-eng-f3', 'Kenya', 'KE', 'National', 'KICD', 'Form 3', 'English', 'KICD');
    """))
    
    conn.execute(text("""
        INSERT OR IGNORE INTO competencies (id, curriculum_id, title, description, order_index) VALUES
        ('c1', 'ng-bio-ss1', 'Cell Division', 'Describe the stages of mitosis and meiosis, and explain their significance in growth, repair, and sexual reproduction.', 1),
        ('c2', 'ng-bio-ss1', 'Genetics and Heredity', 'Explain the principles of heredity, genetic crosses, and predict offspring phenotypes using Punnett squares.', 2),
        ('c3', 'ng-bio-ss1', 'Ecology and Environment', 'Analyse food chains, food webs, and energy flow in ecosystems, and discuss human impact on the environment.', 3),
        ('c4', 'ca-math-09', 'Linear Relations', 'Determine the equation of a line given sufficient information and graph linear relations using intercepts and slope.', 1),
        ('c5', 'ca-math-09', 'Solving Equations', 'Solve first-degree equations involving one variable, including equations with fractional coefficients.', 2),
        ('c6', 'ca-math-09', 'Measurement and Geometry', 'Determine the optimal values of various measurements using algebraic and geometric reasoning.', 3),
        ('c7', 'uk-sci-ks3', 'Cells and Organisation', 'Describe the structure of plant and animal cells, and explain how cells are organised into tissues, organs, and systems.', 1),
        ('c8', 'uk-sci-ks3', 'Atoms and the Periodic Table', 'Describe the structure of an atom and use the periodic table to predict the properties of elements.', 2),
        ('c9', 'uk-sci-ks3', 'Forces and Motion', 'Calculate speed from distance-time data, describe the effects of balanced and unbalanced forces, and explain friction.', 3),
        ('c10', 'gh-ict-jhs2', 'Introduction to Coding', 'Write simple programs using Scratch or Python to solve everyday problems, applying sequence, selection, and iteration.', 1),
        ('c11', 'gh-ict-jhs2', 'Spreadsheet Applications', 'Use spreadsheet software to enter data, create formulae, and produce appropriate charts for data presentation.', 2),
        ('c12', 'gh-ict-jhs2', 'Internet Safety', 'Identify online risks and demonstrate safe practices for browsing, social media, and digital communication.', 3),
        ('c13', 'ke-eng-f3', 'Creative Writing', 'Compose imaginative and descriptive essays demonstrating varied sentence structures, figurative language, and coherent organisation.', 1),
        ('c14', 'ke-eng-f3', 'Oral Skills and Listening', 'Participate in debates and discussions using persuasive techniques, appropriate register, and active listening skills.', 2),
        ('c15', 'ke-eng-f3', 'Grammar and Usage', 'Apply advanced grammatical rules including reported speech, conditional sentences, and subject-verb agreement in writing.', 3);
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
        app_mode = st.radio("Navigation", ["Create Resources", "Add Curriculum", "Review Dashboard"])
        st.markdown("---")

        st.info(
            "**📚 Create Resources** — Generate teaching materials from your curricula\n\n"
            "**🔍 Add Curriculum** — Search & ingest new official curriculum sources\n\n"
            "**📋 Review Dashboard** — Approve or reject pending ingestion jobs"
        )

        with st.expander("Advanced Options"):
             if st.button("🧹 Clear Cache"):
                 st.cache_resource.clear()
                 st.cache_data.clear()
                 st.success("Cache Cleared!")
                 st.rerun()

        if app_mode == "Add Curriculum":
             try:
                 from app_additions.app_ingest_ui import add_curriculum_tab
                 add_curriculum_tab(st.session_state.get("user_id", "local_dev_user"))
             except ImportError as e:
                 st.error(f"Ingestion UI module missing: {e}")
             return
        elif app_mode == "Review Dashboard":
            try:
                from app_additions.admin_pending_ui import render_admin_dashboard
                render_admin_dashboard()
            except ImportError:
                st.error("Admin UI module missing. Please ensure 'app_additions/admin_pending_ui.py' exists.")
            return # Stop further rendering of the main dashboard for Admin mode
        else: # This 'else' now covers "Generator"
            try:
                from app_additions.resource_generation_ui import render_generation_admin_flow
                render_generation_admin_flow(
                    engine=engine,
                    fetch_curricula=fetch_curricula,
                    fetch_competencies=fetch_competencies,
                )
            except Exception as e:
                st.error(f"System Error: {str(e)}")
                st.stop()

if __name__ == "__main__":
    main_dashboard()
