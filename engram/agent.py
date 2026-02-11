"""
Agent Memory Integration - Helper functions for AI agents using Engram.

Provides high-level functions for common agent memory patterns:
- Session context loading
- Task completion logging
- Lesson/insight storage
- Decision tracking

Example:
    from engram.agent import AgentMemory
    
    memory = AgentMemory()
    
    # At session start
    context = memory.load_context(tags=["pitbull", "api"])
    
    # After completing work
    memory.log_task(
        what="Added user authentication",
        tags=["auth", "security"],
        artifacts=["src/auth.py"],
    )
    
    # When learning something
    memory.log_insight(
        what="EF Core needs explicit Include() for navigation properties",
        tags=["dotnet", "efcore", "gotcha"],
    )
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID

from engram.core import (
    MemoryNode,
    Edge,
    EdgeType,
    NodeType,
    SQLiteBackend,
)
from engram.query import MemoryTraverser


class AgentMemory:
    """High-level interface for agent memory operations."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize agent memory.
        
        Args:
            db_path: Path to SQLite database. Defaults to ~/.engram/memory.db
        """
        if db_path is None:
            db_path = str(Path.home() / ".engram" / "memory.db")
        
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.storage = SQLiteBackend(db_path)
        self.storage.initialize()
        self.traverser = MemoryTraverser(self.storage)
        self._last_task_id: Optional[UUID] = None
    
    def close(self):
        """Close the database connection."""
        self.storage.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # =========================================================================
    # Context Loading
    # =========================================================================
    
    def load_context(
        self,
        tags: Optional[list[str]] = None,
        days: int = 7,
        max_hops: int = 2,
        limit: int = 20,
    ) -> list[MemoryNode]:
        """Load relevant context for this session.
        
        Args:
            tags: Filter by these tags (optional)
            days: Look back this many days
            max_hops: Traverse this many hops from recent nodes
            limit: Maximum nodes to return
            
        Returns:
            List of relevant memory nodes
        """
        since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        
        # Get recent memories
        if tags:
            recent = self.storage.query_by_tags(tags, limit=limit)
            # Filter by time
            recent = [n for n in recent if n.when and n.when >= since]
        else:
            recent = self.storage.query_by_time(since=since, limit=limit)
        
        if not recent:
            return []
        
        # Expand context via graph traversal
        context_ids = set()
        for node in recent:
            context_ids.add(node.id)
            if max_hops > 0:
                related = self.traverser.traverse_bfs(
                    node.id, max_hops=max_hops, include_start=False
                )
                # traverse_bfs returns QueryResult objects
                context_ids.update(r.node.id for r in related)
        
        # Fetch all nodes
        context = []
        for node_id in context_ids:
            node = self.storage.get_node(node_id)
            if node:
                context.append(node)
        
        # Sort by recency
        context.sort(key=lambda n: n.when or datetime.min, reverse=True)
        return context[:limit]
    
    def get_recent_tasks(self, limit: int = 10) -> list[MemoryNode]:
        """Get recent task completions."""
        all_recent = self.storage.query_by_time(limit=100)
        tasks = [n for n in all_recent if n.type == NodeType.TASK]
        return tasks[:limit]
    
    def get_insights(self, tags: Optional[list[str]] = None, limit: int = 20) -> list[MemoryNode]:
        """Get stored insights/lessons learned."""
        if tags:
            all_nodes = self.storage.query_by_tags(tags, limit=100)
        else:
            all_nodes = self.storage.query_by_time(limit=100)
        
        insights = [n for n in all_nodes if n.type == NodeType.INSIGHT]
        return insights[:limit]
    
    # =========================================================================
    # Memory Logging
    # =========================================================================
    
    def log_task(
        self,
        what: str,
        tags: Optional[list[str]] = None,
        artifacts: Optional[list[str]] = None,
        link_to: Optional[UUID] = None,
        how: Optional[str] = None,
        why: Optional[str] = None,
    ) -> UUID:
        """Log a completed task.
        
        Args:
            what: Description of what was done
            tags: Relevant tags
            artifacts: Files/URLs created or modified
            link_to: Previous node this task relates to
            how: How it was accomplished
            why: Why it was done
            
        Returns:
            ID of the created node
        """
        node = MemoryNode(
            type=NodeType.TASK,
            what=what,
            when=datetime.now(timezone.utc).replace(tzinfo=None),
            tags=tags or [],
            artifacts=artifacts or [],
            how=how,
            why=why,
        )
        
        node_id = self.storage.add_node(node)
        self._last_task_id = node_id
        
        # Link to previous context if provided
        if link_to:
            edge = Edge(
                source_id=link_to,
                target_id=node_id,
                type=EdgeType.LED_TO,
            )
            self.storage.add_edge(edge)
        
        return node_id
    
    def log_insight(
        self,
        what: str,
        tags: Optional[list[str]] = None,
        why: Optional[str] = None,
        how: Optional[str] = None,
        confidence: float = 0.8,
        link_to: Optional[UUID] = None,
    ) -> UUID:
        """Log a lesson learned or insight.
        
        Args:
            what: The insight/lesson
            tags: Relevant tags for retrieval
            why: Why this matters
            how: How to apply this knowledge
            confidence: How confident we are (0-1)
            link_to: Task/event that led to this insight
            
        Returns:
            ID of the created node
        """
        node = MemoryNode(
            type=NodeType.INSIGHT,
            what=what,
            when=datetime.now(timezone.utc).replace(tzinfo=None),
            tags=tags or [],
            why=why,
            how=how,
            confidence=confidence,
        )
        
        node_id = self.storage.add_node(node)
        
        # Link to source if provided
        source = link_to or self._last_task_id
        if source:
            edge = Edge(
                source_id=source,
                target_id=node_id,
                type=EdgeType.LED_TO,
            )
            self.storage.add_edge(edge)
        
        return node_id
    
    def log_decision(
        self,
        what: str,
        why: str,
        alternatives: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
        link_to: Optional[UUID] = None,
    ) -> UUID:
        """Log a decision that was made.
        
        Args:
            what: The decision
            why: Reasoning behind it
            alternatives: Options that were considered
            tags: Relevant tags
            link_to: What caused this decision
            
        Returns:
            ID of the created node
        """
        how = None
        if alternatives:
            how = f"Alternatives considered: {', '.join(alternatives)}"
        
        node = MemoryNode(
            type=NodeType.DECISION,
            what=what,
            when=datetime.now(timezone.utc).replace(tzinfo=None),
            why=why,
            how=how,
            tags=tags or [],
        )
        
        node_id = self.storage.add_node(node)
        
        # Link to cause if provided
        source = link_to or self._last_task_id
        if source:
            edge = Edge(
                source_id=source,
                target_id=node_id,
                type=EdgeType.CAUSED_BY,
            )
            self.storage.add_edge(edge)
        
        return node_id
    
    def log_event(
        self,
        what: str,
        who: Optional[list[str]] = None,
        where: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> UUID:
        """Log an event that happened.
        
        Args:
            what: What happened
            who: People involved
            where: Context/location
            tags: Relevant tags
            
        Returns:
            ID of the created node
        """
        node = MemoryNode(
            type=NodeType.EVENT,
            what=what,
            when=datetime.now(timezone.utc).replace(tzinfo=None),
            who=who or [],
            where=where,
            tags=tags or [],
        )
        
        return self.storage.add_node(node)
    
    # =========================================================================
    # Graph Queries
    # =========================================================================
    
    def find_related(
        self,
        node_id: UUID,
        max_hops: int = 2,
    ) -> list[MemoryNode]:
        """Find memories related to a given node."""
        results = self.traverser.traverse_bfs(node_id, max_hops=max_hops)
        return [r.node for r in results]
    
    def find_path(
        self,
        from_id: UUID,
        to_id: UUID,
    ) -> Optional[list[MemoryNode]]:
        """Find connection path between two memories."""
        return self.traverser.find_path(from_id, to_id)
    
    def search(
        self,
        query: str,
        limit: int = 10,
    ) -> list[MemoryNode]:
        """Full-text search across memories."""
        return self.storage.query_by_text(query, limit=limit)
