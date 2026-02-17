# app_additions/app_ingest_ui.py
"""
Streamlit UI snippet to add a 'Add Curriculum' wizard.
Integrated with secure server-side search.
"""

import streamlit as st
import logging
from src.ingestion.search import search_web
from src.ingestion.gatekeeper import infer_authority
from src.ingestion.worker import ingest_sync

# Optional: Import RQ
try:
    from redis import Redis
    from rq import Queue
    import os
    REDIS_URL = os.getenv("REDIS_URL")
except ImportError:
    REDIS_URL = None

def add_curriculum_tab(current_user_id: str):
    st.header("Search & Add Curriculum")
    
    # --- 1. SEARCH SECTION ---
    with st.form("search_form"):
        col1, col2 = st.columns([4, 1])
        query = col1.text_input("Find Official Curricula", placeholder="e.g., 'UK Year 6 History Curriculum'")
        submitted = col2.form_submit_button("🔍 Search Web")
    
    if submitted and query:
        with st.spinner("Searching secure sources..."):
            try:
                # Direct call to backend logic (simulating API call for now since we are in-process)
                # In a split deployment, this would be requests.post(API_URL)
                results = search_web(query, max_results=10)
                st.session_state["search_results"] = results
            except Exception as e:
                st.error(f"Search failed: {e}")

    # --- 2. RESULTS LIST ---
    if "search_results" in st.session_state and st.session_state["search_results"]:
        st.subheader("Search Results")
        results = st.session_state["search_results"]
        
        for idx, r in enumerate(results):
            authority = infer_authority(r['url'])
            
            # Card-like layout
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                
                # Title & Metadata
                title_clean = r.get('title', 'Untitled')
                c1.markdown(f"**{title_clean}**")
                c1.caption(f"{r['url'][:60]}...")
                c1.write(r.get('snippet', '')[:150] + "...")
                
                # Badge
                if authority == "high":
                    c1.markdown("✅ :green-background[Official Source]")
                elif authority == "medium":
                    c1.markdown("🎓 :blue-background[Academic/Edu]")
                else:
                    c1.markdown("⚠️ :orange-background[Third-Party]")

                # Select Action
                if c2.button("Select", key=f"sel_{idx}"):
                    st.session_state["selected_url"] = r['url']
                    st.session_state["selected_auth"] = authority
                    st.rerun()

    st.markdown("---")

    # --- 3. INGESTION FORM ---
    st.subheader("Ingest Selection")
    
    # Auto-fill from selection or manual paste
    source_url = st.text_input(
        "Source URL (PDF/HTML)", 
        value=st.session_state.get("selected_url", ""),
        key="ingest_url_input"
    )
    
    if source_url:
        # Pre-check info
        auth_level = st.session_state.get("selected_auth", infer_authority(source_url))
        
        if auth_level == "high":
            st.info("✅ Trusted Official Domain detected.")
        elif auth_level == "medium":
            st.info("🎓 Academic/Educational Domain detected.")
        else:
            st.warning("⚠️ Third-party domain. Please verify this is a legitimate curriculum source.")

        # Governance Checkbox
        consent = st.checkbox(
            "I confirm this is official/public content or I have rights to ingest it.",
            value=(auth_level == "high") # Auto-check for .gov, user must check for others
        )
        
        # Mode
        mode = st.radio("Mode", ("Synchronous (Debug)", "Asynchronous (Production)"), horizontal=True)

        if st.button("🚀 Start Ingestion", type="primary"):
            if not consent:
                st.error("⛔ You must confirm rights to proceed.")
                return
            
            if mode.startswith("Synchronous"):
                with st.spinner("Ingesting & Processing..."):
                    try:
                        res = ingest_sync(source_url)
                        if res.status == "success":
                            st.success("Ingestion Complete!")
                            st.json(res.dict())
                        elif res.status == "pending_manual_review":
                            st.warning("Job Queued for Manual Review (License/Auth Check)")
                            st.json(res.dict())
                        else:
                            st.error(f"Ingestion Rejected: {res}")
                    except Exception as e:
                        st.error(f"Ingestion Error: {e}")
            else:
                # Async
                if REDIS_URL:
                    try:
                        conn = Redis.from_url(REDIS_URL, decode_responses=True)
                        q = Queue("ingest", connection=conn)
                        job = q.enqueue(ingest_sync, source_url)
                        st.success(f"Job Enqueued! ID: {job.id}")
                    except Exception as e:
                        st.error(f"Redis Error: {e}")
                else:
                    st.warning("Redis not configured. Creating Sync Job instead.")
                    ingest_sync(source_url)
                    st.success("Done (Sync Fallback)")
