import os
import logging
from dotenv import load_dotenv

# Add parent directory to path to ensure correct imports
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import db_manager as db
from plane_client import PlaneClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def run_sync():
    load_dotenv()
    
    workspace = os.getenv("PLANE_WORKSPACE_SLUG", "project-status-agent")
    project = os.getenv("PLANE_PROJECT_SLUG", "a93859b7-4b3f-45be-91a5-0c60fb3f2515")
    api_key = os.getenv("PLANE_API_KEY")
    
    if not api_key:
        logger.error("Sync aborted: PLANE_API_KEY is not defined in the environment.")
        return False
        
    logger.info(f"Starting automatic sync for workspace: '{workspace}', project: '{project}'...")
    
    client = PlaneClient(api_key=api_key)
    response = client.fetch_issues(workspace, project)
    
    if "success" in response:
        issues = response["issues"]
        logger.info(f"Successfully fetched {len(issues)} issues from Plane API.")
        
        # Save to SQLite
        conn = db.get_connection()
        cursor = conn.cursor()
        
        # Clear existing issues for this project
        cursor.execute("DELETE FROM issues WHERE project_id = ?", (project,))
        
        # Ensure project header exists
        cursor.execute("SELECT id FROM projects WHERE id = ?", (project,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO projects VALUES (?, ?, ?, ?, ?)", 
                           (project, project.replace("-", " ").title(), "Active", 3, "Coding"))
        
        # Insert issues
        for issue in issues:
            cursor.execute("""
            INSERT OR REPLACE INTO issues (id, project_id, name, assignee, status, priority, cycle, description, blocker_details, updated_at)
            VALUES (:id, :project_id, :name, :assignee, :status, :priority, :cycle, :description, :blocker_details, :updated_at)
            """, issue)
            
        conn.commit()
        conn.close()
        
        # Update last sync timestamp file
        sync_time_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_sync.txt")
        from datetime import datetime
        with open(sync_time_file, "w") as f:
            f.write(datetime.now().isoformat())
            
        logger.info("Automatic database sync completed successfully.")
        return True
    else:
        logger.error(f"Sync failed: {response.get('error')}")
        return False

if __name__ == "__main__":
    run_sync()
