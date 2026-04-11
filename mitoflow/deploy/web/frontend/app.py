"""MitoFlow Web Frontend - Streamlit."""

from __future__ import annotations
import os
import time
from pathlib import Path

import requests
import streamlit as st

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8000")
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

st.set_page_config(
    page_title="MitoFlow Web",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
    }
    .info-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
</style>
""", unsafe_allow_html=True)


def check_api_health():
    """Check if API is available."""
    try:
        response = requests.get(f"{API_URL}/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False


def upload_file(file, name, threads, skip_trna, skip_rrna, skip_qc):
    """Upload file and create annotation task."""
    files = {"file": file}
    data = {
        "name": name,
        "threads": threads,
        "skip_trna": skip_trna,
        "skip_rrna": skip_rrna,
        "skip_qc": skip_qc,
    }
    
    response = requests.post(
        f"{API_URL}/api/annotate",
        files=files,
        data=data,
        timeout=30,
    )
    return response


def get_task_status(task_id):
    """Get task status."""
    response = requests.get(f"{API_URL}/api/tasks/{task_id}", timeout=10)
    return response


def download_results(task_id):
    """Download results."""
    response = requests.get(
        f"{API_URL}/api/results/{task_id}/download",
        timeout=60,
        stream=True,
    )
    return response


# Sidebar
with st.sidebar:
    st.image("https://img.shields.io/badge/MitoFlow-Web-blue", width=200)
    st.markdown("---")
    
    st.header("About")
    st.info(
        "MitoFlow is a modern plant mitochondrial genome "
        "annotation and analysis platform."
    )
    
    st.markdown("---")
    st.header("Resources")
    st.markdown("- [Documentation](https://github.com/mitoflow/mitoflow)")
    st.markdown("- [GitHub](https://github.com/mitoflow/mitoflow)")
    st.markdown("- [Report Issues](https://github.com/mitoflow/mitoflow/issues)")


# Main content
st.markdown('<p class="main-header">🧬 MitoFlow Web</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Plant Mitochondrial Genome Annotation Platform</p>',
    unsafe_allow_html=True
)

# Check API health
if not check_api_health():
    st.error("⚠️ API server is not available. Please try again later.")
    st.stop()

st.success("✅ API server is ready")

# Tabs
tab1, tab2, tab3 = st.tabs(["🚀 New Analysis", "📊 Task Status", "ℹ️ Help"])

with tab1:
    st.header("Submit New Annotation Job")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # File upload
        uploaded_file = st.file_uploader(
            "Upload mitochondrial genome FASTA",
            type=["fasta", "fa", "fas", "fna"],
            help="Maximum file size: 100MB",
        )
        
        if uploaded_file:
            file_size = len(uploaded_file.getvalue())
            st.info(f"File size: {file_size / 1024 / 1024:.2f} MB")
            
            if file_size > MAX_FILE_SIZE:
                st.error("File too large! Maximum size is 100MB.")
                st.stop()
    
    with col2:
        # Parameters
        st.subheader("Parameters")
        
        sample_name = st.text_input(
            "Sample Name",
            value="MyMito",
            help="Name for this analysis",
        )
        
        threads = st.slider(
            "CPU Threads",
            min_value=1,
            max_value=8,
            value=4,
            help="Number of parallel threads",
        )
        
        skip_trna = st.checkbox("Skip tRNA annotation", value=False)
        skip_rrna = st.checkbox("Skip rRNA annotation", value=False)
        skip_qc = st.checkbox("Skip QC checks", value=False)
    
    # Submit button
    if uploaded_file is not None:
        if st.button("🚀 Start Annotation", type="primary", use_container_width=True):
            with st.spinner("Uploading and starting analysis..."):
                try:
                    response = upload_file(
                        uploaded_file,
                        sample_name,
                        threads,
                        skip_trna,
                        skip_rrna,
                        skip_qc,
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        task_id = result["task_id"]
                        
                        st.session_state["current_task_id"] = task_id
                        st.success(f"Task created successfully! ID: {task_id[:8]}...")
                        st.info("Go to 'Task Status' tab to monitor progress.")
                    else:
                        st.error(f"Error: {response.text}")
                        
                except Exception as e:
                    st.error(f"Failed to submit task: {str(e)}")

with tab2:
    st.header("Check Task Status")
    
    # Task ID input
    task_id = st.text_input(
        "Task ID",
        value=st.session_state.get("current_task_id", ""),
        help="Enter your task ID to check status",
    )
    
    if task_id:
        if st.button("🔍 Check Status", use_container_width=True):
            try:
                response = get_task_status(task_id)
                
                if response.status_code == 200:
                    task = response.json()
                    
                    # Status display
                    status = task["status"]
                    progress = task["progress"]
                    message = task["message"]
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Status", status.upper())
                    
                    with col2:
                        st.metric("Progress", f"{progress}%")
                    
                    with col3:
                        if status == "completed":
                            st.metric("Result", "Ready ✅")
                        elif status == "failed":
                            st.metric("Result", "Failed ❌")
                        else:
                            st.metric("Result", "Pending ⏳")
                    
                    # Progress bar
                    st.progress(progress / 100)
                    st.info(message)
                    
                    # Download button
                    if status == "completed":
                        st.success("🎉 Annotation completed!")
                        
                        if st.button("📥 Download Results", type="primary"):
                            with st.spinner("Downloading..."):
                                try:
                                    download_resp = download_results(task_id)
                                    
                                    if download_resp.status_code == 200:
                                        st.download_button(
                                            label="Save ZIP File",
                                            data=download_resp.content,
                                            file_name=f"mitoflow_results_{task_id[:8]}.zip",
                                            mime="application/zip",
                                        )
                                    else:
                                        st.error("Failed to download results")
                                except Exception as e:
                                    st.error(f"Download error: {str(e)}")
                    
                    elif status == "failed":
                        st.error("Task failed. Please check the error message above.")
                    
                    else:
                        # Auto-refresh for running tasks
                        st.info("Task is running... Refresh this page to update status.")
                        
                else:
                    st.error("Task not found")
                    
            except Exception as e:
                st.error(f"Error checking status: {str(e)}")

with tab3:
    st.header("Help & Documentation")
    
    st.subheader("Input Requirements")
    st.markdown("""
    - **File format**: FASTA format (.fasta, .fa, .fas, .fna)
    - **Max size**: 100 MB
    - **Content**: Plant mitochondrial genome sequence
    - **Contigs**: Single or multiple contigs accepted
    """)
    
    st.subheader("Annotation Pipeline")
    st.markdown("""
    The annotation pipeline includes:
    1. **Protein-coding genes** - HMM search against 46 mitochondrial gene profiles
    2. **tRNA genes** - tRNAscan-SE + ARAGORN dual prediction
    3. **rRNA genes** - Barrnap prediction
    4. **Boundary correction** - Start/stop codon optimization
    5. **QC checks** - Five-dimensional quality assessment (optional)
    """)
    
    st.subheader("Output Files")
    st.markdown("""
    Results ZIP contains:
    - `gff/` - GFF3 annotation files
    - `genbank/` - GenBank format files
    - `fasta/` - Extracted sequences (CDS, protein, tRNA, rRNA)
    - `report/` - QC reports and statistics
    """)
    
    st.subheader("Estimated Runtime")
    st.markdown("""
    | Genome Size | Runtime |
    |-------------|---------|
    | < 500 kb | 2-5 min |
    | 500 kb - 1 Mb | 5-15 min |
    | 1-5 Mb | 15-45 min |
    | > 5 Mb | 1-2 hours |
    """)

# Footer
st.markdown("---")
st.caption("MitoFlow Web v0.1.0 | © 2024 MitoFlow Team")
