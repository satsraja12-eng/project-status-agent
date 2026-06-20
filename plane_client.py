import requests
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PlaneClient:
    def __init__(self, api_key=None, base_url=None):
        self.api_key = api_key or os.getenv("PLANE_API_KEY")
        self.base_url = (base_url or os.getenv("PLANE_BASE_URL", "https://api.plane.so/api/v1")).rstrip("/")
        
    def fetch_issues(self, workspace_slug, project_slug):
        """
        Fetches issues for a specific workspace and project from Plane.so API.
        Endpoint: GET /api/v1/workspaces/{workspace_slug}/projects/{project_slug}/issues/
        """
        if not self.api_key:
            logger.error("Plane API Key is not set.")
            return {"error": "API key is missing"}

        url = f"{self.base_url}/workspaces/{workspace_slug}/projects/{project_slug}/issues/"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        try:
            logger.info(f"Fetching issues from Plane: {url}")
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 401:
                return {"error": "Unauthorized. Please check your Plane API Key."}
            elif response.status_code == 404:
                return {"error": "Workspace or Project not found. Check slugs."}
            
            response.raise_for_status()
            data = response.json()
            
            # Plane returns a paginated list or list of results
            results = data.get("results", []) if isinstance(data, dict) else data
            
            mapped_issues = []
            for issue in results:
                # 1. Parse Assignees
                assignee_name = "Unassigned"
                assignees = issue.get("assignees", []) or issue.get("assignee_details", [])
                if assignees:
                    # In some API versions, assignee is a list of display names or user objects
                    first_assignee = assignees[0]
                    if isinstance(first_assignee, dict):
                        assignee_name = first_assignee.get("display_name") or first_assignee.get("first_name", "Unassigned")
                    else:
                        assignee_name = str(first_assignee)
                
                # 2. Parse State (Status)
                state_name = "Todo"
                state_detail = issue.get("state_detail", {})
                if isinstance(state_detail, dict):
                    state_name = state_detail.get("name", "Todo")
                else:
                    state_name = issue.get("state", "Todo")
                
                # Normalize state name to match our categories: Todo, In Progress, Blocked, Done, Delayed
                norm_state = "Todo"
                state_lower = state_name.lower()
                if "progress" in state_lower or "started" in state_lower:
                    norm_state = "In Progress"
                elif "block" in state_lower or "hold" in state_lower:
                    norm_state = "Blocked"
                elif "done" in state_lower or "complete" in state_lower or "closed" in state_lower:
                    norm_state = "Done"
                elif "delay" in state_lower or "late" in state_lower:
                    norm_state = "Delayed"
                
                # 3. Parse Cycle (Sprint)
                cycle_name = "Backlog"
                cycle_detail = issue.get("cycle_detail", {})
                if isinstance(cycle_detail, dict):
                    cycle_name = cycle_detail.get("name", "Backlog")
                
                # 4. Blocker description detection
                blocker_details = None
                if norm_state == "Blocked":
                    blocker_details = issue.get("blocker_details") or "No blocker detail provided. Status set to Blocked."
                elif norm_state == "Delayed":
                    blocker_details = issue.get("blocker_details") or "No delay details provided. Status set to Delayed."

                mapped_issues.append({
                    "id": issue.get("sequence_id") or f"PLANE-{issue.get('id', '')[:8]}",
                    "project_id": project_slug,
                    "name": issue.get("name", "Untitled Issue"),
                    "assignee": assignee_name,
                    "status": norm_state,
                    "priority": issue.get("priority", "medium").capitalize(),
                    "cycle": cycle_name,
                    "description": issue.get("description_text") or issue.get("description", ""),
                    "blocker_details": blocker_details,
                    "updated_at": issue.get("updated_at", "")
                })
                
            return {"success": True, "issues": mapped_issues}
            
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request failed: {e}")
            return {"error": f"Failed to connect to Plane: {str(e)}"}
