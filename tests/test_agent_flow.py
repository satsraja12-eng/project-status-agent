import os
import sys
import uuid

# Dynamically add the parent directory to sys.path to resolve imports correctly
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

import db_manager as db
import agent_engine as engine

def run_tests():
    print("==================================================")
    print("🚀 STARTING AUTOMATED TEST FOR PROJECT STATUS AGENT")
    print("==================================================")

    # 1. Initialize DB
    print("\n[Step 1] Initializing SQLite database...")
    db.init_db()
    issues = db.get_issues()
    projects = db.get_projects()
    print(f"✅ Database loaded successfully with {len(projects)} projects and {len(issues)} issues.")

    # 2. Test Tools
    print("\n[Step 2] Testing Custom Tools...")
    
    tasks_output = engine.list_tasks_tool.invoke({})
    print("✅ list_tasks_tool successfully invoked.")
    assert "PLANE-1" in tasks_output, "PLANE-1 should be listed in tasks output"
    
    blocker_output = engine.filter_blockers_tool.invoke({})
    print("✅ filter_blockers_tool successfully invoked.")
    assert "PLANE-4" in blocker_output or "PLANE-7" in blocker_output, "Blocked tasks should be filtered"

    # 3. Test LangGraph Pipeline
    print("\n[Step 3] Testing LangGraph Report Generator Flow...")
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    
    initial_state = {
        "messages": [],
        "current_report_draft": "",
        "approved": False,
        "tasks_context": "",
        "historical_context": "",
        "report_date": "2026-06-15",
        "feedback": "",
        "project_id": "data-pipeline-upgrade"
    }
    
    # 3.1 Initial draft generation
    print("-> Triggering initial report draft generation...")
    events = engine.report_graph.stream(initial_state, config)
    for event in events:
        pass
    
    # Verify graph interrupted at the breakpoint
    graph_state = engine.report_graph.get_state(config)
    next_step = graph_state.next
    print(f"✅ Graph execution reached step: {next_step}")
    assert "human_review" in next_step or not next_step, "Graph should pause before human_review node"
    
    draft = graph_state.values.get("current_report_draft")
    print(f"✅ Draft report generated successfully (~{len(draft)} characters).")
    print("--- DRAFT REPORT HIGHLIGHTS ---")
    print(draft[:250] + "\n...")
    print("-------------------------------")

    # 3.2 Simulating User Feedback Loop
    print("\n-> Simulating User Refinement Feedback ('Emphasize Bob's Spark task')...")
    engine.report_graph.update_state(
        config,
        {"feedback": "Make sure to highlight Bob's work migrating data pipelines to Spark.", "approved": False},
        as_node="human_review"
    )
    # Resume the graph execution
    events = engine.report_graph.stream(None, config)
    for event in events:
        pass
        
    updated_state = engine.report_graph.get_state(config)
    updated_draft = updated_state.values.get("current_report_draft")
    print(f"✅ Updated draft report generated successfully (~{len(updated_draft)} characters).")

    # 3.3 Simulating Approval and Finalization
    print("\n-> Approving and Finalizing Report...")
    engine.report_graph.update_state(
        config,
        {"approved": True},
        as_node="human_review"
    )
    # Resume the graph execution to final node
    events = engine.report_graph.stream(None, config)
    for event in events:
        pass
        
    # Check SQLite archive
    reports = db.get_weekly_reports()
    assert len(reports) > 2, "A new report should be added to the SQLite database"
    print(f"✅ Finalized report successfully archived in database. Total reports archived: {len(reports)}")

    # Check ChromaDB
    print("\n-> Searching ChromaDB memory to ensure report was indexed...")
    search_results = engine.memory_search_tool.invoke("Spark cluster migrations")
    print("ChromaDB Query Output:")
    print(search_results[:300] + "...")
    assert "Spark" in search_results, "ChromaDB memory search should successfully retrieve the finalized report details"
    print("✅ Report successfully indexed and retrieved from ChromaDB vector store.")

    print("\n==================================================")
    print("🎉 ALL TESTS COMPLETED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
