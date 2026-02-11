"""
Deduplication for Engram ingestion.

Prevents duplicate nodes when re-running imports by using content hashes.
"""

import hashlib
from typing import Optional
from uuid import UUID

from engram.core import SQLiteBackend, MemoryNode


def content_hash(what: str, when: Optional[str] = None, source: Optional[str] = None) -> str:
    """
    Generate a content hash for deduplication.
    
    The hash is based on:
    - what: The main content
    - when: Timestamp (if available)
    - source: Source identifier (e.g., "git:abc123" or "md:file.md")
    
    Returns a hex string that can be used to detect duplicates.
    """
    parts = [what.strip()]
    if when:
        parts.append(str(when))
    if source:
        parts.append(source)
    
    content = "|".join(parts)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def check_duplicate(storage: SQLiteBackend, content_hash_value: str) -> Optional[UUID]:
    """
    Check if a memory with this content hash already exists.
    
    Returns the node ID if found, None otherwise.
    
    We store the content hash in the node's `source` field with a "hash:" prefix.
    """
    # Query nodes that might be duplicates
    # We use a convention: source field contains "hash:{hash}" 
    cursor = storage.conn.execute(
        "SELECT id FROM nodes WHERE source LIKE ?",
        (f"%hash:{content_hash_value}%",)
    )
    row = cursor.fetchone()
    return UUID(row['id']) if row else None


def add_node_with_dedup(
    storage: SQLiteBackend,
    node: MemoryNode,
    hash_value: Optional[str] = None
) -> tuple[UUID, bool]:
    """
    Add a node with deduplication.
    
    If hash_value is provided, checks for existing node first.
    Updates the node's source field to include the hash.
    
    Returns (node_id, was_new) tuple.
    """
    if hash_value:
        existing = check_duplicate(storage, hash_value)
        if existing:
            return existing, False
        
        # Add hash to source
        if node.source:
            node.source = f"{node.source} hash:{hash_value}"
        else:
            node.source = f"hash:{hash_value}"
    
    node_id = storage.add_node(node)
    return node_id, True
