"""Tests for tree/root model functionality."""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from engram.core import (
    MemoryNode,
    Edge,
    EdgeType,
    NodeType,
    KnowledgeScope,
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


class TestKnowledgeScope:
    """Tests for KnowledgeScope enum."""
    
    def test_scope_values(self):
        assert KnowledgeScope.BRANCH.value == "branch"
        assert KnowledgeScope.ROOT.value == "root"
    
    def test_scope_from_string(self):
        assert KnowledgeScope("branch") == KnowledgeScope.BRANCH
        assert KnowledgeScope("root") == KnowledgeScope.ROOT


class TestMemoryNodeTreeFields:
    """Tests for tree/root fields on MemoryNode."""
    
    def test_default_scope_is_branch(self):
        node = MemoryNode(what="Test")
        assert node.scope == KnowledgeScope.BRANCH
    
    def test_default_project_is_none(self):
        node = MemoryNode(what="Test")
        assert node.project is None
    
    def test_create_branch_node(self):
        node = MemoryNode(
            what="Vista can only do monthly costing",
            project="vista",
            scope=KnowledgeScope.BRANCH,
        )
        assert node.project == "vista"
        assert node.scope == KnowledgeScope.BRANCH
    
    def test_create_root_node(self):
        node = MemoryNode(
            what="Vista costing gap - no weekly granularity",
            project="vista",
            scope=KnowledgeScope.ROOT,
        )
        assert node.project == "vista"
        assert node.scope == KnowledgeScope.ROOT
    
    def test_root_without_project(self):
        """Root knowledge can exist without a project (shared insight)."""
        node = MemoryNode(
            what="All legacy systems struggle with real-time data",
            scope=KnowledgeScope.ROOT,
        )
        assert node.project is None
        assert node.scope == KnowledgeScope.ROOT


class TestStorageTreeFields:
    """Tests for storage backend tree/root support."""
    
    def test_add_and_get_node_with_project(self, storage):
        node = MemoryNode(
            what="PnPv4 decision",
            project="pnpv4",
            scope=KnowledgeScope.BRANCH,
        )
        
        node_id = storage.add_node(node)
        retrieved = storage.get_node(node_id)
        
        assert retrieved.project == "pnpv4"
        assert retrieved.scope == KnowledgeScope.BRANCH
    
    def test_add_and_get_root_node(self, storage):
        node = MemoryNode(
            what="Root cause insight",
            project="vista",
            scope=KnowledgeScope.ROOT,
        )
        
        node_id = storage.add_node(node)
        retrieved = storage.get_node(node_id)
        
        assert retrieved.project == "vista"
        assert retrieved.scope == KnowledgeScope.ROOT
    
    def test_update_node_preserves_tree_fields(self, storage):
        node = MemoryNode(
            what="Original",
            project="pitbull",
            scope=KnowledgeScope.ROOT,
        )
        node_id = storage.add_node(node)
        
        node.what = "Updated"
        storage.update_node(node)
        
        retrieved = storage.get_node(node_id)
        assert retrieved.what == "Updated"
        assert retrieved.project == "pitbull"
        assert retrieved.scope == KnowledgeScope.ROOT


class TestQueryByProject:
    """Tests for project-based querying."""
    
    @pytest.fixture
    def populated_storage(self, storage):
        """Storage with nodes across multiple projects."""
        # Vista nodes
        storage.add_node(MemoryNode(
            what="Vista monthly costing only",
            project="vista",
            scope=KnowledgeScope.BRANCH,
        ))
        storage.add_node(MemoryNode(
            what="Vista costing gap - no weekly",
            project="vista",
            scope=KnowledgeScope.ROOT,
        ))
        
        # PnPv4 nodes
        storage.add_node(MemoryNode(
            what="PnPv4 fills the costing gap",
            project="pnpv4",
            scope=KnowledgeScope.BRANCH,
        ))
        storage.add_node(MemoryNode(
            what="PnPv4 weekly rollups work well",
            project="pnpv4",
            scope=KnowledgeScope.BRANCH,
        ))
        
        # Global root (no project)
        storage.add_node(MemoryNode(
            what="Legacy systems rarely do real-time",
            scope=KnowledgeScope.ROOT,
        ))
        
        return storage
    
    def test_query_by_project_includes_roots(self, populated_storage):
        """Query by project should include both branches and roots by default."""
        results = populated_storage.query_by_project("vista", include_roots=True)
        
        # Should get vista branch, vista root, and global root
        assert len(results) >= 2
        whats = [r.what for r in results]
        assert "Vista monthly costing only" in whats
        assert "Vista costing gap - no weekly" in whats
    
    def test_query_by_project_branches_only(self, populated_storage):
        """Query by project excluding roots."""
        results = populated_storage.query_by_project("vista", include_roots=False)
        
        # Should only get vista branch nodes
        assert len(results) == 1
        assert results[0].what == "Vista monthly costing only"
    
    def test_query_roots_only(self, populated_storage):
        """Query only root-scoped nodes."""
        results = populated_storage.query_roots_only()
        
        # Should get both roots (vista root and global root)
        assert len(results) == 2
        for r in results:
            assert r.scope == KnowledgeScope.ROOT
    
    def test_query_different_projects(self, populated_storage):
        """Query different projects returns different results."""
        vista = populated_storage.query_by_project("vista", include_roots=False)
        pnpv4 = populated_storage.query_by_project("pnpv4", include_roots=False)
        
        assert len(vista) == 1
        assert len(pnpv4) == 2
        
        vista_whats = {r.what for r in vista}
        pnpv4_whats = {r.what for r in pnpv4}
        
        # No overlap (branches are project-specific)
        assert vista_whats.isdisjoint(pnpv4_whats)


class TestTextSearchWithFilters:
    """Tests for text search with project/scope filtering."""
    
    @pytest.fixture
    def search_storage(self, storage):
        """Storage with searchable nodes."""
        storage.add_node(MemoryNode(
            what="Vista costing is monthly only",
            project="vista",
            scope=KnowledgeScope.BRANCH,
        ))
        storage.add_node(MemoryNode(
            what="Costing gap exposed by Vista",
            project="vista",
            scope=KnowledgeScope.ROOT,
        ))
        storage.add_node(MemoryNode(
            what="PnPv4 addresses costing with weekly rollups",
            project="pnpv4",
            scope=KnowledgeScope.BRANCH,
        ))
        return storage
    
    def test_text_search_with_project_filter(self, search_storage):
        """Text search filtered to a project."""
        results = search_storage.query_by_text_filtered(
            "costing",
            project="vista"
        )
        
        # Should find both vista nodes (branch and root)
        assert len(results) == 2
        for r in results:
            assert r.project == "vista" or r.scope == KnowledgeScope.ROOT
    
    def test_text_search_roots_only(self, search_storage):
        """Text search filtered to roots only."""
        results = search_storage.query_by_text_filtered(
            "costing",
            roots_only=True
        )
        
        # Should only find the root node
        assert len(results) == 1
        assert results[0].scope == KnowledgeScope.ROOT
        assert "gap" in results[0].what


class TestProjectStats:
    """Tests for project statistics."""
    
    @pytest.fixture
    def stats_storage(self, storage):
        """Storage with multiple projects for stats."""
        # Vista: 2 branches, 1 root
        storage.add_node(MemoryNode(what="v1", project="vista", scope=KnowledgeScope.BRANCH))
        storage.add_node(MemoryNode(what="v2", project="vista", scope=KnowledgeScope.BRANCH))
        storage.add_node(MemoryNode(what="v3", project="vista", scope=KnowledgeScope.ROOT))
        
        # PnPv4: 1 branch
        storage.add_node(MemoryNode(what="p1", project="pnpv4", scope=KnowledgeScope.BRANCH))
        
        # Orphan root
        storage.add_node(MemoryNode(what="o1", scope=KnowledgeScope.ROOT))
        
        return storage
    
    def test_get_all_projects(self, stats_storage):
        """Get list of all project names."""
        projects = stats_storage.get_all_projects()
        
        assert "vista" in projects
        assert "pnpv4" in projects
        assert len(projects) == 2
    
    def test_get_project_stats(self, stats_storage):
        """Get detailed project statistics."""
        stats = stats_storage.get_project_stats()
        
        assert 'projects' in stats
        assert 'total_roots' in stats
        assert 'orphan_roots' in stats
        
        # Find vista stats
        vista_stats = next(p for p in stats['projects'] if p['name'] == 'vista')
        assert vista_stats['node_count'] == 3
        assert vista_stats['branch_count'] == 2
        assert vista_stats['root_count'] == 1
        
        # Check root counts
        assert stats['total_roots'] == 2  # vista root + orphan
        assert stats['orphan_roots'] == 1


class TestNewEdgeTypes:
    """Tests for cross-project edge types."""
    
    def test_exposes_root_edge(self, storage):
        """Test EXPOSES_ROOT edge type."""
        # Branch decision exposes a root insight
        branch = MemoryNode(what="Vista only does monthly", project="vista", scope=KnowledgeScope.BRANCH)
        root = MemoryNode(what="Weekly costing gap", project="vista", scope=KnowledgeScope.ROOT)
        
        branch_id = storage.add_node(branch)
        root_id = storage.add_node(root)
        
        edge = Edge(
            source_id=branch_id,
            target_id=root_id,
            type=EdgeType.EXPOSES_ROOT,
        )
        storage.add_edge(edge)
        
        edges = storage.get_edges(branch_id, direction="outgoing")
        assert len(edges) == 1
        assert edges[0].type == EdgeType.EXPOSES_ROOT
    
    def test_addresses_root_edge(self, storage):
        """Test ADDRESSES_ROOT edge type."""
        # PnPv4 addresses a root cause from Vista
        root = MemoryNode(what="Weekly costing gap", project="vista", scope=KnowledgeScope.ROOT)
        solution = MemoryNode(what="PnPv4 does weekly rollups", project="pnpv4", scope=KnowledgeScope.BRANCH)
        
        root_id = storage.add_node(root)
        solution_id = storage.add_node(solution)
        
        edge = Edge(
            source_id=solution_id,
            target_id=root_id,
            type=EdgeType.ADDRESSES_ROOT,
        )
        storage.add_edge(edge)
        
        edges = storage.get_edges(solution_id, direction="outgoing")
        assert len(edges) == 1
        assert edges[0].type == EdgeType.ADDRESSES_ROOT
        assert edges[0].target_id == root_id


class TestMigration:
    """Tests for backwards compatibility with existing databases."""
    
    def test_node_without_project_scope_loads(self, storage):
        """Nodes created before tree/root feature should load with defaults."""
        # Simulate old-style node (no project/scope)
        node = MemoryNode(what="Old node")
        node_id = storage.add_node(node)
        
        retrieved = storage.get_node(node_id)
        
        # Should have default values
        assert retrieved.project is None
        assert retrieved.scope == KnowledgeScope.BRANCH
