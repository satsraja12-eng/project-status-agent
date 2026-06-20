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
