# LangGraph Weekly Report Generator - Visual Flow & Scenarios

This guide provides a pictorial view of the step-by-step state machine execution, highlighting how the application transitions between autonomous agent nodes and human-in-the-loop intervention.

---

## 🗺️ Step-by-Step Flowchart

The diagram below maps the 5 steps of the weekly report generator lifecycle. Notice how the graph is forced to pause at the human review checkpoint:

```mermaid
flowchart TD
    classDef start_end fill:#111827,stroke:#374151,stroke-width:2px,color:#FFF;
    classDef step fill:#1E293B,stroke:#6366F1,stroke-width:2px,color:#FFF;
    classDef checkpoint fill:#1E1B4B,stroke:#8B5CF6,stroke-width:2px,color:#FFF;
    classDef user_action fill:#451A03,stroke:#F59E0B,stroke-width:2px,color:#FFF;
    classDef success fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#FFF;

    Start([🚀 User clicks 'Draft Weekly Report']):::start_end --> Step1["Step 1: Retrieve Context Node<br>• Pull active sprint tasks from SQLite DB<br>• Query historical report context from ChromaDB"]:::step
    
    Step1 --> Step2["Step 2: Draft Report Node<br>• Combine current tasks & history<br>• Llama 3.3 writes structured draft report"]:::step
    
    Step2 --> Step3["Step 3: Human Review Breakpoint<br>• Graph halts execution before 'human_review' node<br>• Saves state checkpoint to thread database"]:::checkpoint
    
    Step3 --> UI["🖥️ UI Renders Editable Text Area<br>User reviews draft report in Streamlit"]:::user_action
    
    UI --> Action{User Action in UI}
    
    %% Scenario B
    Action -- "Scenario B: Request Changes<br>(Enter feedback & click 'Regenerate')" --> Feedback["Step 4: Update State with Feedback<br>• Set feedback = user_input<br>• Set approved = False<br>• Resume Graph"]:::user_action
    Feedback --> Step2
    
    %% Scenario C
    Action -- "Scenario C: Approve Draft<br>(Click 'Approve & Save')" --> Approve["Step 5: Finalize and Save<br>• Update state: approved = True<br>• Resume Graph"]:::success
    
    Approve --> SaveNode["Step 5 (cont): Save & Index Node<br>• Write report to SQLite archives<br>• Embed & save in ChromaDB vector memory"]:::step
    
    SaveNode --> End([🏁 End Workflow]):::start_end
```

---

## 🎬 Interaction Scenarios (Sequence Views)

The following diagrams illustrate the communication sequence between the **Streamlit Frontend**, the **LangGraph Orchestrator**, and the **SQLite/Vector Databases** for each of the three user interaction scenarios:

### Scenario A: Initial Drafting (Steps 1–3)
The user initiates the workflow. The graph gathers data, writes the initial layout, and freezes state.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Streamlit UI
    participant Graph as LangGraph Engine
    participant DB as SQLite / Chroma DB
    participant LLM as Llama 3.3 (Nebius)

    User->>UI: Click "Draft Weekly Report"
    UI->>Graph: report_graph.stream(initial_state, config)
    activate Graph
    Graph->>DB: Query current tasks & past reports
    DB-->>Graph: Return sprint details & trends
    Graph->>LLM: Send context to write report
    LLM-->>Graph: Return draft text
    Note over Graph: Graph reaches "human_review" breakpoint
    Graph->>DB: Save state checkpoint (thread_id)
    deactivate Graph
    Graph-->>UI: Return control (Pause)
    UI->>User: Display editable report draft in UI
```

---

### Scenario B: Refinement Feedback Loop (Step 4)
The user reviews the draft, identifies a correction or missing fact, inputs text feedback, and requests a rebuild.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Streamlit UI
    participant Graph as LangGraph Engine
    participant LLM as Llama 3.3 (Nebius)

    User->>UI: Input feedback (e.g., "Mention Bob is sick") + click "Regenerate"
    UI->>Graph: report_graph.update_state(feedback="...", approved=False)
    UI->>Graph: report_graph.stream(None, config)
    activate Graph
    Graph->>LLM: Send original context + new user feedback
    LLM-->>Graph: Return revised draft text
    Note over Graph: Graph hits "human_review" breakpoint again
    deactivate Graph
    Graph-->>UI: Return control (Pause)
    UI->>User: Display updated report draft in UI
```

---

### Scenario C: Final Approval & Archiving (Step 5)
The user is satisfied with the text, approves it, and the system permanently commits it to memory.

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant UI as Streamlit UI
    participant Graph as LangGraph Engine
    participant DB as SQLite / Chroma DB

    User->>UI: Click "Approve & Save Report"
    UI->>Graph: report_graph.update_state(approved=True)
    UI->>Graph: report_graph.stream(None, config)
    activate Graph
    Note over Graph: approved is True -> Route to save_report
    Graph->>DB: Save report to SQLite tables
    Graph->>DB: Add report to ChromaDB vector store
    deactivate Graph
    Graph-->>UI: Return control (Finish)
    UI->>User: Show success checkmark + enable report downloads
```

---

## 🧠 Components & Data Flow (How ReAct, Mem0, SQLite, and ChromaDB are involved)

Here is a detailed breakdown of how each component is involved during different stages of the application lifecycle:

### 1. SQLite Database (`project_status.db`)
* **When it is involved**: Ground-truth data storage.
* **Usage**:
  - Used by `list_tasks_tool` and `filter_blockers_tool` to query active tasks and dependencies.
  - Used by the Streamlit dashboard to render KPI cards, Plotly stacked bar charts, and timeline stages.
  - Used by the `save_report_node` to save the final approved markdown report.

### 2. ChromaDB (Local Vector Database)
* **When it is involved**: Historical report search and week-over-week trend analysis.
* **Usage**:
  - When the report is approved (`save_report_node`), it is embedded using the `BAAI/bge-small-en-v1.5` local model and stored inside the `chroma_db/` folder.
  - When the ReAct Agent is asked about past performance trends, it triggers `memory_search_tool` to run a semantic search across the ChromaDB database to retrieve the top 3 matching report snippets.

### 3. Mem0 Cloud (Atomic Memory Engine)
* **When it is involved**: Guidelines, calendars, and user-defined operational rules storage.
* **Usage**:
  - When a user inputs a rule in the **Operational Rules** panel, it is saved directly to Mem0 Cloud via `mem0_client.add()`.
  - When the ReAct Agent is asked a question, it queries Mem0 Cloud using `memory_search_tool` to pull relevant facts.
  - The ReAct Agent can autonomously add facts from conversation context by invoking `add_memory_tool`.

---

### 💬 ReAct Chat Loop & Memory Interaction

When a user asks a question in the **AI Assistant Chat**, Llama 3.3 acts as a reasoning engine, deciding dynamically which tools to run to compile the answer:

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Chatbot as Streamlit Chat UI
    participant ReAct as ReAct Agent (Llama 3.3)
    participant Tools as Custom Tools
    participant DB as SQLite DB
    participant Chroma as ChromaDB Vector Store
    participant Mem0 as Mem0 Cloud Memory

    User->>Chatbot: Ask "Who leads the upgrade project and what is blocked?"
    Chatbot->>ReAct: query_chatbot(message, history)
    activate ReAct
    
    Note over ReAct: Decide to query Mem0 for project roles/rules
    ReAct->>Tools: Call memory_search_tool("Lead of upgrade project")
    activate Tools
    Tools->>Mem0: Fetch facts matching query
    Mem0-->>Tools: Return "Sathish is the Lead Architect"
    deactivate Tools
    
    Note over ReAct: Decide to check current sprint blockers
    ReAct->>Tools: Call filter_blockers_tool()
    activate Tools
    Tools->>DB: Query issue backlog for Blocked state
    DB-->>Tools: Return "PLANE-2 Kafka Registry is Blocked"
    deactivate Tools

    Note over ReAct: Decide to search ChromaDB for past blocker trends
    ReAct->>Tools: Call memory_search_tool("Kafka blockers")
    activate Tools
    Tools->>Chroma: Query similar past report snippets
    Chroma-->>Tools: Return "Week of June 8: Kafka registry configuration stalled"
    deactivate Tools

    Note over ReAct: Synthesize facts, tasks, and trends into final response
    ReAct-->>Chatbot: Return structured markdown answer
    deactivate ReAct
    Chatbot->>User: Display answer: "Sathish leads... PLANE-2 is blocked (stalled since June 8)"
```

