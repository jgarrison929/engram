"""
Graph traversal for multi-hop memory queries.

The "six degrees" part - finding related context through edges.
"""

from collections import deque
from typing import Optional
from uuid import UUID

from ..core import StorageBackend, MemoryNode, Edge, EdgeType, QueryResult


class MemoryTraverser:
    """
    Traverse the memory graph to find related context.
    
    Supports BFS/DFS with configurable hop limits and edge filters.
    """
    
    def __init__(self, storage: StorageBackend):
        self.storage = storage
    
    def traverse_bfs(
        self,
        start_id: UUID,
        max_hops: int = 2,
        edge_types: Optional[list[EdgeType]] = None,
        direction: str = "both",
        include_start: bool = True
    ) -> list[QueryResult]:
        """
        Breadth-first traversal from a starting node.
        
        Args:
            start_id: Node to start from
            max_hops: Maximum edges to traverse (default 2)
            edge_types: Filter to specific relationship types
            direction: "outgoing", "incoming", or "both"
            include_start: Whether to include the starting node in results
        
        Returns:
            List of QueryResults with nodes and traversal paths
        """
        visited: set[UUID] = set()
        results: list[QueryResult] = []
        
        # Queue: (node_id, hop_count, path)
        queue: deque[tuple[UUID, int, list[UUID]]] = deque()
        queue.append((start_id, 0, [start_id]))
        
        while queue:
            current_id, hop_count, path = queue.popleft()
            
            if current_id in visited:
                continue
            visited.add(current_id)
            
            # Get the node
            node = self.storage.get_node(current_id)
            if not node:
                continue
            
            # Add to results (skip start node if not wanted)
            if include_start or current_id != start_id:
                results.append(QueryResult(
                    node=node,
                    score=1.0 / (hop_count + 1),  # Closer = higher score
                    path=path,
                    hop_count=hop_count
                ))
            
            # Don't traverse beyond max_hops
            if hop_count >= max_hops:
                continue
            
            # Get edges and continue traversal
            for edge_type in (edge_types or list(EdgeType)):
                edges = self.storage.get_edges(
                    current_id,
                    direction=direction,
                    edge_type=edge_type
                )
                
                for edge in edges:
                    # Determine next node based on direction
                    if edge.source_id == current_id:
                        next_id = edge.target_id
                    else:
                        next_id = edge.source_id
                    
                    if next_id not in visited:
                        queue.append((
                            next_id,
                            hop_count + 1,
                            path + [next_id]
                        ))
        
        return results
    
    def find_path(
        self,
        from_id: UUID,
        to_id: UUID,
        max_hops: int = 6
    ) -> Optional[list[MemoryNode]]:
        """
        Find the shortest path between two nodes.
        
        The "six degrees" query - how are these two memories connected?
        
        Args:
            from_id: Starting node
            to_id: Target node
            max_hops: Maximum path length
        
        Returns:
            List of nodes forming the path, or None if no path exists
        """
        if from_id == to_id:
            node = self.storage.get_node(from_id)
            return [node] if node else None
        
        visited: set[UUID] = set()
        queue: deque[tuple[UUID, list[UUID]]] = deque()
        queue.append((from_id, [from_id]))
        
        while queue:
            current_id, path = queue.popleft()
            
            if len(path) > max_hops + 1:
                continue
            
            if current_id in visited:
                continue
            visited.add(current_id)
            
            # Get all connected nodes
            edges = self.storage.get_edges(current_id)
            
            for edge in edges:
                next_id = edge.target_id if edge.source_id == current_id else edge.source_id
                
                if next_id == to_id:
                    # Found the path!
                    full_path = path + [next_id]
                    return [self.storage.get_node(nid) for nid in full_path]
                
                if next_id not in visited:
                    queue.append((next_id, path + [next_id]))
        
        return None  # No path found
    
    def find_related(
        self,
        node_id: UUID,
        relationship: EdgeType,
        direction: str = "outgoing"
    ) -> list[MemoryNode]:
        """
        Find all nodes with a specific relationship to this node.
        
        Examples:
            - find_related(decision_id, CAUSED_BY) -> what caused this decision?
            - find_related(project_id, PART_OF, "incoming") -> what's part of this project?
        """
        edges = self.storage.get_edges(node_id, direction=direction, edge_type=relationship)
        
        result_ids = set()
        for edge in edges:
            if edge.source_id == node_id:
                result_ids.add(edge.target_id)
            else:
                result_ids.add(edge.source_id)
        
        return [self.storage.get_node(nid) for nid in result_ids if self.storage.get_node(nid)]
    
    def get_context_window(
        self,
        center_id: UUID,
        before: int = 5,
        after: int = 5
    ) -> list[MemoryNode]:
        """
        Get temporal context around a memory.
        
        Returns memories that happened before and after the given node,
        useful for understanding "what was going on at the time."
        """
        center = self.storage.get_node(center_id)
        if not center or not center.when:
            return []
        
        # Get nodes before
        before_nodes = self.storage.query_by_time(
            until=center.when,
            limit=before + 1  # +1 to exclude center
        )
        before_nodes = [n for n in before_nodes if n.id != center_id][:before]
        
        # Get nodes after
        after_nodes = self.storage.query_by_time(
            since=center.when,
            limit=after + 1
        )
        after_nodes = [n for n in after_nodes if n.id != center_id][:after]
        
        # Combine: before (oldest first) + center + after
        before_nodes.reverse()
        return before_nodes + [center] + after_nodes
