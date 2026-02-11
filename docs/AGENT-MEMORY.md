# Agent Memory with Engram

> Ideas for how AI sub-agents can use Engram to persist memory across sessions

## The Problem

Sub-agents wake up fresh each session. They lose:
- Context from previous tasks
- Lessons learned from mistakes
- Relationships between related work
- The "why" behind decisions

Current solutions (flat markdown files, raw logs) don't capture the **connections** between memories.

## Engram as Agent Memory

Engram's graph structure maps naturally to how agents should remember:

### 1. Task Memory

When an agent completes a task, store it as a memory node:

```python
from engram import SQLiteBackend, MemoryNode, NodeType

storage = SQLiteBackend("~/.agent/memory.db")
storage.initialize()

# After completing a task
node = MemoryNode(
    type=NodeType.TASK,
    what="Built CLI for Engram project",
    when=datetime.now(),
    who=["main-agent"],  # Which agent did this
    where="engram-cli session",  # Session context
    why="User requested CLI commands",  # The goal
    how="Created Click CLI, wrote tests, updated README",  # Method
    tags=["engram", "cli", "development"],
    artifacts=[
        "/mnt/c/engram/src/cli.py",
        "/mnt/c/engram/tests/test_cli.py",
    ],
)
storage.add_node(node)
```

### 2. Learning from Mistakes

When something goes wrong, store it as an insight:

```python
insight = MemoryNode(
    type=NodeType.INSIGHT,
    what="Rich markup interprets [text] as formatting tags",
    why="Tests failed because [led_to] was parsed as rich markup",
    how="Escape brackets with backslash: \\[text]",
    tags=["python", "rich", "debugging", "gotcha"],
    confidence=1.0,  # High confidence - verified fix
)
storage.add_node(insight)

# Link to the task where we learned this
edge = Edge(
    source_id=task_node.id,
    target_id=insight.id,
    type=EdgeType.LED_TO,
)
storage.add_edge(edge)
```

### 3. Decision Chains

Track why decisions were made:

```python
# Store the decision
decision = MemoryNode(
    type=NodeType.DECISION,
    what="Renamed 'link' command to 'relate' for clarity",
    why="'relate' better describes creating relationships between memories",
    who=["agent"],
    tags=["cli", "api-design", "naming"],
)
storage.add_node(decision)

# Link to what influenced the decision
edge = Edge(
    source_id=user_request.id,  # Previous node with user's task
    target_id=decision.id,
    type=EdgeType.CAUSED_BY,
)
storage.add_edge(edge)
```

### 4. Session Continuity

At session start, load relevant context:

```python
traverser = MemoryTraverser(storage)

# Find recent work on this project
recent = storage.query_by_tags(["engram"], limit=10)

# Find related context (2 hops from recent work)
context = []
for node in recent:
    related = traverser.traverse_bfs(node.id, max_hops=2, include_start=False)
    context.extend(related)

# Now the agent has context about:
# - What was done recently
# - Decisions that were made
# - Lessons learned
# - Connected work
```

## Agent Memory Protocol

### On Session Start

```python
def load_session_context(project_tags: list[str], session_type: str):
    """Load relevant memories for this session."""
    storage = SQLiteBackend("~/.agent/memory.db")
    storage.initialize()
    
    # Recent memories (last 7 days)
    recent = storage.query_by_time(
        since=datetime.now() - timedelta(days=7),
        limit=50
    )
    
    # Project-specific memories
    project = storage.query_by_tags(project_tags, limit=30)
    
    # High-confidence insights (lessons learned)
    insights = [n for n in recent if n.type == NodeType.INSIGHT and n.confidence > 0.8]
    
    return {
        "recent": recent,
        "project": project,
        "insights": insights,
    }
```

### On Task Completion

```python
def record_task_completion(
    what: str,
    how: str,
    artifacts: list[str],
    tags: list[str],
    linked_to: Optional[UUID] = None,
):
    """Record a completed task."""
    node = MemoryNode(
        type=NodeType.TASK,
        what=what,
        how=how,
        artifacts=artifacts,
        tags=tags,
    )
    storage.add_node(node)
    
    if linked_to:
        edge = Edge(
            source_id=linked_to,
            target_id=node.id,
            type=EdgeType.LED_TO,
        )
        storage.add_edge(edge)
    
    return node.id
```

### On Error/Learning

```python
def record_insight(
    what: str,
    how: str,
    context_id: Optional[UUID] = None,
    confidence: float = 0.8,
):
    """Record a lesson learned."""
    insight = MemoryNode(
        type=NodeType.INSIGHT,
        what=what,
        how=how,
        confidence=confidence,
        tags=["insight", "lesson-learned"],
    )
    storage.add_node(insight)
    
    if context_id:
        edge = Edge(
            source_id=context_id,
            target_id=insight.id,
            type=EdgeType.LED_TO,
        )
        storage.add_edge(edge)
```

## OpenClaw Integration

Engram could integrate with OpenClaw's agent system:

### 1. Automatic Memory Capture

Hook into agent lifecycle:
- Task start → create pending memory node
- Task complete → finalize with results
- Error → capture insight

### 2. Context Injection

Before each agent turn:
- Query relevant memories
- Inject into system prompt or context

### 3. Cross-Agent Memory

Multiple agents share the same graph:
- Main agent stores decisions
- Sub-agents store task completions
- Insights propagate between sessions

```yaml
# openclaw.yaml
memory:
  backend: engram
  db_path: ~/.openclaw/memory/engram.db
  context:
    max_hops: 2
    recent_days: 7
    max_nodes: 50
```

## Query Patterns for Agents

### "What did I do with X?"

```python
results = storage.query_by_text("logo design")
context = traverser.traverse_bfs(results[0].id, max_hops=2)
```

### "Why did we decide Y?"

```python
decision = storage.query_by_text("cloud architecture")[0]
causes = traverser.find_related(
    decision.id,
    EdgeType.CAUSED_BY,
    direction="incoming"
)
```

### "What's connected to Z?"

```python
node = storage.get_node(node_id)
context = traverser.traverse_bfs(node.id, max_hops=3)
```

### "What mistakes did I make before?"

```python
insights = storage.query_by_tags(["insight", "gotcha", "debugging"])
```

## Future Directions

1. **Embedding Search** - Semantic similarity for "memories like this"
2. **Memory Decay** - Older, low-impact memories fade
3. **Confidence Updates** - Beliefs get stronger/weaker over time
4. **Multi-Agent Graphs** - Each agent has a subgraph, connected via shared nodes
5. **Memory Tools** - MCP tools for memory operations during agent execution

---

*This document was created while building the Engram CLI - itself an example of task memory that could be stored in Engram.*
