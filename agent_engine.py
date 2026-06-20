import os
import json
import logging
from typing import TypedDict, Annotated, Sequence, Literal
from dotenv import load_dotenv

# LangChain / LangGraph imports
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

# Database imports
from db_manager import get_projects, get_issues, save_weekly_report, get_weekly_reports

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory path for ChromaDB
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

# Initialize Embeddings
embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

# Initialize Vector Store
vectorstore = Chroma(persist_directory=CHROMA_DIR, embedding_function=embeddings)

# Initialize Mem0 Client if API Key is set
from mem0 import MemoryClient

MEM0_KEY = os.getenv("MEM0_API_KEY")
mem0_client = MemoryClient(api_key=MEM0_KEY) if (MEM0_KEY and MEM0_KEY != "your-api-key" and MEM0_KEY != "") else None
if mem0_client:
    logger.info("Mem0 Cloud Memory successfully initialized.")


# =====================================================================
# 1. Custom Tools for Chatbot Agent and State Machine
# =====================================================================

@tool
def list_tasks_tool() -> str:
    """
    Retrieves all projects and sprint tasks/issues from the database.
    Use this to get the overall status of the workspace, check which cycle (sprint) tasks belong to, and list assignees.
    """
    projects = get_projects()
    issues = get_issues()
    
    result = "### Simulated Plane Workspace Data\n\n"
    result += "#### Projects:\n"
    for p in projects:
        result += f"- **{p['name']}** (ID: {p['id']}) | Status (Lifecycle): {p['status']} | Health (Execution): {p['health']} | Phase: {p['phase']} | Team: {p['engineers_count']} engineers\n"
        
    result += "\n#### Issues (Tasks):\n"
    if not issues:
        result += "No tasks found.\n"
    else:
        for i in issues:
            result += f"- **[{i['id']}] {i['name']}**\n"
            result += f"  - Project: {i['project_id']} | Status: {i['status']} | Priority: {i['priority']} | Assignee: {i['assignee']} | Cycle: {i['cycle']}\n"
            result += f"  - Description: {i['description']}\n"
            if i['blocker_details']:
                result += f"  - Blocker/Delay Details: {i['blocker_details']}\n"
    return result

@tool
def filter_blockers_tool() -> str:
    """
    Specifically filters and returns tasks/issues that are currently marked as "Blocked" or "Delayed".
    Use this to identify risks, blockers, and details on project delays.
    """
    issues = get_issues()
    blocked_issues = [i for i in issues if i['status'] in ["Blocked", "Delayed"]]
    
    if not blocked_issues:
        return "No blocked or delayed issues found in the current sprint!"
        
    result = "### Currently Blocked & Delayed Issues\n\n"
    for i in blocked_issues:
        result += f"- **[{i['id']}] {i['name']}** ({i['status']})\n"
        result += f"  - Project: {i['project_id']} | Priority: {i['priority']} | Assignee: {i['assignee']}\n"
        result += f"  - Context: {i['description']}\n"
        result += f"  - **Why it is blocked/delayed**: {i['blocker_details'] or 'No details specified.'}\n\n"
    return result

@tool
def memory_search_tool(query: str) -> str:
    """
    Searches the historical weekly reports memory (via Mem0 or ChromaDB) for previous weekly summaries and trends.
    Use this to answer questions about week-over-week progress, recurring issues, or what was stuck in previous sprints.
    """
    # Try Mem0 first if available
    if mem0_client:
        try:
            search_res = mem0_client.search(query, filters={"user_id": "project_status_agent_user"})
            results = search_res.get("results", []) if isinstance(search_res, dict) else search_res
            if results:
                res_str = "### Historical Facts found in Mem0 Cloud Memory:\n\n"
                for idx, r in enumerate(results):
                    if isinstance(r, dict):
                        fact = r.get("memory") or r.get("text")
                        metadata = r.get("metadata", {}) or {}
                        date = metadata.get("report_date", "Unknown")
                        res_str += f"- {fact} (Date: {date})\n"
                    else:
                        res_str += f"- {str(r)}\n"
                return res_str
        except Exception as e:
            logger.error(f"Mem0 search error, falling back to ChromaDB: {e}")

    # Fallback to local ChromaDB
    try:
        docs = vectorstore.similarity_search(query, k=3)
        if not docs:
            # Fallback to query SQLite database directly if Chroma is empty
            reports = get_weekly_reports()
            if not reports:
                return "No historical reports found in memory."
            # Return raw summaries as fallback
            result = "No exact vector matches. Showing last report from database:\n\n"
            result += reports[0]['report_markdown']
            return result
            
        result = "### Historical Report Snippets found in memory:\n\n"
        for idx, doc in enumerate(docs):
            result += f"--- Result {idx+1} (Date: {doc.metadata.get('report_date', 'Unknown')}) ---\n"
            result += doc.page_content + "\n\n"
        return result
    except Exception as e:
        logger.error(f"Error searching ChromaDB: {e}")
        return f"Error querying historical memory: {str(e)}"

@tool
def save_report_tool(report_date: str, report_markdown: str) -> str:
    """
    Saves a finalized weekly status report to the database and indexes it in both ChromaDB and Mem0 memory.
    This enables trend tracking across weeks.
    """
    try:
        # Save to SQLite
        report_id = save_weekly_report(report_date, report_markdown)
        
        # Index in ChromaDB
        doc = Document(
            page_content=report_markdown,
            metadata={"report_date": report_date, "report_id": report_id}
        )
        vectorstore.add_documents([doc])
        
        # Index in Mem0 Cloud Memory if available
        if mem0_client:
            try:
                logger.info(f"Indexing report in Mem0 Cloud Memory for date {report_date}...")
                mem0_client.add(
                    report_markdown, 
                    user_id="project_status_agent_user", 
                    metadata={"report_date": report_date}
                )
            except Exception as e:
                logger.error(f"Failed to save to Mem0: {e}")
        
        return f"Successfully saved and indexed weekly report for {report_date} (ID: {report_id}) in SQLite, ChromaDB, and Mem0."
    except Exception as e:
        logger.error(f"Failed to save report: {e}")
        return f"Failed to save report: {str(e)}"

@tool
def add_memory_tool(fact: str) -> str:
    """
    Saves a new fact, context, or user preference to the semantic memory (Mem0 and ChromaDB).
    Use this when the user explicitly asks you to remember something, provides new contextual details,
    or tells you about project updates, status corrections, or engineering roles.
    """
    try:
        # Index in ChromaDB
        doc = Document(
            page_content=fact,
            metadata={"source": "user_chat", "report_date": "N/A"}
        )
        vectorstore.add_documents([doc])
        
        # Index in Mem0 Cloud Memory if available
        if mem0_client:
            try:
                mem0_client.add(
                    fact, 
                    user_id="project_status_agent_user",
                    metadata={"source": "user_chat"}
                )
                return f"Successfully saved and indexed memory: '{fact}' in Mem0 and ChromaDB."
            except Exception as e:
                logger.error(f"Failed to save to Mem0: {e}")
                return f"Saved memory to ChromaDB, but failed to save to Mem0: {str(e)}"
        
        return f"Successfully saved and indexed memory: '{fact}' in ChromaDB (Mem0 is offline)."
    except Exception as e:
        logger.error(f"Failed to save memory: {e}")
        return f"Failed to save memory: {str(e)}"

# Collection of tools for the chatbot
CHAT_TOOLS = [list_tasks_tool, filter_blockers_tool, memory_search_tool, add_memory_tool]


# =====================================================================
# 2. LLM Setup (Nebius Studio and Groq support)
# =====================================================================

def get_llm(provider="nebius", temperature=0.2):
    """Initializes and returns the selected LLM client (Nebius or Groq)."""
    if provider == "nebius":
        api_key = os.environ.get("NEBIUS_API_KEY")
        if not api_key:
            logger.warning("NEBIUS_API_KEY not found, falling back to Groq")
            provider = "groq"
        else:
            base_url = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.ai/v1/")
            return ChatOpenAI(
                base_url=base_url,
                api_key=api_key,
                model="meta-llama/Llama-3.3-70B-Instruct",
                temperature=temperature
            )
            
    if provider == "groq":
        # We can use ChatOpenAI configured with Groq endpoint or import ChatGroq
        # To avoid importing other packages, use OpenAI client pointing to Groq
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Neither NEBIUS_API_KEY nor GROQ_API_KEY is configured in .env")
        return ChatOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
            model="llama-3.1-8b-instant",
            temperature=temperature
        )


# =====================================================================
# 3. LangGraph Flow for Weekly Report Generation (HITL)
# =====================================================================

class ReportState(TypedDict):
    messages: list[BaseMessage]
    current_report_draft: str
    approved: bool
    tasks_context: str
    historical_context: str
    report_date: str
    feedback: str
    project_id: str

# 3.1 Retrieve Data Node
def retrieve_context_node(state: ReportState):
    project_id = state.get("project_id", "")
    logger.info(f"Node: Retrieve Context for project ID: {project_id}")
    
    # Resolve project name
    project_name = project_id
    try:
        projects = get_projects()
        for p in projects:
            if p["id"] == project_id:
                project_name = p["name"]
                break
    except Exception as e:
        logger.error(f"Error fetching projects in retrieve_context: {e}")
        
    # 1. Gather current task details specifically for this project
    issues = get_issues(project_id)
    
    tasks_data = f"### Active Issues for Project: {project_name} (ID: {project_id})\n\n"
    if not issues:
        tasks_data += "No issues found for this project.\n"
    else:
        for i in issues:
            tasks_data += f"- **[{i['id']}] {i['name']}**\n"
            tasks_data += f"  - Status: {i['status']} | Priority: {i['priority']} | Assignee: {i['assignee']} | Cycle: {i['cycle']}\n"
            tasks_data += f"  - Description: {i['description']}\n"
            if i['blocker_details']:
                tasks_data += f"  - Blocker/Delay Details: {i['blocker_details']}\n"
    
    # 2. Query historical trends for this project
    query = f"Find recent weekly reports and blockers for project {project_name}"
    history_data = memory_search_tool.invoke(query)
    
    return {
        "tasks_context": tasks_data,
        "historical_context": history_data
    }

# 3.2 Draft Report Node
def draft_report_node(state: ReportState):
    logger.info("Node: Draft Report")
    
    tasks = state.get("tasks_context", "")
    history = state.get("historical_context", "")
    report_date = state.get("report_date", "")
    feedback = state.get("feedback", "")
    project_id = state.get("project_id", "")
    
    # Resolve project name
    project_name = project_id
    try:
        projects = get_projects()
        for p in projects:
            if p["id"] == project_id:
                project_name = p["name"]
                break
    except Exception as e:
        logger.error(f"Error fetching projects in draft_report: {e}")
    
    system_prompt = """You are an Intelligent Project Status Agent. Your task is to draft a comprehensive, highly professional weekly project status report in Markdown for the specific project: {project_name}.
    
    Use the following current task status information and historical context:
    
    ### CURRENT TASKS & STATUS:
    {tasks}
    
    ### HISTORICAL TRENDS SUMMARY:
    {history}
    
    Instructions:
    1. Organize the report clearly into these sections:
       - **# Project Status Report - Project: {project_name} (Week of {report_date})**
       - **## Executive Summary**: Summarize the overall health of the {project_name} project. Total active, completed, blocked, or delayed tasks. Call out if blockers are newly introduced this week or stuck from previous sprints.
       - **## Sprint Backlog Health Table**: Create a clean markdown table showing all tasks for this project: Task ID, Task Name, Status (Todo / In Progress / Blocked / Done / Delayed), Priority, and Assignee.
       - **## Risks & Key Blockers Detail**: Call out specific issues, explaining why they are blocked/delayed and listing the assignee.
       - **## Week-over-Week Trends**: Detail which tasks remain stuck from the previous weeks (compare against historical trends) and verify if progress was made.
       - **## Recommended Actions**: Generate 3 practical action items to resolve the blockers and delays specifically for this project.
    2. Maintain factual grounding. Do not hallucinate tasks or statuses.
    3. Ensure the tone is objective and analytical.
    """
    
    messages = [
        SystemMessage(content=system_prompt.format(project_name=project_name, tasks=tasks, history=history, report_date=report_date))
    ]
    
    if feedback:
        messages.append(HumanMessage(content=f"Please edit the previous draft. User Feedback: {feedback}"))
    else:
        messages.append(HumanMessage(content="Please generate the initial status report draft."))
        
    llm = get_llm(temperature=0.3)
    response = llm.invoke(messages)
    
    return {
        "current_report_draft": response.content,
        "feedback": "" # Reset feedback
    }

# 3.3 Human Review Node (Placeholder / Breakpoint trigger)
def human_review_node(state: ReportState):
    logger.info("Node: Human Review Checkpoint")
    # This node does nothing computationally. It is a marker for the LangGraph breakpoint.
    return state

# 3.4 Save Report Node
def save_report_node(state: ReportState):
    logger.info("Node: Save & Index Report")
    report_date = state.get("report_date")
    report_content = state.get("current_report_draft")
    
    # Run the save tool
    result = save_report_tool.invoke({"report_date": report_date, "report_markdown": report_content})
    logger.info(result)
    
    return state

# 3.5 Routing condition
def should_continue(state: ReportState) -> Literal["save", "draft"]:
    if state.get("approved"):
        return "save"
    return "draft"

# Build the Graph
workflow = StateGraph(ReportState)
workflow.add_node("retrieve_context", retrieve_context_node)
workflow.add_node("draft_report", draft_report_node)
workflow.add_node("human_review", human_review_node)
workflow.add_node("save_report", save_report_node)

workflow.set_entry_point("retrieve_context")
workflow.add_edge("retrieve_context", "draft_report")
workflow.add_edge("draft_report", "human_review")
workflow.add_conditional_edges(
    "human_review",
    should_continue,
    {
        "save": "save_report",
        "draft": "draft_report"
    }
)
workflow.add_edge("save_report", END)

# Compile graph with memory checkpoints for HITL support
memory_checkpoint = MemorySaver()
report_graph = workflow.compile(
    checkpointer=memory_checkpoint,
    interrupt_before=["human_review"]
)


# =====================================================================
# 4. Interactive Chatbot ReAct Agent Loop
# =====================================================================

def query_chatbot(user_message: str, chat_history: list, provider="nebius") -> str:
    """Runs a single ReAct step or multi-turn conversational loop to query the project status agent."""
    llm = get_llm(provider=provider, temperature=0.1)
    
    # Core system instructions for the project analyst
    system_prompt = """You are an Intelligent Project Status Agent for Plane workspace management. 
    You have tools to query the current issues, filter blocked tasks, search historical weekly reports, and add new memories.
    
    Use the tools when the user asks questions about task statuses, workload distribution, blockers, or historical trends.
    Use the add_memory_tool when the user explicitly asks you to remember a fact/preference, or when they share new information/updates about engineers, project statuses, or blocker details that you should keep in long-term memory.
    Always provide clear, structured, and helpful summaries in markdown.
    If you don't have information from tools to answer the question, state that you cannot find it.
    
    Strictly enforce the boundary: You CANNOT perform 'Write' actions on tasks (e.g. updating issue statuses or finalizing reports in Plane/DB) without human approval. You are a 'Read' and 'Analysis' agent, but you CAN update your own memory using add_memory_tool.
    """
    
    # Prepare messages payload
    messages = [SystemMessage(content=system_prompt)]
    
    # Append historical conversations
    for msg in chat_history[-6:]:  # limit context to last 3 exchanges
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
            
    # Append current user query
    messages.append(HumanMessage(content=user_message))
    
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(CHAT_TOOLS)
    
    try:
        response = llm_with_tools.invoke(messages)
        
        # Tool execution loop
        if response.tool_calls:
            # Append AI's intent to call tools to message history
            messages.append(response)
            
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                
                # Retrieve the actual function
                tool_func = None
                if tool_name == "list_tasks_tool":
                    tool_func = list_tasks_tool
                elif tool_name == "filter_blockers_tool":
                    tool_func = filter_blockers_tool
                elif tool_name == "memory_search_tool":
                    tool_func = memory_search_tool
                elif tool_name == "add_memory_tool":
                    tool_func = add_memory_tool
                
                if tool_func:
                    logger.info(f"Executing tool: {tool_name} with args {tool_args}")
                    tool_result = tool_func.invoke(tool_args)
                    # Create Tool message
                    from langchain_core.messages import ToolMessage
                    tool_message = ToolMessage(content=tool_result, tool_call_id=tool_call["id"])
                    messages.append(tool_message)
                else:
                    messages.append(HumanMessage(content=f"Error: Tool {tool_name} not found."))
            
            # Make final call to LLM with tool results included
            final_response = llm.invoke(messages)
            return final_response.content
        else:
            return response.content
            
    except Exception as e:
        logger.error(f"Error querying agent: {e}")
        return f"Sorry, I encountered an error answering that: {str(e)}"
