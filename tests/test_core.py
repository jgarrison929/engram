"""Tests for core memory models and storage."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.core import (
    MemoryNode,
    Edge,
    EdgeType,
    NodeType,
    SQLiteBackend,
)


@pytest.fixture
def storage(tmp_path):
    """Create a temporary SQLite storage."""
    db_path = tmp_path / "test.db"
    backend = SQLiteBackend(str(db_path))
    backend.initialize()
    yield backend
    backend.close()


class TestMemoryNode:
    """Tests for MemoryNode dataclass."""
    
    def test_create_minimal(self):
        node = MemoryNode(what="Something happened")
        assert node.what == "Something happened"
        assert node.id is not None
        assert node.type == NodeType.EVENT
    
    def test_create_full(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        node = MemoryNode(
            type=NodeType.DECISION,
            what="Chose line art for logo",
            when=now,
            where="Telegram chat",
            who=["Josh", "River"],
            why="More professional look",
            how="Generated 30+ variations, narrowed down",
            tags=["logo", "design", "pitbull"],
            artifacts=["/path/to/logo.png"],
            confidence=0.95,
        )
        
        assert node.type == NodeType.DECISION
        assert node.when == now
        assert "Josh" in node.who
        assert "logo" in node.tags


class TestSQLiteBackend:
    """Tests for SQLite storage backend."""
    
    def test_add_and_get_node(self, storage):
        node = MemoryNode(
            what="Test memory",
            tags=["test"],
        )
        
        node_id = storage.add_node(node)
        retrieved = storage.get_node(node_id)
        
        assert retrieved is not None
        assert retrieved.what == "Test memory"
        assert "test" in retrieved.tags
    
    def test_update_node(self, storage):
        node = MemoryNode(what="Original")
        node_id = storage.add_node(node)
        
        node.what = "Updated"
        success = storage.update_node(node)
        
        assert success
        retrieved = storage.get_node(node_id)
        assert retrieved.what == "Updated"
    
    def test_delete_node(self, storage):
        node = MemoryNode(what="To be deleted")
        node_id = storage.add_node(node)
        
        success = storage.delete_node(node_id)
        
        assert success
        assert storage.get_node(node_id) is None
    
    def test_add_and_get_edge(self, storage):
        node1 = MemoryNode(what="Cause")
        node2 = MemoryNode(what="Effect")
        
        id1 = storage.add_node(node1)
        id2 = storage.add_node(node2)
        
        edge = Edge(
            source_id=id1,
            target_id=id2,
            type=EdgeType.LED_TO,
        )
        storage.add_edge(edge)
        
        # Get outgoing edges from node1
        edges = storage.get_edges(id1, direction="outgoing")
        assert len(edges) == 1
        assert edges[0].target_id == id2
        assert edges[0].type == EdgeType.LED_TO
    
    def test_query_by_time(self, storage):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        # Add nodes at different times
        old = MemoryNode(what="Old", when=now - timedelta(days=7))
        recent = MemoryNode(what="Recent", when=now - timedelta(hours=1))
        future = MemoryNode(what="Future", when=now + timedelta(days=1))
        
        storage.add_node(old)
        storage.add_node(recent)
        storage.add_node(future)
        
        # Query last 24 hours
        results = storage.query_by_time(
            since=now - timedelta(days=1),
            until=now
        )
        
        assert len(results) == 1
        assert results[0].what == "Recent"
    
    def test_query_by_tags(self, storage):
        storage.add_node(MemoryNode(what="Logo work", tags=["design", "logo"]))
        storage.add_node(MemoryNode(what="Code work", tags=["code", "pitbull"]))
        storage.add_node(MemoryNode(what="Both", tags=["design", "code"]))
        
        # Match any
        results = storage.query_by_tags(["design"])
        assert len(results) == 2
        
        # Match all
        results = storage.query_by_tags(["design", "code"], match_all=True)
        assert len(results) == 1
        assert results[0].what == "Both"
    
    def test_query_by_text(self, storage):
        storage.add_node(MemoryNode(what="Created the pitbull logo"))
        storage.add_node(MemoryNode(what="Fixed a bug in the API"))
        storage.add_node(MemoryNode(what="Updated the logo colors"))
        
        results = storage.query_by_text("logo")
        
        assert len(results) == 2
        whats = [r.what for r in results]
        assert "Created the pitbull logo" in whats
        assert "Updated the logo colors" in whats
