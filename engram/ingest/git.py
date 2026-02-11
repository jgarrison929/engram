"""
Git commit ingestion for Engram.

Scans git log and creates memory nodes for significant commits.
"""

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from engram.core import MemoryNode, Edge, EdgeType, NodeType, SQLiteBackend
from .dedup import content_hash, add_node_with_dedup


@dataclass
class CommitFilter:
    """Configuration for filtering git commits."""
    
    # Skip these commit types
    skip_merge: bool = True
    skip_trivial: bool = True
    
    # Trivial patterns (commit messages to skip)
    trivial_patterns: list[str] = field(default_factory=lambda: [
        r"^Merge (branch|pull request)",
        r"^WIP",
        r"^wip",
        r"^fixup!",
        r"^squash!",
        r"^chore: Update.*lock",
        r"^chore: Bump version",
    ])
    
    # Significant patterns (always include)
    significant_patterns: list[str] = field(default_factory=lambda: [
        r"^feat:",
        r"^fix:",
        r"^refactor:",
        r"^perf:",
        r"^security:",
        r"^BREAKING CHANGE",
    ])
    
    # File patterns that make a commit significant
    significant_files: list[str] = field(default_factory=lambda: [
        r"README\.md",
        r"CHANGELOG\.md",
        r"\.env",
        r"Dockerfile",
        r"docker-compose",
        r"\.github/workflows/",
    ])
    
    # Maximum commits to process (0 = unlimited)
    max_commits: int = 0
    
    # Only include commits since this date
    since: Optional[datetime] = None
    
    # Only include commits until this date
    until: Optional[datetime] = None


@dataclass
class GitCommit:
    """Parsed git commit data."""
    hash: str
    author: str
    date: datetime
    message: str
    files: list[str]
    
    @property
    def short_hash(self) -> str:
        return self.hash[:7]
    
    @property
    def commit_type(self) -> Optional[str]:
        """Extract conventional commit type (feat, fix, etc.)."""
        match = re.match(r"^(\w+)(?:\([^)]+\))?:", self.message)
        return match.group(1) if match else None


def parse_git_log(repo_path: Path, filter_config: CommitFilter) -> list[GitCommit]:
    """
    Parse git log from a repository.
    
    Returns list of GitCommit objects.
    """
    cmd = [
        "git", "-C", str(repo_path),
        "log",
        "--format=%H|%an|%ai|%s",
        "--name-only",
    ]
    
    if filter_config.since:
        cmd.append(f"--since={filter_config.since.isoformat()}")
    if filter_config.until:
        cmd.append(f"--until={filter_config.until.isoformat()}")
    if filter_config.max_commits > 0:
        cmd.append(f"-n{filter_config.max_commits * 2}")  # Over-fetch to account for filtering
    
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    
    commits = []
    current_commit = None
    
    for line in result.stdout.strip().split("\n"):
        if not line:
            # Empty line separates commits
            if current_commit:
                commits.append(current_commit)
            current_commit = None
            continue
        
        if "|" in line and len(line.split("|")) == 4:
            # New commit line
            if current_commit:
                commits.append(current_commit)
            
            parts = line.split("|")
            commit_hash, author, date_str, message = parts
            
            # Parse date
            try:
                commit_date = datetime.fromisoformat(date_str.replace(" -", "-").replace(" +", "+"))
                commit_date = commit_date.replace(tzinfo=None)  # Strip timezone for consistency
            except ValueError:
                commit_date = datetime.now()
            
            current_commit = GitCommit(
                hash=commit_hash,
                author=author,
                date=commit_date,
                message=message,
                files=[],
            )
        elif current_commit and line.strip():
            # File name
            current_commit.files.append(line.strip())
    
    # Don't forget the last commit
    if current_commit:
        commits.append(current_commit)
    
    return commits


def is_significant(commit: GitCommit, filter_config: CommitFilter) -> bool:
    """
    Determine if a commit is significant enough to import.
    """
    message = commit.message
    
    # Always skip merge commits if configured
    if filter_config.skip_merge and message.startswith("Merge"):
        return False
    
    # Check trivial patterns
    if filter_config.skip_trivial:
        for pattern in filter_config.trivial_patterns:
            if re.match(pattern, message, re.IGNORECASE):
                return False
    
    # Check significant patterns - always include
    for pattern in filter_config.significant_patterns:
        if re.match(pattern, message, re.IGNORECASE):
            return True
    
    # Check significant files
    for file in commit.files:
        for pattern in filter_config.significant_files:
            if re.search(pattern, file):
                return True
    
    # Default: include if not filtered out
    return True


def commit_to_node(commit: GitCommit, repo_name: str) -> MemoryNode:
    """
    Convert a GitCommit to a MemoryNode.
    """
    # Determine node type from conventional commit prefix
    commit_type = commit.commit_type
    
    if commit_type in ("feat", "feature"):
        node_type = NodeType.ARTIFACT
    elif commit_type in ("fix", "bugfix"):
        node_type = NodeType.EVENT
    elif commit_type in ("refactor", "perf"):
        node_type = NodeType.ARTIFACT
    elif commit_type in ("docs", "doc"):
        node_type = NodeType.ARTIFACT
    elif commit_type in ("test", "tests"):
        node_type = NodeType.ARTIFACT
    elif commit_type == "decision":
        node_type = NodeType.DECISION
    else:
        node_type = NodeType.EVENT
    
    # Build tags from commit type, repo, and file types
    tags = [repo_name]
    if commit_type:
        tags.append(commit_type)
    
    # Add file-based tags
    file_types = set()
    for file in commit.files:
        if file.endswith(".py"):
            file_types.add("python")
        elif file.endswith((".js", ".ts")):
            file_types.add("javascript")
        elif file.endswith((".cs", ".csproj")):
            file_types.add("csharp")
        elif file.endswith(".md"):
            file_types.add("docs")
        elif file.endswith((".yml", ".yaml")):
            file_types.add("ci")
        elif "test" in file.lower():
            file_types.add("testing")
    tags.extend(file_types)
    
    # Build what/how fields
    what = commit.message
    how = ", ".join(commit.files[:5])
    if len(commit.files) > 5:
        how += f" (+{len(commit.files) - 5} more)"
    
    return MemoryNode(
        type=node_type,
        what=what,
        when=commit.date,
        who=[commit.author],
        how=how,
        tags=list(set(tags)),
        source=f"git:{repo_name}:{commit.short_hash}",
    )


def import_git_repo(
    storage: SQLiteBackend,
    repo_path: Path,
    filter_config: Optional[CommitFilter] = None,
    link_related: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Import git commits from a repository into Engram.
    
    Args:
        storage: SQLite backend to store nodes
        repo_path: Path to git repository
        filter_config: Filtering configuration
        link_related: Create edges between commits that touch same files
        dry_run: Preview without saving
    
    Returns:
        Statistics dict with counts
    """
    if filter_config is None:
        filter_config = CommitFilter()
    
    repo_name = repo_path.name
    
    # Parse commits
    all_commits = parse_git_log(repo_path, filter_config)
    
    # Filter to significant commits
    significant = [c for c in all_commits if is_significant(c, filter_config)]
    
    # Apply max limit
    if filter_config.max_commits > 0:
        significant = significant[:filter_config.max_commits]
    
    stats = {
        "total_commits": len(all_commits),
        "significant_commits": len(significant),
        "nodes_created": 0,
        "nodes_skipped": 0,
        "edges_created": 0,
    }
    
    if dry_run:
        return stats
    
    # Track created nodes and their files for linking
    nodes_by_hash: dict[str, UUID] = {}
    files_to_nodes: dict[str, list[UUID]] = {}
    
    for commit in significant:
        node = commit_to_node(commit, repo_name)
        
        # Generate content hash for dedup
        hash_val = content_hash(node.what, str(node.when), node.source)
        
        # Add with deduplication
        node_id, was_new = add_node_with_dedup(storage, node, hash_val)
        
        if was_new:
            stats["nodes_created"] += 1
            nodes_by_hash[commit.hash] = node_id
            
            # Track files for linking
            for file in commit.files:
                if file not in files_to_nodes:
                    files_to_nodes[file] = []
                files_to_nodes[file].append(node_id)
        else:
            stats["nodes_skipped"] += 1
    
    # Create edges between related commits (same files)
    if link_related:
        created_edges = set()
        for file, node_ids in files_to_nodes.items():
            # Link nodes that touched the same file
            for i, source_id in enumerate(node_ids):
                for target_id in node_ids[i+1:]:
                    edge_key = (min(str(source_id), str(target_id)), 
                               max(str(source_id), str(target_id)))
                    if edge_key not in created_edges:
                        edge = Edge(
                            source_id=source_id,
                            target_id=target_id,
                            type=EdgeType.RELATES_TO,
                            metadata={"shared_file": file},
                        )
                        storage.add_edge(edge)
                        created_edges.add(edge_key)
                        stats["edges_created"] += 1
    
    return stats
