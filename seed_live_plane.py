import os
import requests
import json
import logging
from dotenv import load_dotenv

# Load credentials
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("PLANE_API_KEY")
WORKSPACE_SLUG = os.getenv("PLANE_WORKSPACE_SLUG", "project-status-agent")
BASE_URL = os.getenv("PLANE_BASE_URL", "https://api.plane.so/api/v1").rstrip("/")

headers = {
    "x-api-key": API_KEY,
    "Content-Type": "application/json"
}

def make_request(method, endpoint, payload=None):
    url = f"{BASE_URL}{endpoint}"
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(url, headers=headers, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            return response.json()
        else:
            logger.error(f"Error {response.status_code} on {endpoint}: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Exception on {endpoint}: {e}")
        return None

def get_or_create_project(name, identifier, description):
    """Checks if project exists by identifier; if not, creates it."""
    # List existing projects
    projects = make_request("GET", f"/workspaces/{WORKSPACE_SLUG}/projects/")
    if projects:
        results = projects.get("results", []) if isinstance(projects, dict) else projects
        for p in results:
            if p.get("identifier") == identifier:
                logger.info(f"Project '{name}' ({identifier}) already exists with ID: {p.get('id')}")
                return p.get("id")
                
    # Create project
    logger.info(f"Creating project '{name}' ({identifier})...")
    payload = {
        "name": name,
        "identifier": identifier,
        "description": description
    }
    project = make_request("POST", f"/workspaces/{WORKSPACE_SLUG}/projects/", payload)
    if project:
        logger.info(f"Successfully created project '{name}' with ID: {project.get('id')}")
        return project.get("id")
    return None

def get_state_mapping(project_id):
    """Retrieves states list for the project and maps names/groups to UUIDs."""
    states_data = make_request("GET", f"/workspaces/{WORKSPACE_SLUG}/projects/{project_id}/states/")
    mapping = {}
    if states_data:
        results = states_data.get("results", []) if isinstance(states_data, dict) else states_data
        for s in results:
            name = s.get("name", "").lower()
            group = s.get("group", "").lower()
            state_id = s.get("id")
            
            # Map by standard names
            if "backlog" in name or group == "backlog":
                mapping["backlog"] = state_id
            elif "todo" in name or "to do" in name or group == "unstarted":
                mapping["todo"] = state_id
            elif "progress" in name or "started" in name or group == "started":
                mapping["in progress"] = state_id
            elif "done" in name or "completed" in name or group == "completed":
                mapping["done"] = state_id
            elif "block" in name or "hold" in name:
                mapping["blocked"] = state_id
                
        # Default fallbacks if keys not set
        all_states = [s.get("id") for s in results]
        if all_states:
            if "todo" not in mapping: mapping["todo"] = all_states[0]
            if "in progress" not in mapping: mapping["in progress"] = all_states[0]
            if "done" not in mapping: mapping["done"] = all_states[-1]
            if "blocked" not in mapping: mapping["blocked"] = all_states[0]
            if "delayed" not in mapping: mapping["delayed"] = all_states[0]
            
    return mapping

def seed_issues():
    if not API_KEY:
        logger.error("PLANE_API_KEY is not defined in the environment!")
        return

    print("==================================================")
    print("🌱 SEEDING LIVE PLANE WORKSPACE")
    print("==================================================")

    # 1. Define Projects to create
    mock_projects = [
        {"name": "Data Pipeline Upgrade", "identifier": "DPU", "desc": "Spark migration"},
        {"name": "Mobile App Redesign", "identifier": "MOB", "desc": "Figma layout overhaul"},
        {"name": "Security Audit Patch", "identifier": "SEC", "desc": "Fixing dependency CVEs"},
        {"name": "Legacy System Migration", "identifier": "LEG", "desc": "Moving db2 schemas to cloud"}
    ]

    project_ids = {}
    for p in mock_projects:
        proj_id = get_or_create_project(p["name"], p["identifier"], p["desc"])
        if proj_id:
            project_ids[p["identifier"]] = proj_id

    # 2. Define Issues to create
    mock_issues = [
        {
            "proj_key": "DPU",
            "name": "Migrate pipeline jobs to Spark cluster",
            "priority": "high",
            "status": "in progress",
            "desc": "Rewrite the batch ETL pipelines to run on Spark cluster to handle larger datasets."
        },
        {
            "proj_key": "DPU",
            "name": "Configure Kafka schema registry",
            "priority": "medium",
            "status": "todo",
            "desc": "Register schemas for user activity event telemetry streams."
        },
        {
            "proj_key": "DPU",
            "name": "Resolve Spark memory leakage under load",
            "priority": "urgent",
            "status": "blocked",
            "desc": "Executor processes crash when processing partitions over 50GB. Blocked due to waiting on infrastructure team to configure larger memory allocation and garbage collection parameters on Kubernetes nodes."
        },
        {
            "proj_key": "DPU",
            "name": "Verify Spark ETL pipeline parity against DB2",
            "priority": "low",
            "status": "todo",
            "desc": "Check checksum and count values for processed event batches."
        },
        {
            "proj_key": "MOB",
            "name": "Implement Figma dark mode design system",
            "priority": "urgent",
            "status": "blocked",
            "desc": "Convert Figma colors and layout parameters into CSS-in-JS design tokens. Blocked because final design tokens JSON file has missing secondary screen values."
        },
        {
            "proj_key": "MOB",
            "name": "Write unit tests for authentication hooks",
            "priority": "medium",
            "status": "todo",
            "desc": "Establish unit tests using React Testing Library for custom auth hooks."
        },
        {
            "proj_key": "MOB",
            "name": "Integrate OAuth2 login flow with Keycloak",
            "priority": "high",
            "status": "in progress",
            "desc": "Implement PKCE auth flow on mobile frontend side and connect it to Keycloak endpoints."
        },
        {
            "proj_key": "MOB",
            "name": "Refactor navigation state transitions",
            "priority": "medium",
            "status": "delayed",
            "desc": "Slow animations in React Native screen changes. Delayed because we need to upgrade the react-native-screens package, which has compatibility issues with current Expo version."
        },
        {
            "proj_key": "SEC",
            "name": "Address CVE-2025-XXXX package vulnerabilities",
            "priority": "urgent",
            "status": "delayed",
            "desc": "Upgrade legacy crypto libraries. Delayed because major upgrade introduces breaking changes in the database encryption wrappers."
        },
        {
            "proj_key": "SEC",
            "name": "Audit npm packages lockfile",
            "priority": "medium",
            "status": "done",
            "desc": "Analyze npm packages using npm audit and resolve vulnerabilities."
        },
        {
            "proj_key": "LEG",
            "name": "Extract requirements for legacy mainframes",
            "priority": "high",
            "status": "in progress",
            "desc": "Hold workshops with domain experts to map data schemas of mainframe DB2 tables."
        },
        {
            "proj_key": "LEG",
            "name": "Establish DB2 data dump extract scripts",
            "priority": "high",
            "status": "blocked",
            "desc": "Write JCL jobs to extract transactional data. Blocked because mainframe database administration team has not granted read access permissions to the schema files yet."
        }
    ]

    # Create issues in Plane
    for issue in mock_issues:
        proj_id = project_ids.get(issue["proj_key"])
        if not proj_id:
            logger.warning(f"Project ID not found for key {issue['proj_key']}. Skipping issue.")
            continue
            
        # Get state mappings
        state_mapping = get_state_mapping(proj_id)
        state_id = state_mapping.get(issue["status"].lower(), state_mapping.get("todo"))
        
        # Check if issue already exists in project issues list to avoid duplicates
        existing = make_request("GET", f"/workspaces/{WORKSPACE_SLUG}/projects/{proj_id}/issues/")
        exists = False
        if existing:
            results = existing.get("results", []) if isinstance(existing, dict) else existing
            for ex_iss in results:
                if ex_iss.get("name") == issue["name"]:
                    logger.info(f"Issue '{issue['name']}' already exists in project {issue['proj_key']}")
                    exists = True
                    break
        
        if exists:
            continue
            
        # Create Issue
        logger.info(f"Creating issue '{issue['name']}' in project {issue['proj_key']}...")
        payload = {
            "name": issue["name"],
            "description_html": f"<p>{issue['desc']}</p>",
            "priority": issue["priority"],
            "state": state_id
        }
        
        res = make_request("POST", f"/workspaces/{WORKSPACE_SLUG}/projects/{proj_id}/issues/", payload)
        if res:
            logger.info(f"Successfully created issue with sequence ID: {res.get('sequence_id') or res.get('id')}")

    print("\n==================================================")
    print("🎉 SEEDING COMPLETED SUCCESSFUL!")
    print("==================================================")

if __name__ == "__main__":
    seed_issues()
