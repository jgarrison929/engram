# Changelog

All notable changes to Engram will be documented in this file.

## [Unreleased]

### Added
- `AgentMemory` class - high-level interface for AI agent integration
  - `load_context()` - Load relevant memories at session start
  - `log_task()`, `log_insight()`, `log_decision()`, `log_event()` - Memory logging
  - `find_related()`, `search()` - Graph queries
  - Auto-linking between related memories
- `engram stats` - Show memory graph statistics
- `engram export` - Export memories to JSON or Markdown
- `engram import-md` - Import markdown files as memories

### Fixed
- Replace deprecated `datetime.utcnow()` with timezone-aware equivalent

## [0.1.0] - 2026-02-10

### 🚀 Initial Release

First public release of Engram - graph-based memory for AI agents.

### Features

- **Core Memory System**
  - 5W+H indexing (who, what, when, where, why, how)
  - SQLite + FTS5 full-text search
  - Typed edges (caused_by, relates_to, supersedes, contradicts, etc.)

- **Graph Traversal**
  - BFS-based context discovery
  - Six degrees of separation pathfinding
  - Configurable hop depth

- **CLI Commands**
  - `engram add` - Create memories with 5W+H metadata
  - `engram query` - Search with text, tags, time filters
  - `engram relate` - Create typed edges between memories
  - `engram show` - Display memory with connections
  - `engram path` - Find connection paths between memories
  - `engram context` - Explore graph around a memory

- **Developer Experience**
  - 47 tests (18 core + 29 CLI)
  - 88% code coverage
  - GitHub Actions CI
  - Full Python API

### Documentation

- Comprehensive README with CLI and API examples
- Full specification in docs/SPEC.md
- Agent memory integration ideas in docs/AGENT-MEMORY.md

### Technical Details

- Python 3.10+
- SQLite with FTS5 extension
- Click-based CLI
- Designed for Postgres+pgvector migration at scale
