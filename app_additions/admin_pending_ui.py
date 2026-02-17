# app_additions/admin_pending_ui.py
import streamlit as st
import requests
import os

API_BASE = os.environ.get("API_BASE", "http://localhost:8000")

def render_admin_dashboard():
    st.title("Ingestion - Pending Manual Review")

    # Fetch pending jobs from backend endpoint
    try:
        res = requests.get(f"{API_BASE}/api/admin/pending_jobs")
        if res.status_code != 200:
            st.error("Unable to fetch pending jobs: " + res.text)
            return

        jobs = res.json().get("jobs", [])
    except Exception as e:
        st.error(f"Connection error: {e}")
        return

    if not jobs:
        st.info("No pending ingestion jobs.")
    else:
        for job in jobs:
            with st.expander(f"Job {job['job_id']} - {job['source_url']}"):
                st.write("Requested by:", job.get("requested_by"))
                st.write("Decision reason:", job.get("decision_reason"))
                if st.button(f"Preview {job['job_id']}", key=f"preview-{job['job_id']}"):
                    try:
                        pr = requests.get(f"{API_BASE}/api/ingest/preview", params={"url": job["source_url"]})
                        if pr.status_code == 200:
                            st.text_area("Preview snippet", pr.json().get("preview_snippet",""), height=200)
                        else:
                            st.error("Preview failed: " + pr.text)
                    except Exception as e:
                        st.error(f"Preview error: {e}")

                col1, col2 = st.columns(2)
                if col1.button(f"Approve {job['job_id']}", key=f"approve-{job['job_id']}"):
                    try:
                        r = requests.post(f"{API_BASE}/api/admin/approve", json={"job_id": job["job_id"]})
                        if r.ok:
                            st.success("Approved and enqueued")
                            st.rerun()
                        else:
                            st.error("Approve failed: " + r.text)
                    except Exception as e:
                        st.error(f"Action error: {e}")
                
                if col2.button(f"Reject {job['job_id']}", key=f"reject-{job['job_id']}"):
                    try:
                        r = requests.post(f"{API_BASE}/api/admin/reject", json={"job_id": job["job_id"]})
                        if r.ok:
                            st.success("Rejected")
                            st.rerun()
                        else:
                            st.error("Reject failed: " + r.text)
                    except Exception as e:
                        st.error(f"Action error: {e}")

if __name__ == "__main__":
    render_admin_dashboard()
