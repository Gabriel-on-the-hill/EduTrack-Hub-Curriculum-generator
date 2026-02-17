# app_additions/admin_pending_ui.py
import streamlit as st
import logging

# Direct service assignment (Monolithic mode)
# This avoids HTTP calls to localhost:8000 which requires a separate process
try:
    from src.ingestion.services import list_pending_jobs, approve_ingestion_job, reject_ingestion_job
except ImportError:
    st.error("Could not import ingestion services. Ensure you are running from the root directory.")
    list_pending_jobs = None

def render_admin_dashboard():
    st.title("Ingestion - Pending Manual Review")
    st.caption("Internal Governance Console")

    if not list_pending_jobs:
        st.stop()

    # Fetch pending jobs directly from DB
    try:
        jobs = list_pending_jobs()
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    if not jobs:
        st.info("No pending ingestion jobs.")
    else:
        for job in jobs:
            with st.expander(f"Job {job['job_id']} - {job['source_url']}"):
                st.write(f"**Requested by:** {job.get('requested_by')}")
                st.write(f"**Reason:** {job.get('decision_reason')}")
                st.write(f"**Created:** {job.get('created_at')}")
                
                col1, col2 = st.columns(2)
                
                # Preview logic (could be added here if we want to fetch the snippet from DB or re-fetch)
                # For now, simplistic.
                
                if col1.button(f"Approve", key=f"approve-{job['job_id']}"):
                    try:
                        ok = approve_ingestion_job(job['job_id'])
                        if ok:
                            st.success(f"Job {job['job_id']} Approved & Enqueued")
                            st.rerun()
                        else:
                            st.error("Approval failed (ID not found?)")
                    except Exception as e:
                        st.error(f"Error approving: {e}")
                
                if col2.button(f"Reject", key=f"reject-{job['job_id']}"):
                    try:
                        ok = reject_ingestion_job(job['job_id'])
                        if ok:
                            st.success(f"Job {job['job_id']} Rejected")
                            st.rerun()
                        else:
                            st.error("Rejection failed")
                    except Exception as e:
                        st.error(f"Error rejecting: {e}")

if __name__ == "__main__":
    render_admin_dashboard()
