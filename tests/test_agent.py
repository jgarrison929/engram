"""Tests for the AgentMemory helper class."""

import tempfile
from pathlib import Path

import pytest

from src.agent import AgentMemory
from src.core import NodeType


@pytest.fixture
def agent_memory():
    """Create a temporary AgentMemory instance."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        memory = AgentMemory(db_path)
        yield memory
        memory.close()


class TestAgentMemoryBasics:
    """Basic AgentMemory functionality."""
    
    def test_context_manager(self):
        """Test using AgentMemory as context manager."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "test.db")
            with AgentMemory(db_path) as memory:
                node_id = memory.log_event("Test event")
                assert node_id is not None
    
    def test_log_task(self, agent_memory):
        """Test logging a task."""
        node_id = agent_memory.log_task(
            what="Implemented feature X",
            tags=["feature", "backend"],
            artifacts=["src/feature.py"],
            how="Used TDD approach",
        )
        
        node = agent_memory.storage.get_node(node_id)
        assert node is not None
        assert node.type == NodeType.TASK
        assert "feature X" in node.what
        assert "feature" in node.tags
    
    def test_log_insight(self, agent_memory):
        """Test logging an insight."""
        node_id = agent_memory.log_insight(
            what="Always validate input before processing",
            tags=["security", "best-practice"],
            why="Prevents injection attacks",
        )
        
        node = agent_memory.storage.get_node(node_id)
        assert node is not None
        assert node.type == NodeType.INSIGHT
        assert "validate" in node.what
    
    def test_log_decision(self, agent_memory):
        """Test logging a decision."""
        node_id = agent_memory.log_decision(
            what="Use PostgreSQL instead of MySQL",
            why="Better JSON support and performance",
            alternatives=["MySQL", "SQLite", "MongoDB"],
            tags=["database", "architecture"],
        )
        
        node = agent_memory.storage.get_node(node_id)
        assert node is not None
        assert node.type == NodeType.DECISION
        assert "PostgreSQL" in node.what
        assert "Alternatives" in node.how
    
    def test_log_event(self, agent_memory):
        """Test logging an event."""
        node_id = agent_memory.log_event(
            what="Deployed to production",
            who=["agent", "josh"],
            where="railway",
            tags=["deploy", "production"],
        )
        
        node = agent_memory.storage.get_node(node_id)
        assert node is not None
        assert node.type == NodeType.EVENT


class TestContextLoading:
    """Test context loading functionality."""
    
    def test_load_empty_context(self, agent_memory):
        """Test loading context from empty database."""
        context = agent_memory.load_context()
        assert context == []
    
    def test_load_context_with_data(self, agent_memory):
        """Test loading context with some memories."""
        agent_memory.log_task("Task 1", tags=["project"])
        agent_memory.log_task("Task 2", tags=["project"])
        agent_memory.log_insight("Lesson learned", tags=["project"])
        
        context = agent_memory.load_context(tags=["project"])
        assert len(context) >= 3
    
    def test_get_recent_tasks(self, agent_memory):
        """Test retrieving recent tasks."""
        agent_memory.log_task("Task A")
        agent_memory.log_event("Event B")  # Not a task
        agent_memory.log_task("Task C")
        
        tasks = agent_memory.get_recent_tasks()
        assert len(tasks) == 2
        assert all(t.type == NodeType.TASK for t in tasks)
    
    def test_get_insights(self, agent_memory):
        """Test retrieving insights."""
        agent_memory.log_insight("Insight 1", tags=["python"])
        agent_memory.log_task("Task 1")  # Not an insight
        agent_memory.log_insight("Insight 2", tags=["python"])
        
        insights = agent_memory.get_insights(tags=["python"])
        assert len(insights) == 2
        assert all(i.type == NodeType.INSIGHT for i in insights)


class TestLinking:
    """Test automatic linking between memories."""
    
    def test_task_links_to_previous(self, agent_memory):
        """Test that tasks can link to previous context."""
        event_id = agent_memory.log_event("User requested feature")
        task_id = agent_memory.log_task(
            "Implemented feature",
            link_to=event_id,
        )
        
        # Check edge was created
        edges = agent_memory.storage.get_edges(event_id)
        assert len(edges) == 1
        assert edges[0].target_id == task_id
    
    def test_insight_auto_links_to_last_task(self, agent_memory):
        """Test that insights auto-link to the last task."""
        task_id = agent_memory.log_task("Did something tricky")
        insight_id = agent_memory.log_insight("Learned a lesson")
        
        # Insight should be linked from the task
        edges = agent_memory.storage.get_edges(task_id)
        assert len(edges) == 1
        assert edges[0].target_id == insight_id


class TestSearch:
    """Test search functionality."""
    
    def test_text_search(self, agent_memory):
        """Test full-text search."""
        agent_memory.log_task("Implemented authentication system")
        agent_memory.log_task("Fixed database connection pool")
        agent_memory.log_task("Added authentication middleware")
        
        results = agent_memory.search("authentication")
        assert len(results) >= 1  # Should find authentication-related items
    
    def test_find_related(self, agent_memory):
        """Test finding related memories."""
        task1 = agent_memory.log_task("Task 1")
        task2 = agent_memory.log_task("Task 2", link_to=task1)
        task3 = agent_memory.log_task("Task 3", link_to=task2)
        
        related = agent_memory.find_related(task1, max_hops=2)
        related_ids = {r.id for r in related}
        assert task2 in related_ids
        assert task3 in related_ids
