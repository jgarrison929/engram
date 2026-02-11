# Engram

> Graph-based memory for AI agents. Remember what happened, when, why, and how it connects.

## The Problem

Current AI memory is flat text files and semantic search. That works for "what's Josh's email?" but fails for:
- "Walk me through the logo evolution"
- "Why did we choose this approach?"
- "What were we working on last Tuesday?"
- "Show me everything related to the job search"

## The Solution

**Engram** stores memories as a graph with:
- **5W+H indexed nodes** - What, When, Where, Who, Why, How
- **Typed edges** - caused_by, led_to, supersedes, contradicts, relates_to
- **Multi-hop traversal** - "Six degrees" style context discovery
- **Temporal queries** - Time-based retrieval built in
- **Artifact linking** - Connect memories to files, images, URLs

## Installation

```bash
# Install with CLI support
pip install engram[cli]

# Or install everything
pip install engram[all]
```

## CLI Usage

### Adding Memories

```bash
# Basic memory
engram add "Deployed the new website"

# With full 5W+H metadata
engram add "Decided to use cloud-only architecture" \
  --when "2026-02-10 14:30" \
  --who Josh \
  --who River \
  --where "Architecture meeting" \
  --why "Avoid on-prem deployment complexity" \
  --how "Team discussion and vote" \
  --tags architecture,decision,cloud \
  --type decision

# With artifact links
engram add "Created the Pitbull logo" \
  --tags logo,design \
  --artifact /path/to/logo.png \
  --artifact https://example.com/design-doc
```

### Querying Memories

```bash
# Full-text search
engram query "logo"

# Search with traversal (follow connected memories)
engram query "logo" --hops 2

# Time-based queries
engram query --since yesterday
engram query --since "2 hours ago" --until now
engram query --since "2026-02-01" --until "2026-02-10"

# Filter by tags
engram query --tags design,logo

# JSON output for scripting
engram query "logo" --json
```

### Viewing Memory Details

```bash
# Show a specific memory (full UUID or prefix)
engram show abc12345

# Shows all 5W+H fields plus connections to other memories
```

### Creating Relationships

```bash
# Connect two memories with a relationship
engram relate <source-id> <target-id> --type led_to

# Relationship types:
#   caused_by    - X was caused by Y
#   led_to       - X led to Y
#   supersedes   - X replaces Y (newer version)
#   preceded_by  - X came after Y
#   relates_to   - General association (default)
#   contradicts  - X conflicts with Y
#   supports     - X reinforces Y
#   mentions     - X references Y
#   part_of      - X is a component of Y
#   derived_from - X was created from Y
```

### Finding Paths (Six Degrees)

```bash
# Find how two memories are connected
engram path <from-id> <to-id>

# Limit path length
engram path <from-id> <to-id> --max-hops 4
```

### Context Exploration

```bash
# See the graph around a memory
engram context <id> --hops 2
```

### Importing History

```bash
# Import git commits from a repository
engram import-git /path/to/repo
engram import-git . --limit 100  # Current dir, last 100 commits

# Import markdown files from a directory
engram import-md-dir /path/to/notes
engram import-md-dir ./memory --dry-run  # Preview without importing

# Features:
# - Deduplication (re-running skips existing nodes)
# - Auto-tagging by commit type (feat, fix, docs)
# - Links related commits touching same files
# - Extracts dates from YYYY-MM-DD.md filenames
# - Parses ## headers as memory boundaries
```

### Statistics

```bash
# View memory graph statistics
engram stats

# Shows: node counts by type, edge counts, date range, most connected nodes
```

## Python API

### Agent Memory (High-Level)

For AI agents, use the `AgentMemory` helper class:

```python
from engram import AgentMemory

# Initialize
memory = AgentMemory()  # Uses ~/.engram/memory.db by default

# At session start - load relevant context
context = memory.load_context(tags=["project-x"], days=7, max_hops=2)

# Log completed tasks
memory.log_task(
    what="Implemented user authentication",
    tags=["auth", "backend"],
    artifacts=["src/auth.py", "tests/test_auth.py"],
)

# Store lessons learned (auto-links to last task)
memory.log_insight(
    what="Always hash passwords with bcrypt, not SHA256",
    tags=["security", "passwords"],
    why="SHA256 is too fast for password hashing",
)

# Track decisions with reasoning
memory.log_decision(
    what="Use PostgreSQL for production",
    why="Better JSON support and proven scalability",
    alternatives=["MySQL", "SQLite"],
    tags=["database", "architecture"],
)

# Search and traverse
results = memory.search("authentication")
related = memory.find_related(node_id, max_hops=2)

# Clean up
memory.close()

# Or use as context manager
with AgentMemory() as memory:
    memory.log_event("Session started", tags=["session"])
```

### Low-Level API

For more control, use the storage and traversal APIs directly:

```python
from engram import SQLiteBackend, MemoryNode, Edge, EdgeType, MemoryTraverser

# Initialize storage
storage = SQLiteBackend("memory.db")
storage.initialize()

# Create a memory
node = MemoryNode(
    what="Decided on cloud architecture",
    who=["Josh", "River"],
    why="Simpler deployment",
    tags=["architecture", "decision"],
)
storage.add_node(node)

# Query memories
results = storage.query_by_text("architecture")
recent = storage.query_by_time(since=datetime.now() - timedelta(days=7))

# Create relationships
edge = Edge(
    source_id=node1.id,
    target_id=node2.id,
    type=EdgeType.LED_TO,
)
storage.add_edge(edge)

# Traverse the graph
traverser = MemoryTraverser(storage)
context = traverser.traverse_bfs(node.id, max_hops=2)
path = traverser.find_path(from_id, to_id)
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Integrations                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ OpenClaw │  │   MCP    │  │  CLI / Python    │  │
│  │  Plugin  │  │  Server  │  │      API         │  │
│  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
└───────┼─────────────┼─────────────────┼────────────┘
        │             │                 │
┌───────▼─────────────▼─────────────────▼────────────┐
│                   Query Layer                       │
│  • Traversal (BFS/DFS, hop limits)                 │
│  • Temporal (since/until, ranges)                  │
│  • Semantic (embedding search)                     │
│  • Structured (tags, types, who/what/where)        │
└───────────────────────┬────────────────────────────┘
                        │
┌───────────────────────▼────────────────────────────┐
│                   Core Layer                        │
│  • MemoryNode (5W+H schema)                        │
│  • Edge (typed relationships)                      │
│  • Storage backends (SQLite, Postgres, Neo4j)      │
└────────────────────────────────────────────────────┘
```

## Memory Types

- `event` - Something that happened (default)
- `decision` - A choice that was made
- `artifact` - A thing that was created
- `conversation` - A discussion
- `insight` - A realization or lesson learned
- `person` - A person reference
- `project` - A project reference
- `task` - A to-do or action item

## Status

🚧 **Early Development** - Core functionality works, API may change.

- ✅ SQLite storage with FTS5 full-text search
- ✅ 5W+H indexed memory nodes
- ✅ Typed edges and relationships
- ✅ BFS graph traversal
- ✅ CLI with add/query/show/relate/path/context/stats
- ✅ Git commit import (import-git)
- ✅ Markdown directory import (import-md-dir)
- ✅ Deduplication via content hashing
- ⏳ Semantic search with embeddings
- ⏳ PostgreSQL backend
- ⏳ Neo4j backend
- ⏳ OpenClaw integration
- ⏳ MCP server

## Contributing

```bash
# Clone and install
git clone https://github.com/jgarrison929/engram.git
cd engram
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src
```

## License

MIT

---

*Built by Josh Garrison and River Banks Garrison*
