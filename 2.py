## Tools Creation

Tools are the fundamental execution units in an agentic workflow, exposed as **Model Context Protocol (MCP)** services from HPE GreenLake infrastructure nodes. Each tool encapsulates a single, well-defined capability—such as running a command, restarting a service, or parsing logs—making them modular and reusable.

### Key Characteristics

| Property | Description |
|----------|-------------|
| **Stateless** | Tools do not retain any execution context between calls |
| **SSE-Based** | Registered on the MCP server using Server-Sent Events (SSE) protocol |
| **One-Time Registration** | Tools are registered once, eliminating repetitive setup overhead |
| **Universally Accessible** | Once registered, tools can be invoked by any AI agent during orchestration |

### MCP Integration Architecture

The MCP Server hosts registered tools (run_command, restart_service, parse_logs, check_status, etc.) and communicates with the Agent Runtime via SSE connection. The Agent Runtime uses an MCP client session to load tools and invoke them during workflow execution.

### How It Works

The MCPManager component handles the connection lifecycle:

1. Establishes SSE connection to MCP server endpoint
2. Initializes a client session for bidirectional communication
3. Loads all registered tools into the orchestration context
4. Makes tools available for agent invocation during workflow execution

### Operational Benefits

- **Efficiency**: Tool creation is a one-time activity performed by the Site Reliability Engineer (SRE)
- **Reusability**: Same tools can be reused across multiple workflows
- **Consistency**: Standardized tool interfaces ensure predictable behavior
- **Reduced Complexity**: Eliminates per-workflow tool configuration

---

## Agent Creation - Logic

Agents are the intelligent decision-making units that orchestrate workflow execution. The system implements a **hierarchical agent architecture** with three distinct agent types, each serving a specific role in the workflow execution pipeline.

### Agent Type Hierarchy

The architecture follows a three-tier hierarchy:

**Tier 1: SUPERVISOR AGENT (Multi-Node Orchestrator)**
- Loops through target nodes: [node1, node2, ...]
- Runs the entire child workflow for each node

**Tier 2: DECISION SUPERVISOR AGENT (Conditional Flow Coordinator)**
- Evaluates conditions and routes to TRUE/FALSE execution paths
- Interprets results from child agents to make branching decisions

**Tier 3: EXECUTION AGENTS (Tool Invocation Units)**
- exec_check: Verifies conditions by executing diagnostic commands
- exec_action: Performs remediation actions when conditions are met

### Agent Types Summary

| Agent Type | YAML Source | Role | Tool Access |
|------------|-------------|------|-------------|
| **SUPERVISOR** | multi-node-op | Orchestrates workflow execution across multiple infrastructure nodes | None (delegates to children) |
| **DECISION SUPERVISOR** | if-else-op + decision-op | Evaluates conditions and routes workflow to appropriate execution path | None (coordinates children) |
| **EXECUTION** | rpa-op + exec-stmt | Invokes MCP tools to execute commands on target infrastructure | Full MCP toolset |

### Agent Factory - YAML to Agent Transformation

The AgentFactory parses YAML runbook definitions and creates AgentConfig objects that define each agent's behavior. It recursively walks through the nested operation structure, identifying operation types and generating appropriate agent configurations with context-aware prompts.

### Agent Configuration Structure

Each agent is defined by a configuration containing:
- **Name**: Unique identifier (e.g., "supervisor_1", "decision_supervisor_2", "exec_3")
- **Agent Type**: SUPERVISOR, DECISION_SUPERVISOR, or EXECUTION
- **Prompt**: System prompt with context and role-specific instructions
- **Metadata**: Operation-specific data (commands, conditions, timeouts)
- **Operations**: Nested child operations for hierarchical processing

### Agent Creation Examples

**1. Supervisor Agent (Multi-Node Orchestrator)**

Created from "multi-node-op" YAML operations. When the YAML specifies "Loop over each impacted node: [node1, node2]", the factory creates a supervisor agent that will iterate through the target nodes and invoke the child subgraph for each node sequentially.

**2. Decision Supervisor Agent (Conditional Coordinator)**

Created from "if-else-op" containing "decision-op". When the YAML specifies conditional logic like "Check for 404 error in nginx logs", the factory creates a decision supervisor that coordinates child agents to evaluate conditions, interprets their results, makes a TRUE/FALSE decision, and routes to the appropriate execution path.

**3. Execution Agent (Tool Invoker)**

Created from "rpa-op" containing "exec-stmt". When the YAML specifies a command like "grep -q '404' /var/log/morpheus/nginx/current", the factory creates an execution agent that uses MCP tools to execute the specified command on the target infrastructure node.

### Agent Runtime Builder

The AgentRuntimeBuilder transforms AgentConfig objects into live agent instances. It uses selective tool binding:
- EXECUTION agents receive the full MCP toolset for command execution
- SUPERVISOR agents receive no tools (they coordinate, not execute)

### Agent Creation Process

**INPUT:** YAML Runbook (declarative workflow definition)

**OUTPUT:** Executable Multi-Agent Graph

**STEP 1: PARSE & CLASSIFY**
- Read YAML runbook
- Walk through nested operations
- For each operation, determine agent type:
  - multi-node-op → SUPERVISOR
  - if-else-op → DECISION SUPERVISOR
  - rpa-op/exec-stmt → EXECUTION AGENT

**STEP 2: GENERATE CONTEXT-AWARE PROMPTS**
- For each agent, extract operational context from YAML hierarchy
- Build role-specific system prompt
- Attach metadata (commands, conditions, target nodes)

**STEP 3: INSTANTIATE WITH SELECTIVE TOOL BINDING**
- Connect to MCP server and load available tools
- For each agent configuration:
  - If EXECUTION type → Bind full MCP toolset
  - If SUPERVISOR type → No tools (orchestration only)

**STEP 4: COMPOSE HIERARCHICAL GRAPH**
- Build inner workflow graph (decision → execution flow)
- Wrap with multi-node supervisor for target iteration
- Compile into executable state machine

**OUTPUT:** Compiled StateGraph ready for invocation

---

## Innovation: Hierarchical Agent Specialization

The system introduces a **novel three-tier agent architecture** that separates concerns between orchestration, decision-making, and execution.

### Why Three Agent Types?

| Challenge | Traditional Approach | Our Innovation |
|-----------|---------------------|----------------|
| **Multi-node iteration** | Single agent tries to loop internally | **SUPERVISOR** creates a graph-level loop that runs the entire child workflow per node |
| **Conditional branching** | Agent decides AND executes in one call | **DECISION SUPERVISOR** interprets results; graph edges handle routing |
| **Tool execution** | All agents have all tools | **EXECUTION** agents are the only ones with tool access—clean separation |

### Key Design Decisions

**1. SUPERVISOR for Multi-Node Operations**

When the runbook specifies "Loop over each impacted node: [node1, node2]", a single LLM call cannot iterate. Instead of forcing an agent to "remember" to process each node, we create a **graph-level iteration pattern**:

INIT → PROCESS(node1) → ADVANCE → PROCESS(node2) → ADVANCE → AGGREGATE → END

The ADVANCE step loops back to PROCESS until all nodes are complete. This ensures **deterministic iteration** without relying on LLM memory or reasoning.

**2. DECISION SUPERVISOR for Conditional Flow**

When the runbook specifies "Check for 404 error → If found, restart service", traditional agents conflate decision-making with execution. We separate these concerns:
- **LLM Role**: Interpret evidence and output TRUE/FALSE
- **Graph Role**: Route to correct execution path based on decision

This enables **auditable decision points** and **predictable branching**.

**3. EXECUTION Agents with Exclusive Tool Access**

When the runbook specifies a command like "grep -q '404' /var/log/nginx/current", only execution agents receive MCP tools. Supervisors coordinate but never execute directly. This ensures:
- **Principle of least privilege**: Supervisors cannot accidentally invoke tools
- **Clear accountability**: Every tool invocation traces to a specific execution agent
- **Simplified debugging**: Execution failures isolate to execution agents

---

## Tool Attachment

In this orchestration model, agents are provisioned with the complete set of MCP-registered tools at creation. These tools—stateless, reusable, and registered once on the MCP server—are loaded into the orchestration context and made available to the agent as a unified capability set.

### Tool Distribution Strategy

The MCP Tool Pool contains all registered tools (run_cmd, restart, parse_logs, check_svc, etc.). The Tool Attachment Logic distributes tools based on agent type:

- **SUPERVISOR agents** → No tools (orchestration only)
- **DECISION SUPERVISOR agents** → No tools (coordination only)
- **EXECUTION agents** → Full MCP toolset for command execution

### Runtime Tool Selection

The agent **intelligently selects the appropriate tool at runtime** based on:
- Its assigned operation context
- The current target node being processed
- The command specified in the workflow definition

This approach eliminates rigid bindings, promotes flexibility, and ensures tools remain reusable across workflows, while attachment remains lightweight and efficient.

---

## Multi-Agent Communication and State Flow

The orchestration system uses **LangGraph's StateGraph** to manage communication and state flow between agents. State is propagated through the graph as a typed dictionary, enabling agents to share context, results, and decisions.

### State Schema

**WorkflowState** (for inner workflow):
- messages: Execution log/audit trail
- current_node: Active agent name
- current_target_node: Infrastructure node being processed
- results: Agent execution results
- decision_result: TRUE/FALSE from decision supervisor
- workflow_complete: Termination flag

**MultiNodeState** (for multi-node supervisor):
- target_nodes: List of nodes to process (e.g., ["node1", "node2"])
- current_target_node: Current node being processed
- current_node_index: Index in target_nodes
- node_results: Results per target node
- messages: Audit trail
- subgraph_state: State passed to child graph
- all_nodes_complete: Multi-node completion flag
- decision_result: Latest decision outcome

### Multi-Node Supervisor Pattern

The multi-node supervisor implements a **loop-based orchestration pattern** for processing multiple infrastructure nodes:

INIT → PROCESS → ADVANCE → (loop back if more nodes) → AGGREGATE → END

### State Flow Sequence

1. **INIT**: Load target_nodes ["node1", "node2"], set current_node_index to 0, set current_target_node to "node1"

2. **PROCESS (for node1)**: Invoke subgraph with current_target_node context, subgraph executes decision_supervisor → exec_check → exec_action, collect NodeResult for node1

3. **ADVANCE**: Increment current_node_index to 1, set current_target_node to "node2", check all_nodes_complete (NO → loop to PROCESS)

4. **PROCESS (for node2)**: Invoke subgraph with current_target_node context, subgraph executes decision_supervisor → exec_check → exec_action, collect NodeResult for node2

5. **ADVANCE**: Increment current_node_index to 2, check all_nodes_complete (YES → proceed to AGGREGATE)

6. **AGGREGATE**: Compile results from all nodes, calculate success/failure counts, generate summary report

7. **END**: Workflow complete

---



## Automated Execution

### Execution Flow

1. **Runbook Loading**: YAML runbook is parsed to extract workflow structure
2. **Agent Creation**: AgentFactory creates typed agents from operations
3. **MCP Connection**: MCPManager establishes SSE connection and loads tools
4. **Runtime Building**: AgentRuntimeBuilder instantiates agents with LLM and tools
5. **Graph Construction**: StateGraphBuilder creates LangGraph workflow
6. **Multi-Node Wrapping**: Graph is wrapped in multi-node supervisor for iteration
7. **Execution**: Graph is invoked with initial state
8. **Result Aggregation**: Results are collected and summarized

### Entry Point Flow

1. Parse runbook and create agent configs using AgentFactory
2. Initialize LLM (AzureChatOpenAI)
3. Connect to MCP server and load tools via MCPManager
4. Build agent instances using AgentRuntimeBuilder with selective tool binding
5. Build multi-node StateGraph from agent configs and runbook hierarchy
6. Execute the compiled graph with initial state
7. Collect and report results
