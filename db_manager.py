import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "project_status.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(force_reset=False):
    """Initializes the SQLite database tables and pre-populates with mock data."""
    if force_reset and os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = get_connection()
    cursor = conn.cursor()

    # Create Projects Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        health TEXT NOT NULL,
        engineers_count INTEGER DEFAULT 0,
        phase TEXT NOT NULL
    )
    """)

    # Create Issues (Tasks) Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS issues (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        name TEXT NOT NULL,
        assignee TEXT,
        status TEXT NOT NULL,
        priority TEXT NOT NULL,
        cycle TEXT,
        description TEXT,
        blocker_details TEXT,
        updated_at TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id)
    )
    """)

    # Create Team Members Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS team_members (
        name TEXT PRIMARY KEY,
        role TEXT,
        email TEXT
    )
    """)

    # Create Weekly Reports Table (ChromaDB stores vectors, SQLite stores raw archive)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS weekly_reports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        report_date TEXT NOT NULL,
        report_markdown TEXT NOT NULL
    )
    """)

    conn.commit()

    # Prepopulate tables if empty
    cursor.execute("SELECT COUNT(*) as count FROM projects")
    if cursor.fetchone()["count"] == 0:
        # Projects Data
        projects = [
            ("data-pipeline-upgrade", "Data Pipeline Upgrade", "Active", "On-Track", 4, "Coding"),
            ("mobile-app-redesign", "Mobile App Redesign", "Active", "Blocked", 6, "Design"),
            ("security-audit-patch", "Security Audit Patch", "Active", "Delayed", 3, "UT/IT"),
            ("legacy-system-migration", "Legacy System Migration", "Active", "On-Track", 5, "Requirements")
        ]
        cursor.executemany("INSERT INTO projects VALUES (?, ?, ?, ?, ?, ?)", projects)

        # Team Members Data
        team = [
            ("Alice Johnson", "Backend Tech Lead", "alice@company.com"),
            ("Bob Smith", "Data Engineer", "bob@company.com"),
            ("Charlie Brown", "UI Designer", "charlie@company.com"),
            ("Diana Prince", "Frontend Dev", "diana@company.com"),
            ("Evan Wright", "Security Analyst", "evan@company.com"),
            ("Fiona Gallagher", "QA Engineer", "fiona@company.com")
        ]
        cursor.executemany("INSERT INTO team_members VALUES (?, ?, ?)", team)

        # Issues (Tasks) Data
        issues = [
            ("PLANE-1", "data-pipeline-upgrade", "Migrate pipeline jobs to Spark cluster", "Bob Smith", "In Progress", "High", "Cycle 1", 
             "Rewrite the batch ETL pipelines to run on Spark cluster to handle larger datasets.", None, "2026-06-15 10:00:00"),
            
            ("PLANE-2", "data-pipeline-upgrade", "Configure Kafka schema registry", "Bob Smith", "Todo", "Medium", "Cycle 1", 
             "Register schemas for user activity event telemetry streams.", None, "2026-06-14 09:30:00"),
            
            ("PLANE-3", "data-pipeline-upgrade", "Optimize database indexing for batch reads", "Alice Johnson", "Done", "High", "Cycle 1", 
             "Added compound indexes to transactional logs table, reducing query times by 45%.", None, "2026-06-15 15:45:00"),
            
            ("PLANE-4", "mobile-app-redesign", "Implement Figma dark mode design system", "Charlie Brown", "Blocked", "Urgent", "Cycle 1", 
             "Convert Figma colors and layout parameters into CSS-in-JS design tokens.", 
             "Blocked because the final design tokens JSON file from design team has missing color palettes for secondary screens.", "2026-06-12 11:20:00"),
            
            ("PLANE-5", "mobile-app-redesign", "Write unit tests for authentication hooks", "Diana Prince", "Todo", "Medium", "Cycle 1", 
             "Establish unit tests using React Testing Library for custom auth hooks.", None, "2026-06-10 14:00:00"),
            
            ("PLANE-6", "security-audit-patch", "Fix SSL/TLS handshake latency vulnerabilities", "Evan Wright", "In Progress", "High", "Cycle 1", 
             "Investigate handshake failures and configure secure cipher suites.", None, "2026-06-15 16:30:00"),
            
            ("PLANE-7", "security-audit-patch", "Address CVE-2025-XXXX package vulnerabilities", "Evan Wright", "Delayed", "Urgent", "Cycle 1", 
             "Upgrade legacy crypto libraries to secure, audited versions.", 
             "Delayed because the major upgrade introduces breaking changes in the database encryption wrappers, requiring code refactoring.", "2026-06-15 17:00:00"),
            
            ("PLANE-8", "legacy-system-migration", "Extract requirements for legacy mainframes", "Alice Johnson", "In Progress", "High", "Cycle 1", 
             "Hold workshops with domain experts to map data schemas of mainframe DB2 tables.", None, "2026-06-15 08:30:00"),
             
            ("PLANE-9", "legacy-system-migration", "Draft target architecture blueprint", "Alice Johnson", "Todo", "Low", "Cycle 1", 
             "Create technical diagram showing data flow from mainframe to cloud cloud-native tables.", None, "2026-06-11 12:00:00"),
             
            ("PLANE-10", "mobile-app-redesign", "Draft API specifications for profile settings", "Diana Prince", "In Progress", "High", "Cycle 1", 
             "Map profile REST endpoints to match new mobile app interface requests.", None, "2026-06-15 11:15:00")
        ]
        cursor.executemany("INSERT INTO issues VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", issues)

        # Prepopulate a couple of historical weekly reports to give ChromaDB memory context week-over-week
        reports = [
            ("2026-06-01", """# Project Status Report - Week of Jun 1, 2026

## Executive Summary
All projects initialized. Data Pipeline Upgrade is setting up its baseline architecture. Mobile App Redesign completed mockups. 

## Project Health
- **Data Pipeline Upgrade**: Active (On Track)
- **Mobile App Redesign**: Active (On Track)
- **Security Audit Patch**: Active (On Track)
- **Legacy System Migration**: Active (On Track)

## Risks & Key Blockers
- None. Projects are in their requirements and design phases.
"""),
            ("2026-06-08", """# Project Status Report - Week of Jun 8, 2026

## Executive Summary
Development is underway. We have encountered minor friction on the Mobile App Redesign due to dependencies on the design files.

## Project Health
- **Data Pipeline Upgrade**: Active (On Track)
- **Mobile App Redesign**: Active (Delayed)
- **Security Audit Patch**: Active (On Track)
- **Legacy System Migration**: Active (On Track)

## Risks & Key Blockers
- **Mobile App Redesign**: Figma token exports are delayed. Charlie Brown is following up with the design team.
""")
        ]
        cursor.executemany("INSERT INTO weekly_reports (report_date, report_markdown) VALUES (?, ?)", reports)

        conn.commit()
    conn.close()

# Database Helper Operations
def get_projects():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM projects")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def get_issues(project_id=None):
    conn = get_connection()
    cursor = conn.cursor()
    if project_id:
        cursor.execute("SELECT * FROM issues WHERE project_id = ?", (project_id,))
    else:
        cursor.execute("SELECT * FROM issues")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def add_issue(issue):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO issues (id, project_id, name, assignee, status, priority, cycle, description, blocker_details, updated_at)
    VALUES (:id, :project_id, :name, :assignee, :status, :priority, :cycle, :description, :blocker_details, :updated_at)
    """, issue)
    conn.commit()
    conn.close()

def update_issue(issue_id, updates):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Construct dynamic query based on updates dictionary
    fields = []
    values = []
    for k, v in updates.items():
        fields.append(f"{k} = ?")
        values.append(v)
    
    values.append(issue_id)
    query = f"UPDATE issues SET {', '.join(fields)} WHERE id = ?"
    
    cursor.execute(query, values)
    conn.commit()
    conn.close()

def delete_issue(issue_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM issues WHERE id = ?", (issue_id,))
    conn.commit()
    conn.close()

def get_team_members():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM team_members")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

def save_weekly_report(date_str, markdown_text):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO weekly_reports (report_date, report_markdown) VALUES (?, ?)", (date_str, markdown_text))
    conn.commit()
    report_id = cursor.lastrowid
    conn.close()
    return report_id

def get_weekly_reports():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM weekly_reports ORDER BY id DESC")
    rows = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return rows

# Automatically run initialization on import
init_db()
