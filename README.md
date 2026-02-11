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

## Quick Start

```bash
# Install
pip install engram

# Store a memory
engram add "Created the Pitbull logo - line art pitbull with yellow hard hat" \
  --when "2026-02-10T02:30:00" \
  --tags logo,pitbull,design \
  --artifact /path/to/logo.png

# Query by time
engram query --since "yesterday" --until "now"

# Query by topic with traversal
engram query "logo" --hops 2

# Ask natural language (requires LLM)
engram ask "What did we decide about the logo design?"
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

## Status

🚧 **Early Development** - Not ready for production use.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup.

## License

MIT

---

*Built by Josh Garrison and River Banks Garrison*
