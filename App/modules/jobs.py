import streamlit as st
import json
from pathlib import Path
from datetime import datetime
from utils.tasks import manager, check_job_status, JobStatus

_HERE = Path(__file__).parent
_APP_DIR = _HERE.parent
SUBMISSIONS_DIR = _APP_DIR / "jobs"


def _format_ts(ts_str):
    if not ts_str:
        return "—"
    try:
        dt = datetime.fromisoformat(ts_str)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ts_str


def _compute_duration(start_str, end_str):
    if not start_str or not end_str:
        return "—"
    try:
        start = datetime.fromisoformat(start_str)
        end = datetime.fromisoformat(end_str)
        total = int((end - start).total_seconds())
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return "—"


def _show_completed_job(job_id, db_info):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Status", "Success")

    with col2:
        st.metric("Completed", _format_ts(db_info["end_time"] if db_info else None))

    with col3:

        duration = _compute_duration(
            db_info["start_time"] if db_info else None,
            db_info["end_time"] if db_info else None,
        )
        st.metric("Duration", duration)

    result_file = SUBMISSIONS_DIR / job_id / "result.json"

    if not result_file.exists():
        st.warning(
            "Result data not available. "
            "The submission output may have been cleaned up."
        )
        return

    with open(result_file) as f:
        result = json.load(f)

    col1, col2 = st.columns(2)

    with col1:
        st.metric("Samples submitted", result["submitted"])

    with col2:
        st.metric("Errors", result["errors"])

    log_dir = Path(result["log_dir"])

    if not log_dir.exists():
        st.warning("Log directory not found.")
        return

    col_xml, col_zip = st.columns(2)

    submit_xml = log_dir / "submit.xml"
    if submit_xml.exists():
        with col_xml:
            st.download_button(
                label="Download submit.xml",
                data=submit_xml.read_bytes(),
                file_name="submit.xml",
                mime="text/xml",
                use_container_width=True,
                key=f"dl_{job_id}_submit.xml",
            )

    manifests_zip = log_dir / "manifests.zip"
    if manifests_zip.exists():
        with col_zip:
            st.download_button(
                label="Download manifests (ZIP)",
                data=manifests_zip.read_bytes(),
                file_name="manifests.zip",
                mime="application/zip",
                use_container_width=True,
                key=f"dl_{job_id}_manifests.zip",
            )

    log_files = [
        p for p in sorted(log_dir.glob("*"))
        if p.name not in {"result.json", "submit.xml", "manifests.zip"}
    ]

    if log_files:
        st.subheader("Submission logs")

        for logfile in log_files:
            suffix = logfile.suffix.lower()

            try:
                content = logfile.read_text(encoding="utf-8")
            except Exception:
                content = None

            with st.expander(logfile.name, expanded=True):
                if content:
                    lang = "xml" if suffix == ".xml" else "text"
                    st.code(content, language=lang)
                else:
                    st.warning("Could not read file content.")

                with open(logfile, "rb") as f:
                    st.download_button(
                        label=f"Download {logfile.name}",
                        data=f.read(),
                        file_name=logfile.name,
                        use_container_width=True,
                        key=f"dl_{job_id}_{logfile.name}",
                    )


def _show_job(job_id):
    status, _ = check_job_status(job_id)
    db_info = manager.get_result(job_id)

    # Neither Redis nor DB knows about this job
    if status == JobStatus.INVALID and db_info is None:
        st.error(f"Job `{job_id}` not found.")
        return

    # Prefer DB status for completed jobs (Redis results expire)
    db_status = db_info["status"] if db_info else None

    if db_status == "success" or status == JobStatus.FINISHED:
        _show_completed_job(job_id, db_info)

    elif db_status == "failure" or status == JobStatus.FAILED:
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Status", "Failed")
        with col2:
            st.metric("Started", _format_ts(db_info["start_time"] if db_info else None))
        with col3:
            st.metric("Ended", _format_ts(db_info["end_time"] if db_info else None))
        st.error(
            "The submission job failed. "
            "Please check your credentials and metadata and try again."
        )

        error_file = SUBMISSIONS_DIR / job_id / "error.txt"
        if error_file.exists():
            try:
                content = error_file.read_text(encoding="utf-8")
            except Exception:
                content = None
            with st.expander("error.txt", expanded=True):
                if content:
                    st.code(content, language="text")
                with open(error_file, "rb") as f:
                    st.download_button(
                        label="Download error.txt",
                        data=f.read(),
                        file_name="error.txt",
                        use_container_width=True,
                        key=f"dl_{job_id}_error.txt",
                    )

    else:
        pos = manager.get_job_position(job_id)
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Status", "Queued / Running")
        with col2:
            st.metric(
                "Queue position",
                str(pos) if pos is not None else "—",
            )
        st.info(
            "Your submission is being processed. "
            "Refresh this page to check for updates."
        )

def runUI():

    # st.subheader("Queue overview")

    # col1, col2 = st.columns(2)

    # with col1:
    #     st.markdown("**Pending & running**")
    #     pending_df = manager.get_pending_jobs()
    #     if pending_df.empty:
    #         st.info("No jobs currently in queue.")
    #     else:
    #         st.dataframe(
    #             pending_df,
    #             hide_index=True,
    #             use_container_width=True,
    #         )

    # with col2:
    #     st.markdown("**Recently completed**")
    #     completed_df = manager.get_recent_completed_jobs()
    #     if completed_df.empty:
    #         st.info("No completed jobs yet.")
    #     else:
    #         st.dataframe(
    #             completed_df,
    #             hide_index=True,
    #             use_container_width=True,
    #         )

    # st.divider()

    # st.subheader("Look up a submission")

    def _set_example():
        st.session_state["job_input"] = "c1e95e6e-cdf2-4746-87c0-248e717a5d62"

    with st.container(border=True):
        col1, col2 = st.columns([9, 1])

        with col2:
            st.button(
                "Example",
                use_container_width=True,
                on_click=_set_example,
            )

        with st.form("jobs_submit", border=False):
            job_id = st.text_input("Enter Job ID", key="job_input")
            submitted = st.form_submit_button(
                "Submit",
                use_container_width=True,
                type="primary",
            )

    if submitted and job_id:
        st.session_state["job_id"] = job_id.strip()

    if "job_id" in st.session_state:
        _show_job(st.session_state["job_id"])
