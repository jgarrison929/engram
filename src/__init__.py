"""
Engram - Graph-based memory for AI agents.

5W+H indexed nodes, typed edges, multi-hop traversal.
"""

from .core import (
    MemoryNode,
    Edge,
    EdgeType,
    NodeType,
    QueryResult,
    StorageBackend,
    SQLiteBackend,
)
from .query import MemoryTraverser
from .agent import AgentMemory

__version__ = "0.1.0"

__all__ = [
    "MemoryNode",
    "Edge",
    "EdgeType",
    "NodeType",
    "QueryResult",
    "StorageBackend",
    "SQLiteBackend",
    "MemoryTraverser",
    "AgentMemory",
    "__version__",
]
