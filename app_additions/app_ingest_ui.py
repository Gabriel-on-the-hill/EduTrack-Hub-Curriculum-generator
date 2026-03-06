# app_additions/app_ingest_ui.py
"""
Streamlit UI snippet to add a 'Add Curriculum' wizard.
Integrated with secure server-side search.
"""

import streamlit as st
import logging
from src.agents.scout import ScoutAgent
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
        col1, col2, col3 = st.columns(3)
        country = col1.text_input("Country", placeholder="e.g., UK")
        grade = col2.text_input("Grade Level", placeholder="e.g., Year 9")
        subject = col3.text_input("Subject", placeholder="e.g., Science")
        submitted = st.form_submit_button("🔍 Search Web")
    
    if submitted and country and grade and subject:
        with st.spinner("Translating query & Searching secure sources..."):
            try:
                import asyncio
                
                async def run_scout():
                    agent = ScoutAgent()
                    # Generate semantic queries
                    queries = await agent._generate_queries(country, grade, subject)
                    st.info(f"LLM Generated Semantic Queries: {queries}")
                    
                    # Execute searches
                    all_urls = []
                    for q in queries:
                        results = await agent._execute_search_queries([q], "us-en")
                        all_urls.extend(results)
                        
                    # Deduplicate and sort
                    unique_map = {}
                    for r in all_urls:
                        if r.url not in unique_map:
                            unique_map[r.url] = r
                    
                    final_list = list(unique_map.values())
                    # Sort official first
                    final_list.sort(key=lambda x: not x.official_hint)
                    return final_list

                # Run async scout agent from Streamlit UI
                results = asyncio.run(run_scout())
                
                # Convert domain objects back to standard dicts for rendering
                rendering_results = []
                for r in results:
                    rendering_results.append({
                        "title": r.title,
                        "url": r.url,
                        "snippet": r.snippet,
                        "domain": r.domain,
                        "official_hint": r.official_hint,
                        "final_url": r.url,
                        "content_type": "text/html"
                    })
                
                st.session_state["search_results"] = rendering_results
            except Exception as e:
                st.error(f"Search failed: {e}")

    # --- 2. RESULTS LIST ---
    if "search_results" in st.session_state and st.session_state["search_results"]:
        st.subheader("Search Results")
        results = st.session_state["search_results"]
        
        import html
        import requests
        API_BASE = st.secrets.get("api_base", "http://localhost:8000")

        for idx, r in enumerate(results):
            # Safe get for robust implementation
            title = r.get("title") or r.get("final_url") or r.get("url") or "Untitled"
            domain = r.get("domain") or ""
            final_url = r.get("final_url") or r.get("url")
            official = r.get("official_hint", False)
            ctype = r.get("content_type") or ""
            
            # Card-like layout
            with st.container(border=True):
                c1, c2 = st.columns([5, 1])
                
                # Title & Metadata
                c1.markdown(f"**[{html.escape(title)}]({html.escape(final_url)})**")
                c1.caption(f"_{domain}_ • {ctype}")
                c1.write(r.get('snippet', '')[:150] + "...")
                
                # Badge
                if official:
                    c1.markdown("✅ :green-background[Official Source]")
                elif domain.endswith(".edu"):
                     c1.markdown("🎓 :blue-background[Academic]")
                
                # Select Action
                if c2.button("Select", key=f"sel_{idx}"):
                    st.session_state["selected_url"] = final_url
                    st.session_state["selected_auth"] = "high" if official else "medium"
                    st.rerun()
                
                if c2.button("Preview", key=f"prev_{idx}"):
                    try:
                        # Simple fetch for preview (sync for now)
                        preview_resp = requests.get(final_url, timeout=5)
                        if preview_resp.ok:
                             st.code(preview_resp.text[:500] + "...")
                        else:
                             st.error(f"Preview failed: {preview_resp.status_code}")
                    except Exception as e:
                        st.error(f"Preview error: {e}")

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
