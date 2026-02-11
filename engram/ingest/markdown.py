"""
Enhanced Markdown ingestion for Engram.

Parses markdown files with:
- ## headers as memory boundaries
- Date extraction from filenames (YYYY-MM-DD.md)
- Smart node type inference
- Edge creation between related entries
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from engram.core import MemoryNode, Edge, EdgeType, NodeType, SQLiteBackend
from .dedup import content_hash, add_node_with_dedup


def extract_date_from_filename(filepath: Path) -> Optional[datetime]:
    """
    Extract date from filename if it matches YYYY-MM-DD pattern.
    
    Supports:
    - 2026-02-10.md
    - 2026-02-10-notes.md
    - session-2026-02-10.md
    """
    name = filepath.stem
    
    # Try patterns
    patterns = [
        r"(\d{4}-\d{2}-\d{2})",  # YYYY-MM-DD anywhere
        r"(\d{4}_\d{2}_\d{2})",  # YYYY_MM_DD
        r"(\d{8})",              # YYYYMMDD
    ]
    
    for pattern in patterns:
        match = re.search(pattern, name)
        if match:
            date_str = match.group(1)
            try:
                if "-" in date_str:
                    return datetime.strptime(date_str, "%Y-%m-%d")
                elif "_" in date_str:
                    return datetime.strptime(date_str, "%Y_%m_%d")
                else:
                    return datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                continue
    
    return None


def infer_node_type(header: str, content: str) -> NodeType:
    """
    Infer node type from header and content.
    """
    header_lower = header.lower()
    content_lower = content.lower()
    
    # Decision indicators
    if any(w in header_lower for w in ["decision", "decided", "chose", "approved"]):
        return NodeType.DECISION
    
    # Insight/Lesson indicators
    if any(w in header_lower for w in ["lesson", "learned", "insight", "realization", "til"]):
        return NodeType.INSIGHT
    
    # Task/Todo indicators
    if any(w in header_lower for w in ["todo", "task", "action item", "next step"]):
        return NodeType.TASK
    
    # Project indicators
    if any(w in header_lower for w in ["project", "module", "feature", "milestone"]):
        return NodeType.PROJECT
    
    # Person indicators
    if any(w in header_lower for w in ["person", "contact", "team member"]):
        return NodeType.PERSON
    
    # Conversation indicators
    if any(w in header_lower for w in ["meeting", "call", "chat", "discussion"]):
        return NodeType.CONVERSATION
    
    # Artifact indicators
    if any(w in header_lower for w in ["created", "built", "deployed", "released", "artifact"]):
        return NodeType.ARTIFACT
    
    # Content-based inference
    if "- [ ]" in content or "- [x]" in content:
        return NodeType.TASK
    
    return NodeType.EVENT


def extract_tags(header: str, content: str) -> list[str]:
    """
    Extract tags from header and content.
    """
    tags = set()
    
    # Header words (excluding common words)
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with"}
    header_words = re.findall(r"\w+", header.lower())
    tags.update(w for w in header_words if len(w) > 2 and w not in stop_words)
    
    # Explicit hashtags in content
    hashtags = re.findall(r"#(\w+)", content)
    tags.update(h.lower() for h in hashtags)
    
    # Common topic detection
    content_lower = content.lower()
    topic_keywords = {
        "bug": ["bug", "fix", "error", "issue"],
        "feature": ["feature", "implement", "add", "create"],
        "test": ["test", "coverage", "spec"],
        "deploy": ["deploy", "release", "production"],
        "docs": ["document", "readme", "changelog"],
        "refactor": ["refactor", "cleanup", "reorganize"],
        "security": ["security", "auth", "permission"],
        "performance": ["performance", "optimize", "speed"],
    }
    
    for tag, keywords in topic_keywords.items():
        if any(kw in content_lower for kw in keywords):
            tags.add(tag)
    
    return list(tags)[:10]  # Limit tags


def extract_people(content: str) -> list[str]:
    """
    Extract people mentioned in content.
    
    Looks for:
    - @mentions
    - "Josh said", "River created"
    - Explicit names after patterns like "by", "from", "with"
    """
    people = set()
    
    # @mentions
    mentions = re.findall(r"@(\w+)", content)
    people.update(mentions)
    
    # Common patterns
    patterns = [
        r"(?:by|from|with)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
        r"([A-Z][a-z]+)\s+(?:said|created|built|deployed|fixed|added|reviewed)",
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, content)
        people.update(matches)
    
    return list(people)[:5]  # Limit people


def parse_markdown_sections(content: str) -> list[tuple[str, str]]:
    """
    Split markdown content into (header, body) tuples based on ## headers.
    """
    sections = []
    
    # Split by ## headers (keep ###, #### as part of body)
    parts = re.split(r"^## ", content, flags=re.MULTILINE)
    
    for part in parts[1:]:  # Skip content before first ##
        if not part.strip():
            continue
        
        lines = part.strip().split("\n")
        header = lines[0].strip()
        body = "\n".join(lines[1:]).strip()
        
        if body:  # Only include sections with content
            sections.append((header, body))
    
    return sections


def import_markdown_file(
    storage: SQLiteBackend,
    filepath: Path,
    extra_tags: Optional[list[str]] = None,
    dry_run: bool = False,
) -> dict:
    """
    Import a single markdown file into Engram.
    
    Args:
        storage: SQLite backend
        filepath: Path to markdown file
        extra_tags: Additional tags to add to all nodes
        dry_run: Preview without saving
    
    Returns:
        Statistics dict
    """
    stats = {
        "sections_found": 0,
        "nodes_created": 0,
        "nodes_skipped": 0,
    }
    
    filepath = Path(filepath)
    content = filepath.read_text(encoding="utf-8")
    
    # Extract date from filename
    file_date = extract_date_from_filename(filepath)
    
    # Parse sections
    sections = parse_markdown_sections(content)
    stats["sections_found"] = len(sections)
    
    if dry_run:
        return stats
    
    extra_tags = extra_tags or []
    
    for header, body in sections:
        # Build node
        node_type = infer_node_type(header, body)
        tags = extract_tags(header, body)
        tags.extend(extra_tags)
        tags = list(set(tags))
        
        people = extract_people(body)
        
        # Use file date if available, else now
        when = file_date or datetime.now()
        
        node = MemoryNode(
            type=node_type,
            what=f"{header}\n\n{body}",
            when=when,
            who=people,
            tags=tags,
            source=f"md:{filepath.name}",
        )
        
        # Dedup hash
        hash_val = content_hash(node.what, str(node.when), node.source)
        
        # Add with dedup
        node_id, was_new = add_node_with_dedup(storage, node, hash_val)
        
        if was_new:
            stats["nodes_created"] += 1
        else:
            stats["nodes_skipped"] += 1
    
    return stats


def import_markdown_dir(
    storage: SQLiteBackend,
    dir_path: Path,
    pattern: str = "*.md",
    extra_tags: Optional[list[str]] = None,
    link_by_date: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Import all markdown files from a directory.
    
    Args:
        storage: SQLite backend
        dir_path: Directory path
        pattern: Glob pattern for files
        extra_tags: Additional tags for all nodes
        link_by_date: Create edges between nodes from same date
        dry_run: Preview without saving
    
    Returns:
        Aggregate statistics
    """
    dir_path = Path(dir_path)
    files = sorted(dir_path.glob(pattern))
    
    stats = {
        "files_processed": 0,
        "sections_found": 0,
        "nodes_created": 0,
        "nodes_skipped": 0,
        "edges_created": 0,
    }
    
    # Track nodes by date for linking
    nodes_by_date: dict[str, list[UUID]] = {}
    
    for filepath in files:
        file_stats = import_markdown_file(
            storage, filepath, extra_tags, dry_run=dry_run
        )
        
        stats["files_processed"] += 1
        stats["sections_found"] += file_stats["sections_found"]
        stats["nodes_created"] += file_stats["nodes_created"]
        stats["nodes_skipped"] += file_stats["nodes_skipped"]
        
        # Track date for linking
        if link_by_date and not dry_run:
            file_date = extract_date_from_filename(filepath)
            if file_date:
                date_key = file_date.strftime("%Y-%m-%d")
                if date_key not in nodes_by_date:
                    nodes_by_date[date_key] = []
                
                # Get recently created nodes (simple heuristic)
                recent = storage.query_by_time(limit=file_stats["nodes_created"])
                nodes_by_date[date_key].extend(n.id for n in recent)
    
    # Create edges between nodes from same date
    if link_by_date and not dry_run:
        for date_key, node_ids in nodes_by_date.items():
            # Create sequential edges (temporal ordering)
            unique_ids = list(dict.fromkeys(node_ids))  # Preserve order, remove dupes
            for i in range(len(unique_ids) - 1):
                edge = Edge(
                    source_id=unique_ids[i],
                    target_id=unique_ids[i + 1],
                    type=EdgeType.PRECEDED_BY,
                    metadata={"date": date_key},
                )
                storage.add_edge(edge)
                stats["edges_created"] += 1
    
    return stats
