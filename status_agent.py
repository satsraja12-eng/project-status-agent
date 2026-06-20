import streamlit as st
import time
import pandas as pd
import plotly.express as px
import os
import uuid
from datetime import datetime

# Import database manager, plane client, and agent engine
import db_manager as db
from plane_client import PlaneClient
import agent_engine as engine

# Page configurations
st.set_page_config(
    page_title="Intelligent Project Status Agent",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Dark Theme Stylesheet
st.markdown("""
<style>
    /* Main app styles */
    .stApp {
        background-color: #0B0F19;
        color: #F3F4F6;
        font-family: 'Inter', sans-serif;
    }
    
    /* Header and Typography */
    h1, h2, h3, h4, h5, h6 {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    
    /* Custom Sidebar styling */
    div[data-testid="stSidebar"] {
        background-color: #0F172A !important;
        border-right: 1px solid rgba(255, 255, 255, 0.08) !important;
    }
    
    /* Styled Metric Cards */
    .metric-card {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
        padding: 1.25rem;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: rgba(99, 102, 241, 0.3);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.3);
    }
    .metric-label {
        font-size: 0.875rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        font-weight: 600;
    }
    .metric-value {
        font-size: 2.25rem;
        font-weight: 800;
        color: #FFFFFF;
        margin-top: 0.25rem;
    }
    
    /* Status Labels */
    .status-badge {
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        display: inline-block;
        text-align: center;
    }
    .status-active { background-color: rgba(16, 185, 129, 0.15); color: #10B981; border: 1px solid rgba(16, 185, 129, 0.3); }
    .status-blocked { background-color: rgba(239, 68, 68, 0.15); color: #EF4444; border: 1px solid rgba(239, 68, 68, 0.3); }
    .status-delayed { background-color: rgba(245, 158, 11, 0.15); color: #F59E0B; border: 1px solid rgba(245, 158, 11, 0.3); }
    .status-ontrack { background-color: rgba(59, 130, 246, 0.15); color: #3B82F6; border: 1px solid rgba(59, 130, 246, 0.3); }
    
    /* Form fields and inputs styling */
    div[data-baseweb="select"] > div {
        background-color: #1E293B !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    input, textarea {
        background-color: #1E293B !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
    }
    
    /* Streamlit Tab styling */
    button[data-baseweb="tab"] {
        color: #94A3B8 !important;
        font-weight: 600 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #6366F1 !important;
        border-bottom-color: #6366F1 !important;
    }
    
    /* Custom buttons styling */
    .stButton>button {
        background: linear-gradient(135deg, #4F46E5 0%, #3B82F6 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 0.5rem 1.25rem !important;
        font-weight: 600 !important;
        transition: all 0.2s ease !important;
    }
    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
    }
</style>
""", unsafe_allow_html=True)


# Initialize SQLite Database
db.init_db()

# Auto-Sync on load (runs if last sync was > 24 hours ago)
SYNC_FILE = os.path.join(os.path.dirname(__file__), "last_sync.txt")
should_auto_sync = False

if not os.path.exists(SYNC_FILE):
    should_auto_sync = True
else:
    try:
        with open(SYNC_FILE, "r") as f:
            last_sync = datetime.fromisoformat(f.read().strip())
        if (datetime.now() - last_sync).total_seconds() > 86400:
            should_auto_sync = True
    except Exception:
        should_auto_sync = True

if should_auto_sync:
    from sync_plane import run_sync
    # Run sync
    success = run_sync()
    if success:
        st.toast("🔄 Workspace auto-updated from Plane API!", icon="✅")

# Initialize state variables
if "active_tab" not in st.session_state:
    st.session_state.active_tab = "dashboard"
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "graph_thread_id" not in st.session_state:
    st.session_state.graph_thread_id = str(uuid.uuid4())
if "graph_config" not in st.session_state:
    st.session_state.graph_config = {"configurable": {"thread_id": st.session_state.graph_thread_id}}
if "draft_report_content" not in st.session_state:
    st.session_state.draft_report_content = ""
if "generation_step" not in st.session_state:
    st.session_state.generation_step = 1  # 1: Not started, 2: Draft generated, 3: Completed


# =====================================================================
# SIDEBAR CONTROLS & SETTINGS
# =====================================================================
st.sidebar.title("🤖 Project Status Agent")
st.sidebar.caption("Agentic PM Insights & Status Automation")

st.sidebar.subheader("⚙️ Configuration")
llm_provider = st.sidebar.selectbox("LLM Provider", ["nebius", "groq"], help="Select model provider. Nebius runs Llama-3.3-70B; Groq runs Llama-3.1-8B.")
st.sidebar.info(f"Using: **{llm_provider.capitalize()}**")

# Plane API Synchronization Section
st.sidebar.markdown("---")
st.sidebar.subheader("🔌 Plane.so Integration")
st.sidebar.write("Sync with a live Plane instance:")
workspace_slug = st.sidebar.text_input("Workspace Slug", value=os.getenv("PLANE_WORKSPACE_SLUG", "project-status-agent"))
project_slug = st.sidebar.text_input("Project Slug", value=os.getenv("PLANE_PROJECT_SLUG", "a93859b7-4b3f-45be-91a5-0c60fb3f2515"))

if st.sidebar.button("🔄 Sync with Plane API"):
    with st.spinner("Syncing issues from Plane API..."):
        client = PlaneClient()
        response = client.fetch_issues(workspace_slug, project_slug)
        
        if "success" in response:
            issues = response["issues"]
            if not issues:
                st.sidebar.warning("No issues found in Plane project.")
            else:
                # Sync into SQLite
                conn = db.get_connection()
                cursor = conn.cursor()
                # Clear existing issues for this project to prevent duplicates
                cursor.execute("DELETE FROM issues WHERE project_id = ?", (project_slug,))
                
                # Check if project exists in SQLite, if not create it
                cursor.execute("SELECT id FROM projects WHERE id = ?", (project_slug,))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?)", 
                                   (project_slug, project_slug.replace("-", " ").title(), "Active", 3, "Coding"))
                
                # Insert issues
                for issue in issues:
                    cursor.execute("""
                    INSERT OR REPLACE INTO issues (id, project_id, name, assignee, status, priority, cycle, description, blocker_details, updated_at)
                    VALUES (:id, :project_id, :name, :assignee, :status, :priority, :cycle, :description, :blocker_details, :updated_at)
                    """, issue)
                conn.commit()
                conn.close()
                st.sidebar.success(f"Synced {len(issues)} issues successfully!")
                st.rerun()
        else:
            st.sidebar.error(response.get("error", "Failed to sync."))
            
    # Add a dynamic link to the Plane project in the sidebar
    plane_url = f"https://app.plane.so/{workspace_slug}/projects/{project_slug}/issues/"
    st.sidebar.markdown(f"<div style='margin-top: 1rem;'><a href='{plane_url}' target='_blank' style='text-decoration: none; color: #6366F1; font-weight: bold; border: 1px solid rgba(99, 102, 241, 0.3); padding: 6px 12px; border-radius: 6px; background-color: rgba(99, 102, 241, 0.05); font-size: 0.8rem; display: block; text-align: center;'>🔗 Open Plane Workspace</a></div>", unsafe_allow_html=True)


# =====================================================================
# MAIN TABBED USER INTERFACE
# =====================================================================

tabs = st.tabs(["📊 Dashboard", "🗂️ Plane Issues Manager", "📝 Weekly Report Generator", "📚 Report Archives", "💬 AI Assistant Chat"])

# ---------------------------------------------------------------------
# TAB 1: EXECUTIVE DASHBOARD
# ---------------------------------------------------------------------
with tabs[0]:
    col_header, col_link = st.columns([3, 1])
    with col_header:
        st.title("📊 Workspace Overview")
    with col_link:
        plane_url = f"https://app.plane.so/{workspace_slug}/projects/{project_slug}/issues/"
        st.markdown(f"<div style='text-align: right; margin-top: 1.5rem;'><a href='{plane_url}' target='_blank' style='text-decoration: none; color: #6366F1; font-weight: bold; border: 1px solid rgba(99, 102, 241, 0.3); padding: 8px 16px; border-radius: 8px; background-color: rgba(99, 102, 241, 0.05);'>🔗 Open Active Workspace</a></div>", unsafe_allow_html=True)
    
    # Refresh SQLite data
    projects = db.get_projects()
    issues = db.get_issues()
    
    # 1. LANDING PAGE SUMMARY: Projects & Sprint Health with Timelines and Mitigation Plans
    st.subheader("Projects & Sprint Health Summary")
    st.write("Click on any project to expand its timeline, milestones, active engineers, and mitigation plans:")
    
    # Project Metadata for rendering rich UI timelines & details
    project_meta = {
        "data-pipeline-upgrade": {
            "color_indicator": "🟢",
            "eta": "June 30, 2026",
            "milestones": [
                "Milestone 1: Migrate batch ETL jobs to Spark cluster (Completed)",
                "Milestone 2: Configure Kafka schema registry (In Progress - Target: June 22, 2026)",
                "Milestone 3: Database Index optimization (Completed)"
            ],
            "timeline_stages": [
                ("Requirements", "completed"),
                ("Design", "completed"),
                ("Coding", "active"),
                ("UT/IT", "pending"),
                ("Deployment", "pending")
            ],
            "mitigation": None
        },
        "mobile-app-redesign": {
            "color_indicator": "🔴",
            "eta": "July 15, 2026 (At Risk)",
            "milestones": [
                "Milestone 1: FIGMA Dark Mode Token Export (Blocked)",
                "Milestone 2: Write unit tests for auth hooks (In Progress)",
                "Milestone 3: Profile settings API specifications (In Progress)"
            ],
            "timeline_stages": [
                ("Requirements", "completed"),
                ("Design", "blocked"),
                ("Coding", "pending"),
                ("UT/IT", "pending"),
                ("Deployment", "pending")
            ],
            "mitigation": "⚠️ **Mitigation Plan**: Coordinate immediately with the Design team to resolve missing Figma color palettes. In the meantime, reallocate resources from Design tasks to assist Diana with Profile API development to maintain schedule."
        },
        "security-audit-patch": {
            "color_indicator": "🟡",
            "eta": "June 28, 2026 (Delayed)",
            "milestones": [
                "Milestone 1: Resolve SSL/TLS handshakes (In Progress)",
                "Milestone 2: Upgrade crypto packages to resolve CVEs (Delayed due to breaking DB wrapper changes)"
            ],
            "timeline_stages": [
                ("Requirements", "completed"),
                ("Design", "completed"),
                ("Coding", "completed"),
                ("UT/IT", "delayed"),
                ("Deployment", "pending")
            ],
            "mitigation": "⚠️ **Mitigation Plan**: Setup a pair-programming session between Alice Johnson (DB lead) and Evan Wright to refactor legacy crypto libraries to run with the new database encryption wrapper."
        },
        "legacy-system-migration": {
            "color_indicator": "🟢",
            "eta": "August 30, 2026",
            "milestones": [
                "Milestone 1: DB2 mainframe table schemas requirements mapping (In Progress - Target: June 20, 2026)",
                "Milestone 2: Target architecture blueprint mapping (Todo)"
            ],
            "timeline_stages": [
                ("Requirements", "active"),
                ("Design", "pending"),
                ("Coding", "pending"),
                ("UT/IT", "pending"),
                ("Deployment", "pending")
            ],
            "mitigation": None
        }
    }

    def render_timeline(stages):
        html = "<div style='display:flex; justify-content:space-between; align-items:center; margin: 15px 0; background-color:#1E293B; padding:15px; border-radius:8px; border: 1px solid rgba(255,255,255,0.06);'>"
        for idx, (stage_name, stage_status) in enumerate(stages):
            if idx > 0:
                html += "<div style='flex:1; height:2px; background-color:rgba(255,255,255,0.15); margin:0 10px;'></div>"
            
            if stage_status == "completed":
                html += f"<div style='text-align:center;'><div style='width:24px; height:24px; border-radius:50%; background-color:#10B981; color:white; display:flex; align-items:center; justify-content:center; margin:0 auto; font-size:0.75rem; font-weight:bold;'>✓</div><span style='font-size:0.75rem; color:#94A3B8; display:block; margin-top:4px;'>{stage_name}</span></div>"
            elif stage_status == "active":
                html += f"<div style='text-align:center;'><div style='width:24px; height:24px; border-radius:50%; background-color:#6366F1; color:white; display:flex; align-items:center; justify-content:center; margin:0 auto; font-size:0.75rem; font-weight:bold;'>⚡</div><span style='font-size:0.75rem; color:#FFFFFF; display:block; margin-top:4px; font-weight:bold;'>{stage_name}</span></div>"
            elif stage_status == "blocked":
                html += f"<div style='text-align:center;'><div style='width:24px; height:24px; border-radius:50%; background-color:#EF4444; color:white; display:flex; align-items:center; justify-content:center; margin:0 auto; font-size:0.75rem; font-weight:bold;'>✗</div><span style='font-size:0.75rem; color:#EF4444; display:block; margin-top:4px; font-weight:bold;'>{stage_name}</span></div>"
            elif stage_status == "delayed":
                html += f"<div style='text-align:center;'><div style='width:24px; height:24px; border-radius:50%; background-color:#F59E0B; color:white; display:flex; align-items:center; justify-content:center; margin:0 auto; font-size:0.75rem; font-weight:bold;'>!</div><span style='font-size:0.75rem; color:#F59E0B; display:block; margin-top:4px; font-weight:bold;'>{stage_name}</span></div>"
            else: # pending
                html += f"<div style='text-align:center;'><div style='width:24px; height:24px; border-radius:50%; background-color:#475569; color:white; display:flex; align-items:center; justify-content:center; margin:0 auto; font-size:0.75rem; font-weight:bold;'>•</div><span style='font-size:0.75rem; color:#64748B; display:block; margin-top:4px;'>{stage_name}</span></div>"
                
        html += "</div>"
        return html

    for proj in projects:
        meta = project_meta.get(proj["id"], {
            "color_indicator": "🟢",
            "eta": "TBD",
            "milestones": ["Requirements Phase (In Progress)"],
            "timeline_stages": [("Requirements", "active"), ("Design", "pending"), ("Coding", "pending"), ("UT/IT", "pending"), ("Deployment", "pending")],
            "mitigation": None
        })
        
        # Expander Header with Status Indicator Circle
        expander_label = f"{meta['color_indicator']} {proj['name']} (Phase: {proj['phase']} | Status: {proj['status']} | Health: {proj['health']})"
        
        with st.expander(expander_label):
            # Render visual timeline
            st.markdown(render_timeline(meta["timeline_stages"]), unsafe_allow_html=True)
            
            # Details columns
            col_det1, col_det2 = st.columns(2)
            
            # Get engineers and issues for this project
            proj_issues = [i for i in issues if i["project_id"] == proj["id"]]
            engineers = list(set([i["assignee"] for i in proj_issues if i["assignee"]]))
            
            # Pre-load role mappings
            team_members_list = db.get_team_members()
            team_roles = {t['name']: t['role'] for t in team_members_list}
            
            # Calculate global workloads for active tasks (not Done) to get actual bandwidth %
            active_issues_all = [i for i in issues if i['status'] != 'Done']
            global_workload = {}
            for i in active_issues_all:
                if i['assignee']:
                    global_workload[i['assignee']] = global_workload.get(i['assignee'], 0) + 1

            with col_det1:
                st.markdown(f"**📅 Estimated Completion (ETA):** {meta['eta']}")
                st.markdown("**⛳ Project Milestones:**")
                for mil in meta["milestones"]:
                    st.write(f"- {mil}")
                    
            with col_det2:
                st.markdown("**👥 Assigned Engineers & Workload Bandwidth:**")
                if engineers:
                    for eng in engineers:
                        role = team_roles.get(eng, "Software Engineer")
                        active_count = global_workload.get(eng, 0)
                        # Assume each active issue represents 35% bandwidth allocation
                        allocation_pct = min(active_count * 35, 100)
                        
                        st.write(f"🧑‍💻 **{eng}** ({role})")
                        st.progress(allocation_pct / 100.0)
                        st.caption(f"Allocation: {allocation_pct}% ({active_count} active tasks in workspace)")
                else:
                    st.write("No engineers assigned yet.")
            
            # Render Mitigation Plan if Blocked / Delayed
            if meta["mitigation"]:
                st.info(meta["mitigation"])

            # Render list of Project Issues & Statuses
            st.markdown("**📋 Current Project Issues Status:**")
            if proj_issues:
                df_proj_issues = pd.DataFrame(proj_issues)
                st.dataframe(
                    df_proj_issues[["id", "name", "assignee", "status", "priority", "cycle"]],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.write("No issues currently mapped to this project.")
                
            # Add direct link to the Plane Board for this specific project
            proj_plane_url = f"https://app.plane.so/{workspace_slug}/projects/{proj['id']}/issues/"
            st.markdown(f"<p style='margin-top: 15px;'><a href='{proj_plane_url}' target='_blank' style='text-decoration: none; color: #6366F1; font-weight: bold; border: 1px solid rgba(99, 102, 241, 0.3); padding: 6px 12px; border-radius: 6px; background-color: rgba(99, 102, 241, 0.05); font-size: 0.85rem;'>🔗 Open '{proj['name']}' in Plane</a></p>", unsafe_allow_html=True)
            
    st.markdown("<br><hr style='border: 1px solid rgba(255,255,255,0.06);'><br>", unsafe_allow_html=True)

    # 2. DETAILED METRICS & CHARTS PER-PROJECT
    st.subheader("🔍 Project Detailed Analytics")
    project_names = ["All Projects"] + [p["name"] for p in projects]
    selected_proj_name = st.selectbox("Select Project for Detailed Chart Analysis", project_names)
    
    # Filter issues and metrics based on selection
    if selected_proj_name == "All Projects":
        filtered_issues = issues
        st.markdown("Showing analytics for **all active projects** in the workspace.")
    else:
        # Find project id
        proj_id = [p["id"] for p in projects if p["name"] == selected_proj_name][0]
        filtered_issues = [i for i in issues if i["project_id"] == proj_id]
        st.markdown(f"Showing analytics for project: **{selected_proj_name}**")
        
    # Calculate Metrics
    total_issues = len(filtered_issues)
    blocked_issues = len([i for i in filtered_issues if i['status'] == "Blocked"])
    delayed_issues = len([i for i in filtered_issues if i['status'] == "Delayed"])
    done_issues = len([i for i in filtered_issues if i['status'] == "Done"])
    
    # Render Metrics Cards for the filtered data
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Issues</div>
            <div class="metric-value">{total_issues}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #10B981;">Completed Issues</div>
            <div class="metric-value" style="color: #10B981;">{done_issues}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #EF4444;">Blocked Issues</div>
            <div class="metric-value" style="color: #EF4444;">{blocked_issues}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label" style="color: #F59E0B;">Delayed Issues</div>
            <div class="metric-value" style="color: #F59E0B;">{delayed_issues}</div>
        </div>
        """, unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Charts Row for the filtered data
    chart_col1, chart_col2 = st.columns(2)
    df_issues = pd.DataFrame(filtered_issues)
    
    with chart_col1:
        st.write("#### Issue Status Distribution")
        if not df_issues.empty:
            fig_pie = px.pie(
                df_issues, 
                names="status", 
                color="status",
                color_discrete_map={
                    "Todo": "#64748B",
                    "In Progress": "#6366F1",
                    "Blocked": "#EF4444",
                    "Delayed": "#F59E0B",
                    "Done": "#10B981"
                },
                hole=0.4
            )
            fig_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#F3F4F6",
                showlegend=True,
                margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("No task data found for this selection.")
            
    with chart_col2:
        st.write("#### Team Workload Distribution")
        if not df_issues.empty:
            df_workload = df_issues.groupby(["assignee", "status"]).size().reset_index(name="count")
            fig_bar = px.bar(
                df_workload,
                x="assignee",
                y="count",
                color="status",
                color_discrete_map={
                    "Todo": "#64748B",
                    "In Progress": "#6366F1",
                    "Blocked": "#EF4444",
                    "Delayed": "#F59E0B",
                    "Done": "#10B981"
                },
                barmode="stack",
                labels={"assignee": "Engineer", "count": "Issues Assigned"}
            )
            fig_bar.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#F3F4F6",
                margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No task data found for this selection.")


# ---------------------------------------------------------------------
# TAB 2: PLANE ISSUES PLANNER
# ---------------------------------------------------------------------
with tabs[1]:
    st.title("🗂️ Plane Issues Planner")
    
    col_list, col_form = st.columns([2, 1])
    
    with col_list:
        st.subheader("Active Issue Backlog")
        issues_list = db.get_issues()
        if not issues_list:
            st.info("No active issues. Generate mock data or sync with Plane.")
        else:
            df_issues_display = pd.DataFrame(issues_list)
            
            # Simple details edit trigger
            selected_issue_id = st.selectbox("Select Issue to Edit/Delete", df_issues_display["id"].tolist())
            
            # Show Table
            st.dataframe(
                df_issues_display[["id", "project_id", "name", "assignee", "status", "priority", "cycle"]],
                use_container_width=True,
                hide_index=True
            )
            
            # Selected Issue Details
            curr_issue = [i for i in issues_list if i["id"] == selected_issue_id][0]
            st.markdown(f"#### Selected Issue: `{curr_issue['id']}`")
            st.write(f"**Name:** {curr_issue['name']}")
            st.write(f"**Description:** {curr_issue['description']}")
            if curr_issue["blocker_details"]:
                st.warning(f"**Blocker Details:** {curr_issue['blocker_details']}")
                
            if st.button("🗑️ Delete Selected Issue", key="delete_issue_btn"):
                db.delete_issue(selected_issue_id)
                st.success("Deleted issue successfully!")
                st.rerun()

    with col_form:
        st.subheader("Manage Issues")
        
        action = st.radio("Action", ["Add New Issue", "Update Selected Issue"])
        
        projects_list = db.get_projects()
        project_ids = [p["id"] for p in projects_list]
        team_members_list = db.get_team_members()
        team_names = [t["name"] for t in team_members_list]
        
        statuses = ["Todo", "In Progress", "Blocked", "Delayed", "Done"]
        priorities = ["Low", "Medium", "High", "Urgent"]
        
        if action == "Add New Issue":
            with st.form("add_issue_form"):
                new_id = st.text_input("Issue ID (e.g. PLANE-11)", value=f"PLANE-{len(issues_list)+1}")
                new_project = st.selectbox("Project", project_ids)
                new_name = st.text_input("Title")
                new_assignee = st.selectbox("Assignee", team_names)
                new_status = st.selectbox("Status", statuses)
                new_priority = st.selectbox("Priority", priorities)
                new_cycle = st.text_input("Cycle (Sprint)", value="Cycle 1")
                new_desc = st.text_area("Description")
                new_blocker = st.text_area("Blocker/Delay Details (if status is Blocked or Delayed)")
                
                submitted = st.form_submit_button("Add Issue")
                if submitted:
                    if not new_name:
                        st.error("Title is required!")
                    else:
                        db.add_issue({
                            "id": new_id,
                            "project_id": new_project,
                            "name": new_name,
                            "assignee": new_assignee,
                            "status": new_status,
                            "priority": new_priority,
                            "cycle": new_cycle,
                            "description": new_desc,
                            "blocker_details": new_blocker if new_status in ["Blocked", "Delayed"] else None,
                            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        st.success("Added issue successfully!")
                        st.rerun()
        
        elif action == "Update Selected Issue":
            curr_issue = [i for i in issues_list if i["id"] == selected_issue_id][0]
            with st.form("update_issue_form"):
                st.write(f"Updating: `{curr_issue['id']}`")
                up_project = st.selectbox("Project", project_ids, index=project_ids.index(curr_issue["project_id"]) if curr_issue["project_id"] in project_ids else 0)
                up_name = st.text_input("Title", value=curr_issue["name"])
                up_assignee = st.selectbox("Assignee", team_names, index=team_names.index(curr_issue["assignee"]) if curr_issue["assignee"] in team_names else 0)
                up_status = st.selectbox("Status", statuses, index=statuses.index(curr_issue["status"]))
                up_priority = st.selectbox("Priority", priorities, index=priorities.index(curr_issue["priority"].capitalize()) if curr_issue["priority"].capitalize() in priorities else 1)
                up_cycle = st.text_input("Cycle (Sprint)", value=curr_issue["cycle"])
                up_desc = st.text_area("Description", value=curr_issue["description"])
                up_blocker = st.text_area("Blocker/Delay Details", value=curr_issue["blocker_details"] or "")
                
                submitted = st.form_submit_button("Save Changes")
                if submitted:
                    db.update_issue(selected_issue_id, {
                        "project_id": up_project,
                        "name": up_name,
                        "assignee": up_assignee,
                        "status": up_status,
                        "priority": up_priority,
                        "cycle": up_cycle,
                        "description": up_desc,
                        "blocker_details": up_blocker if up_status in ["Blocked", "Delayed"] else None,
                        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    })
                    st.success("Updated issue successfully!")
                    st.rerun()


# ---------------------------------------------------------------------
# TAB 3: WEEKLY REPORT GENERATOR (HITL)
# ---------------------------------------------------------------------
with tabs[2]:
    st.title("📝 Weekly Report Generator")
    st.write("Generate weekly project status summaries with Human-in-the-Loop approval breakpoints.")
    
    col_steps, col_view = st.columns([1, 2])
    
    with col_steps:
        st.subheader("Process Controls")
        
        # Project Selector
        projects_list = db.get_projects()
        if not projects_list:
            st.warning("No projects found in database. Seed mock data first!")
            selected_project_id = ""
        else:
            project_names = [p["name"] for p in projects_list]
            selected_project_name = st.selectbox("Select Project to Monitor", project_names)
            selected_project_id = [p["id"] for p in projects_list if p["name"] == selected_project_name][0]

        # Report Date Input
        report_date = st.date_input("Report Reference Date", value=datetime.today())
        date_str = report_date.strftime("%Y-%m-%d")
        
        # Workflow execution buttons
        if st.button("🚀 Draft Weekly Report", help="Launches the LangGraph workflow to retrieve context and draft the report."):
            if not selected_project_id:
                st.error("Please select a project to proceed.")
            else:
                with st.spinner("LangGraph running (retrieving context & drafting)..."):
                    # Reset thread state
                    st.session_state.graph_thread_id = str(uuid.uuid4())
                    st.session_state.graph_config = {"configurable": {"thread_id": st.session_state.graph_thread_id}}
                    
                    # Start report generation state
                    initial_state = {
                        "messages": [],
                        "current_report_draft": "",
                        "approved": False,
                        "tasks_context": "",
                        "historical_context": "",
                        "report_date": date_str,
                        "feedback": "",
                        "project_id": selected_project_id
                    }
                
                # Run the graph until the human review breakpoint
                events = engine.report_graph.stream(initial_state, st.session_state.graph_config)
                for event in events:
                    # Let it run until it halts before human_review node
                    pass
                
                # Retrieve draft content from state
                graph_state = engine.report_graph.get_state(st.session_state.graph_config)
                st.session_state.draft_report_content = graph_state.values.get("current_report_draft", "")
                st.session_state.generation_step = 2
                st.success("Draft Report generated. Ready for Human-in-the-Loop review.")
                st.rerun()

        # Step 2 controls (Edit & Feedback)
        if st.session_state.generation_step >= 2:
            st.markdown("---")
            st.subheader("Human Intervention")
            
            # Feed back mechanism to edit draft
            refine_feedback = st.text_input("Suggest changes to the draft (e.g. 'Emphasize Spark migration status')", key="refine_feedback_input")
            
            if st.button("🔄 Regenerate with Feedback"):
                with st.spinner("Regenerating draft with feedback..."):
                    # Update state in graph checkpoint with feedback and set approved to False
                    engine.report_graph.update_state(
                        st.session_state.graph_config,
                        {"feedback": refine_feedback, "approved": False},
                        as_node="human_review"
                    )
                    # Resume execution
                    events = engine.report_graph.stream(None, st.session_state.graph_config)
                    for event in events:
                        pass
                    
                    # Fetch new state
                    graph_state = engine.report_graph.get_state(st.session_state.graph_config)
                    st.session_state.draft_report_content = graph_state.values.get("current_report_draft", "")
                    st.success("Draft updated with feedback!")
                    st.rerun()
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Finalize approval button
            if st.button("✅ Approve & Save Report"):
                with st.spinner("Finalizing report..."):
                    # Update state with UI edits and set approved to True
                    engine.report_graph.update_state(
                        st.session_state.graph_config,
                        {
                            "current_report_draft": st.session_state.draft_report_content,
                            "approved": True
                        },
                        as_node="human_review"
                    )
                    # Resume execution to run the save node
                    events = engine.report_graph.stream(None, st.session_state.graph_config)
                    for event in events:
                        pass
                        
                    st.session_state.generation_step = 3
                    st.success("Report finalized, archived in database, and saved in vector memory!")
                    st.rerun()
                    
        # Reset Workflow
        if st.session_state.generation_step > 1:
            if st.button("Reset Workflow", type="secondary"):
                st.session_state.generation_step = 1
                st.session_state.draft_report_content = ""
                st.rerun()
                
    with col_view:
        st.subheader("Status Report Editor")
        if st.session_state.generation_step == 1:
            st.info("Click 'Draft Weekly Report' to start the agentic drafting workflow.")
        else:
            # Render Markdown Report Editor
            st.session_state.draft_report_content = st.text_area(
                "Edit Markdown Draft Below:", 
                value=st.session_state.draft_report_content, 
                height=500
            )
            
            # Side-by-side preview
            with st.expander("👁️ Preview Report Render"):
                st.markdown(st.session_state.draft_report_content)


# ---------------------------------------------------------------------
# TAB 4: REPORT ARCHIVE
# ---------------------------------------------------------------------
with tabs[3]:
    st.title("📚 Weekly Status Reports Archives")
    st.write("Browse and download finalized reports saved to database memory.")
    
    reports_list = db.get_weekly_reports()
    if not reports_list:
        st.info("No saved status reports found.")
    else:
        report_dates = [r["report_date"] for r in reports_list]
        selected_date = st.selectbox("Select Report Date", report_dates)
        
        selected_report = [r for r in reports_list if r["report_date"] == selected_date][0]
        
        st.markdown(f"### Report Date: `{selected_report['report_date']}`")
        
        st.markdown("---")
        st.markdown(selected_report["report_markdown"])
        st.markdown("---")
        
        # Download button
        st.download_button(
            label="Download Markdown Report",
            data=selected_report["report_markdown"],
            file_name=f"weekly_report_{selected_report['report_date']}.md",
            mime="text/markdown"
        )


# ---------------------------------------------------------------------
# TAB 5: AI CHATBOT WORKSPACE
# ---------------------------------------------------------------------
with tabs[4]:
    st.title("💬 Intelligent Project Status Assistant")
    st.write("Ask questions about active tasks, workload distribution, blockers, or historical report trends.")
    
    # Split into 2 columns: Left for Chat, Right for Operational Rules & Guidelines
    col_chat, col_rules = st.columns([5, 3])
    
    with col_chat:
        st.subheader("Chat Assistant")
        
        # Display Chat Messages
        for msg in st.session_state.chat_history:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        # Chat Input
        if prompt := st.chat_input("Ask about project health (e.g. 'Summarize what was blocked in our last cycle?')"):
            # Append User message
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            # Run agent query
            with st.chat_message("assistant"):
                with st.spinner("Agent thinking & executing tools..."):
                    response_text = engine.query_chatbot(
                        prompt, 
                        st.session_state.chat_history[:-1], 
                        provider=llm_provider
                      )
                    st.markdown(response_text)
                    
            # Append Agent message
            st.session_state.chat_history.append({"role": "assistant", "content": response_text})
            st.rerun()
            
        # Clear Chat History Button
        if st.session_state.chat_history:
            if st.button("🗑️ Clear Conversation History"):
                st.session_state.chat_history = []
                st.rerun()
                
    with col_rules:
        st.subheader("📌 Operational Rules & Guidelines")
        st.write("Train the agent by adding team guidelines, vacation calendars, or reporting preferences.")
        
        # 1. Fetch active rules/guidelines first
        memories = []
        sync_status = "Offline"
        if engine.mem0_client is not None:
            sync_status = "Connected"
            try:
                mems_resp = engine.mem0_client.get_all(filters={"user_id": "project_status_agent_user"})
                memories = mems_resp.get("results", []) if isinstance(mems_resp, dict) else []
            except Exception as e:
                st.error(f"Failed to load guidelines: {e}")
        
        # 2. Render summary table
        summary_data = {
            "Metric": ["Active Rules Count", "Memory Engine", "Sync Status"],
            "Value": [str(len(memories)), "Mem0 Cloud", sync_status]
        }
        st.table(pd.DataFrame(summary_data))
        
        # 3. Dropdown list to explore/manage rules
        if memories:
            st.markdown("**🔍 Explore & Manage Active Rules:**")
            rule_options = [f"Rule #{idx+1}: {m.get('memory', '')[:45]}..." for idx, m in enumerate(memories)]
            selected_rule_label = st.selectbox("Select a rule to view details or remove", rule_options)
            
            # Find the selected memory item
            selected_idx = rule_options.index(selected_rule_label)
            selected_item = memories[selected_idx]
            
            # Display full text in a callout card
            st.info(selected_item.get("memory", ""))
            
            # Delete button
            if st.button("🗑️ Remove Selected Rule", key="del_rule_selected", use_container_width=True):
                with st.spinner("Removing rule..."):
                    try:
                        engine.mem0_client.delete(memory_id=selected_item.get("id"))
                        st.success("Rule removed successfully!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        else:
            st.info("No active rules saved. You can add one below or tell the chatbot directly: 'Remember that...'")
            
        # 4. Form to add new rules below
        st.write("---")
        st.markdown("**➕ Add Operational Rule**")
        new_fact = st.text_area("Add New Rule / Guideline", placeholder="e.g. QA freezes releases on Friday afternoons. Bob is out June 20-27.", key="new_fact_text", height=100)
        if st.button("➕ Save Rule", use_container_width=True):
            if new_fact.strip():
                with st.spinner("Saving guideline..."):
                    try:
                        engine.mem0_client.add(
                            new_fact.strip(),
                            user_id="project_status_agent_user",
                            metadata={"source": "chat_panel"}
                        )
                        st.success("Guideline saved! (Takes a few seconds to index)")
                        time.sleep(1.5)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving: {e}")
            else:
                st.error("Please enter a guideline.")
