"""Tests for graph traversal."""

import pytest
from datetime import datetime, timedelta

from engram.core import (
    MemoryNode,
    Edge,
    EdgeType,
    NodeType,
    SQLiteBackend,
)
from engram.query import MemoryTraverser


@pytest.fixture
def storage(tmp_path):
    """Create a temporary SQLite storage."""
    db_path = tmp_path / "test.db"
    backend = SQLiteBackend(str(db_path))
    backend.initialize()
    yield backend
    backend.close()


@pytest.fixture
def traverser(storage):
    """Create a traverser with the test storage."""
    return MemoryTraverser(storage)


@pytest.fixture
def logo_graph(storage):
    """
    Create a test graph representing logo development:
    
    request -> v1 -> feedback -> v2 -> decision -> deploy
                         |
                         v
                       v3 (rejected)
    """
    nodes = {}
    
    nodes['request'] = MemoryNode(
        type=NodeType.CONVERSATION,
        what="Josh asked for a logo",
        when=datetime(2026, 2, 10, 0, 0),
        who=["Josh"],
        tags=["logo", "request"],
    )
    
    nodes['v1'] = MemoryNode(
        type=NodeType.ARTIFACT,
        what="First logo draft - cartoon pitbull",
        when=datetime(2026, 2, 10, 1, 0),
        tags=["logo", "v1", "draft"],
        artifacts=["/path/to/v1.png"],
    )
    
    nodes['feedback'] = MemoryNode(
        type=NodeType.CONVERSATION,
        what="Josh said 'looks sad, needs to be confident'",
        when=datetime(2026, 2, 10, 1, 30),
        who=["Josh"],
        tags=["logo", "feedback"],
    )
    
    nodes['v2'] = MemoryNode(
        type=NodeType.ARTIFACT,
        what="Line art pitbull with hard hat",
        when=datetime(2026, 2, 10, 2, 0),
        tags=["logo", "v2", "draft"],
        artifacts=["/path/to/v2.png"],
    )
    
    nodes['v3'] = MemoryNode(
        type=NodeType.ARTIFACT,
        what="Shield emblem style - rejected",
        when=datetime(2026, 2, 10, 2, 15),
        tags=["logo", "v3", "draft", "rejected"],
        artifacts=["/path/to/v3.png"],
    )
    
    nodes['decision'] = MemoryNode(
        type=NodeType.DECISION,
        what="Chose line art version (v2)",
        when=datetime(2026, 2, 10, 2, 30),
        who=["Josh", "River"],
        why="More professional, confident expression",
        tags=["logo", "decision"],
    )
    
    nodes['deploy'] = MemoryNode(
        type=NodeType.EVENT,
        what="Deployed logo to website",
        when=datetime(2026, 2, 10, 3, 0),
        tags=["logo", "deploy", "website"],
        artifacts=["https://pitbullconstructionsolutions.com"],
    )
    
    # Add all nodes
    for key, node in nodes.items():
        storage.add_node(node)
    
    # Create edges
    edges = [
        (nodes['request'].id, nodes['v1'].id, EdgeType.LED_TO),
        (nodes['v1'].id, nodes['feedback'].id, EdgeType.LED_TO),
        (nodes['feedback'].id, nodes['v2'].id, EdgeType.LED_TO),
        (nodes['feedback'].id, nodes['v3'].id, EdgeType.LED_TO),
        (nodes['v2'].id, nodes['decision'].id, EdgeType.LED_TO),
        (nodes['decision'].id, nodes['deploy'].id, EdgeType.LED_TO),
        (nodes['v3'].id, nodes['decision'].id, EdgeType.RELATES_TO),  # Considered but rejected
    ]
    
    for source_id, target_id, edge_type in edges:
        storage.add_edge(Edge(
            source_id=source_id,
            target_id=target_id,
            type=edge_type,
        ))
    
    return nodes


class TestTraversal:
    """Tests for BFS traversal."""
    
    def test_traverse_one_hop(self, traverser, logo_graph):
        results = traverser.traverse_bfs(
            logo_graph['feedback'].id,
            max_hops=1,
            include_start=False,
        )
        
        # Should find v1, v2, v3 (all connected to feedback)
        whats = [r.node.what for r in results]
        assert len(results) == 3
        assert any("cartoon pitbull" in w for w in whats)  # v1
        assert any("Line art" in w for w in whats)  # v2
        assert any("Shield emblem" in w for w in whats)  # v3
    
    def test_traverse_two_hops(self, traverser, logo_graph):
        results = traverser.traverse_bfs(
            logo_graph['request'].id,
            max_hops=2,
            include_start=False,
        )
        
        # Should find v1 (1 hop) and feedback (2 hops)
        whats = [r.node.what for r in results]
        assert any("cartoon pitbull" in w for w in whats)
        assert any("looks sad" in w for w in whats)
    
    def test_traverse_full_graph(self, traverser, logo_graph):
        results = traverser.traverse_bfs(
            logo_graph['request'].id,
            max_hops=6,
            include_start=True,
        )
        
        # Should find all 7 nodes
        assert len(results) == 7


class TestFindPath:
    """Tests for path finding."""
    
    def test_find_direct_path(self, traverser, logo_graph):
        path = traverser.find_path(
            logo_graph['v1'].id,
            logo_graph['feedback'].id,
        )
        
        assert path is not None
        assert len(path) == 2
        assert path[0].id == logo_graph['v1'].id
        assert path[1].id == logo_graph['feedback'].id
    
    def test_find_multi_hop_path(self, traverser, logo_graph):
        path = traverser.find_path(
            logo_graph['request'].id,
            logo_graph['deploy'].id,
        )
        
        assert path is not None
        # request -> v1 -> feedback -> v2 -> decision -> deploy = 6 nodes
        assert len(path) == 6
        assert path[0].what == "Josh asked for a logo"
        assert path[-1].what == "Deployed logo to website"
    
    def test_no_path_exists(self, storage, traverser):
        # Create two disconnected nodes
        n1 = MemoryNode(what="Island 1")
        n2 = MemoryNode(what="Island 2")
        storage.add_node(n1)
        storage.add_node(n2)
        
        path = traverser.find_path(n1.id, n2.id)
        
        assert path is None


class TestFindRelated:
    """Tests for relationship queries."""
    
    def test_find_what_led_to(self, traverser, logo_graph):
        # What led to the decision?
        related = traverser.find_related(
            logo_graph['decision'].id,
            EdgeType.LED_TO,
            direction="incoming",
        )
        
        # v2 led to decision
        assert len(related) == 1
        assert "Line art" in related[0].what
    
    def test_find_what_it_led_to(self, traverser, logo_graph):
        # What did feedback lead to?
        related = traverser.find_related(
            logo_graph['feedback'].id,
            EdgeType.LED_TO,
            direction="outgoing",
        )
        
        # Feedback led to v2 and v3
        assert len(related) == 2


class TestContextWindow:
    """Tests for temporal context."""
    
    def test_get_context_around_event(self, traverser, logo_graph):
        # Get context around the feedback moment
        context = traverser.get_context_window(
            logo_graph['feedback'].id,
            before=2,
            after=2,
        )
        
        # Should have: request, v1, feedback, v2, v3 (or similar based on timing)
        assert len(context) >= 3
        
        # Feedback should be in the middle-ish
        whats = [n.what for n in context]
        assert any("looks sad" in w for w in whats)
