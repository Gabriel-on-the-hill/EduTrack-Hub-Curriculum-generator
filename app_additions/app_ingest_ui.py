# app_additions/app_ingest_ui.py
"""
Streamlit UI snippet to add a 'Add Curriculum' wizard.
Integrate the functions into your main app.py.
"""

import streamlit as st
try:
    from src.ingestion.worker import ingest_sync
    # Optional: Import RQ if you want to implement async here
    from redis import Redis
    from rq import Queue
    import os
    REDIS_URL = os.getenv("REDIS_URL")
except ImportError:
    ingest_sync = None
    REDIS_URL = None

def add_curriculum_tab(current_user_id: str):
    st.header("Add Curriculum")
    if not ingest_sync:
        st.error("Ingestion module not found. Please install requirements.")
        return

    query = st.text_input("Search query (e.g., 'UK Year 6 History Curriculum')", "")
    if st.button("Search Web"):
        st.info("Searching the web for candidate documents...")
        st.warning("Search provider not enabled in client. Paste a source URL to ingest.")
        
    source_url = st.text_input("Or paste a direct source URL (PDF/HTML)", "")
    
    # Simple Mode Selection
    mode = st.radio("Ingestion Mode", ("Synchronous (Debug)", "Asynchronous (Production)"))
    
    if st.button("Ingest"):
        if not source_url:
            st.error("Please provide a source URL.")
            return
            
        if mode.startswith("Synchronous"):
            with st.spinner("Ingesting..."):
                try:
                    res = ingest_sync(source_url)
                    st.success("Ingestion Complete!")
                    st.json(res.dict())
                except Exception as e:
                    st.error(f"Ingestion Failed: {e}")
        else:
            # Async logic using RQ directly if configured
            if REDIS_URL:
                try:
                    conn = Redis.from_url(REDIS_URL)
                    q = Queue("ingest", connection=conn)
                    job = q.enqueue(ingest_sync, source_url)
                    st.success(f"Job enqueued: {job.id}")
                except Exception as e:
                    st.error(f"Redis Error: {e}")
            else:
                st.warning("Redis not configured. Falling back to Synchronous.")
                try:
                    res = ingest_sync(source_url)
                    st.success("Ingestion Complete!")
                    st.json(res.dict())
                except Exception as e:
                    st.error(f"Ingestion Failed: {e}")
