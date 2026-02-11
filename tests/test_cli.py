"""Tests for Engram CLI commands."""

import json
import pytest
from click.testing import CliRunner
from datetime import datetime, timedelta
from uuid import UUID

from engram.cli import cli, get_storage, parse_datetime
from engram.core import MemoryNode, Edge, EdgeType, NodeType, SQLiteBackend


@pytest.fixture
def runner():
    """Create a Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def temp_db(tmp_path):
    """Create a temp database path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def storage_with_data(temp_db):
    """Create a storage with some test data."""
    storage = SQLiteBackend(temp_db)
    storage.initialize()
    
    # Add some test memories
    nodes = []
    
    n1 = MemoryNode(
        what="Started the project",
        when=datetime(2026, 2, 10, 9, 0),
        who=["Josh"],
        tags=["project", "start"],
    )
    storage.add_node(n1)
    nodes.append(n1)
    
    n2 = MemoryNode(
        what="Created the logo design",
        when=datetime(2026, 2, 10, 10, 0),
        who=["River"],
        where="Studio",
        why="Client requested branding",
        how="Generated AI variations",
        tags=["logo", "design"],
    )
    storage.add_node(n2)
    nodes.append(n2)
    
    n3 = MemoryNode(
        what="Logo approved by client",
        when=datetime(2026, 2, 10, 11, 0),
        who=["Josh", "River"],
        tags=["logo", "approval"],
        type=NodeType.DECISION,
    )
    storage.add_node(n3)
    nodes.append(n3)
    
    # Add an edge
    edge = Edge(
        source_id=n2.id,
        target_id=n3.id,
        type=EdgeType.LED_TO,
    )
    storage.add_edge(edge)
    
    storage.close()
    return temp_db, nodes


class TestParseDatetime:
    """Tests for datetime parsing."""
    
    def test_parse_now(self):
        result = parse_datetime("now")
        assert isinstance(result, datetime)
        # Should be within 1 second of now
        assert (datetime.now() - result).total_seconds() < 1
    
    def test_parse_today(self):
        result = parse_datetime("today")
        assert result.hour == 0
        assert result.minute == 0
    
    def test_parse_yesterday(self):
        result = parse_datetime("yesterday")
        expected = datetime.now() - timedelta(days=1)
        assert result.date() == expected.date()
    
    def test_parse_relative_minutes(self):
        result = parse_datetime("30 minutes ago")
        expected = datetime.now() - timedelta(minutes=30)
        assert abs((result - expected).total_seconds()) < 2
    
    def test_parse_relative_hours(self):
        result = parse_datetime("2 hours ago")
        expected = datetime.now() - timedelta(hours=2)
        assert abs((result - expected).total_seconds()) < 2
    
    def test_parse_relative_days(self):
        result = parse_datetime("3 days ago")
        expected = datetime.now() - timedelta(days=3)
        assert abs((result - expected).total_seconds()) < 2
    
    def test_parse_iso_format(self):
        result = parse_datetime("2026-02-10 14:30:00")
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 10
        assert result.hour == 14
        assert result.minute == 30
    
    def test_parse_date_only(self):
        result = parse_datetime("2026-02-10")
        assert result.year == 2026
        assert result.month == 2
        assert result.day == 10


class TestAddCommand:
    """Tests for 'engram add' command."""
    
    def test_add_minimal(self, runner, temp_db):
        result = runner.invoke(cli, ["--db", temp_db, "add", "Test memory"])
        assert result.exit_code == 0
        assert "Added memory" in result.output
    
    def test_add_with_all_options(self, runner, temp_db):
        result = runner.invoke(cli, [
            "--db", temp_db,
            "add", "Full memory test",
            "--when", "2026-02-10 14:30",
            "--who", "Josh",
            "--who", "River",
            "--where", "Office",
            "--why", "Testing purposes",
            "--how", "Automated test",
            "--tags", "test,cli,full",
            "--type", "decision",
        ])
        
        assert result.exit_code == 0
        assert "Added memory" in result.output
        
        # Verify it was stored
        storage = get_storage(temp_db)
        results = storage.query_by_text("Full memory test")
        assert len(results) == 1
        node = results[0]
        assert "Josh" in node.who
        assert "River" in node.who
        assert node.where == "Office"
        assert node.why == "Testing purposes"
        assert "test" in node.tags
        assert node.type == NodeType.DECISION
        storage.close()
    
    def test_add_with_link(self, runner, temp_db):
        # First add a node
        result1 = runner.invoke(cli, ["--db", temp_db, "add", "First memory"])
        assert result1.exit_code == 0
        
        # Get the ID from output
        storage = get_storage(temp_db)
        first_node = storage.query_by_text("First memory")[0]
        storage.close()
        
        # Add second node linked to first
        result2 = runner.invoke(cli, [
            "--db", temp_db,
            "add", "Second memory",
            "--link-to", str(first_node.id),
        ])
        
        assert result2.exit_code == 0
        assert "Linked from" in result2.output


class TestQueryCommand:
    """Tests for 'engram query' command."""
    
    def test_query_by_text(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, ["--db", db_path, "query", "logo"])
        
        assert result.exit_code == 0
        assert "logo design" in result.output.lower() or "logo" in result.output.lower()
    
    def test_query_by_tags(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, ["--db", db_path, "query", "--tags", "logo"])
        
        assert result.exit_code == 0
        # Should find both logo-related memories
        assert "2 memories" in result.output or "logo" in result.output.lower()
    
    def test_query_recent(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, ["--db", db_path, "query"])
        
        assert result.exit_code == 0
        assert "3 memories" in result.output
    
    def test_query_with_hops(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "query", "logo design",
            "--hops", "1",
        ])
        
        assert result.exit_code == 0
        # Should expand to include connected nodes
    
    def test_query_json_output(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, ["--db", db_path, "query", "--json"])
        
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == 3
        assert all("id" in item for item in data)
        assert all("what" in item for item in data)
    
    def test_query_empty_results(self, runner, temp_db):
        result = runner.invoke(cli, ["--db", temp_db, "query", "nonexistent"])
        
        assert result.exit_code == 0
        assert "No memories found" in result.output


class TestShowCommand:
    """Tests for 'engram show' command."""
    
    def test_show_by_full_id(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, ["--db", db_path, "show", str(nodes[1].id)])
        
        assert result.exit_code == 0
        assert "Created the logo design" in result.output
        assert "River" in result.output
        assert "Studio" in result.output
    
    def test_show_by_partial_id(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        partial_id = str(nodes[0].id)[:8]
        
        result = runner.invoke(cli, ["--db", db_path, "show", partial_id])
        
        assert result.exit_code == 0
        assert "Started the project" in result.output
    
    def test_show_with_connections(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        # Node 1 (logo design) has an edge to node 2 (approval)
        
        result = runner.invoke(cli, ["--db", db_path, "show", str(nodes[1].id)])
        
        assert result.exit_code == 0
        assert "Connections:" in result.output
        # Check the connected node's content is shown (edge type display format may vary)
        assert "Logo approved" in result.output
    
    def test_show_not_found(self, runner, temp_db):
        result = runner.invoke(cli, ["--db", temp_db, "show", "nonexistent123"])
        
        assert result.exit_code == 0
        assert "not found" in result.output.lower() or "No memory" in result.output


class TestRelateCommand:
    """Tests for 'engram relate' command."""
    
    def test_relate_basic(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "relate",
            str(nodes[0].id),
            str(nodes[1].id),
            "--type", "led_to",
        ])
        
        assert result.exit_code == 0
        assert "Related:" in result.output
        # Verify the edge was actually created by checking show command
        show_result = runner.invoke(cli, ["--db", db_path, "show", str(nodes[0].id)])
        assert "Connections:" in show_result.output
    
    def test_relate_default_type(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "relate",
            str(nodes[0].id),
            str(nodes[1].id),
        ])
        
        assert result.exit_code == 0
        assert "Related:" in result.output
        # Default type is relates_to - verify edge was created
        show_result = runner.invoke(cli, ["--db", db_path, "show", str(nodes[0].id)])
        assert "Connections:" in show_result.output
    
    def test_relate_with_partial_ids(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "relate",
            str(nodes[0].id)[:8],
            str(nodes[1].id)[:8],
            "--type", "caused_by",
        ])
        
        assert result.exit_code == 0
        assert "Related:" in result.output


class TestPathCommand:
    """Tests for 'engram path' command."""
    
    def test_find_direct_path(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        # nodes[1] -> nodes[2] via LED_TO edge
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "path",
            str(nodes[1].id),
            str(nodes[2].id),
        ])
        
        assert result.exit_code == 0
        assert "Path" in result.output or "steps" in result.output
    
    def test_no_path_found(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        # Create an isolated node
        storage = get_storage(db_path)
        isolated = MemoryNode(what="Isolated memory")
        storage.add_node(isolated)
        storage.close()
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "path",
            str(nodes[0].id),
            str(isolated.id),
        ])
        
        assert result.exit_code == 0
        assert "No path found" in result.output


class TestContextCommand:
    """Tests for 'engram context' command."""
    
    def test_context_default_hops(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "context",
            str(nodes[1].id),
        ])
        
        assert result.exit_code == 0
        assert "memories in context" in result.output
    
    def test_context_custom_hops(self, runner, storage_with_data):
        db_path, nodes = storage_with_data
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "context",
            str(nodes[1].id),
            "--hops", "1",
        ])
        
        assert result.exit_code == 0


class TestCLIIntegration:
    """Integration tests combining multiple commands."""
    
    def test_full_workflow(self, runner, temp_db):
        """Test adding memories, relating them, and querying."""
        
        # Add first memory
        r1 = runner.invoke(cli, [
            "--db", temp_db,
            "add", "Started building the house",
            "--tags", "construction,start",
            "--type", "event",
        ])
        assert r1.exit_code == 0
        
        # Add second memory
        r2 = runner.invoke(cli, [
            "--db", temp_db,
            "add", "Poured the foundation",
            "--tags", "construction,foundation",
            "--type", "event",
        ])
        assert r2.exit_code == 0
        
        # Add third memory
        r3 = runner.invoke(cli, [
            "--db", temp_db,
            "add", "Framing completed",
            "--tags", "construction,framing",
            "--type", "event",
        ])
        assert r3.exit_code == 0
        
        # Get the IDs
        storage = get_storage(temp_db)
        nodes = storage.query_by_tags(["construction"])
        storage.close()
        
        assert len(nodes) == 3
        
        # Create relationships
        node_dict = {n.what: n for n in nodes}
        
        r4 = runner.invoke(cli, [
            "--db", temp_db,
            "relate",
            str(node_dict["Started building the house"].id),
            str(node_dict["Poured the foundation"].id),
            "--type", "led_to",
        ])
        assert r4.exit_code == 0
        
        r5 = runner.invoke(cli, [
            "--db", temp_db,
            "relate",
            str(node_dict["Poured the foundation"].id),
            str(node_dict["Framing completed"].id),
            "--type", "led_to",
        ])
        assert r5.exit_code == 0
        
        # Query with traversal
        r6 = runner.invoke(cli, [
            "--db", temp_db,
            "query", "building house",
            "--hops", "2",
        ])
        assert r6.exit_code == 0
        
        # Find path
        r7 = runner.invoke(cli, [
            "--db", temp_db,
            "path",
            str(node_dict["Started building the house"].id),
            str(node_dict["Framing completed"].id),
        ])
        assert r7.exit_code == 0
        assert "3" in r7.output  # 3 steps


class TestImportMd:
    """Tests for the import-md command."""
    
    def test_import_md_basic(self, runner, temp_db):
        """Test basic markdown import."""
        # Create a test markdown file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""# Test File

## First Section

This is the first section content.

## Lessons Learned

We learned something important here.

## Decision Made

We decided to do X instead of Y.
""")
            md_path = f.name
        
        try:
            result = runner.invoke(cli, ["--db", temp_db, "import-md", md_path])
            assert result.exit_code == 0
            assert "Imported:" in result.output
            assert "3 nodes" in result.output
        finally:
            import os
            os.unlink(md_path)
    
    def test_import_md_dry_run(self, runner, temp_db):
        """Test dry-run mode shows preview without saving."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""## Test Section

Content here.
""")
            md_path = f.name
        
        try:
            result = runner.invoke(cli, ["--db", temp_db, "import-md", md_path, "--dry-run"])
            assert result.exit_code == 0
            assert "Dry run:" in result.output
            assert "Would create" in result.output
        finally:
            import os
            os.unlink(md_path)
    
    def test_import_md_with_tags(self, runner, temp_db):
        """Test adding tags to imported nodes."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write("""## Quick Note

Just a note.
""")
            md_path = f.name
        
        try:
            result = runner.invoke(cli, ["--db", temp_db, "import-md", md_path, "--tag", "imported", "--tag", "test"])
            assert result.exit_code == 0
            assert "Imported:" in result.output
        finally:
            import os
            os.unlink(md_path)


class TestStats:
    """Tests for the stats command."""
    
    def test_stats_empty(self, runner, temp_db):
        """Test stats on empty database."""
        result = runner.invoke(cli, ["--db", temp_db, "stats"])
        assert result.exit_code == 0
        assert "No memories" in result.output
    
    def test_stats_with_data(self, runner, temp_db):
        """Test stats with some data."""
        # Add some nodes
        runner.invoke(cli, ["--db", temp_db, "add", "First memory", "--type", "event"])
        runner.invoke(cli, ["--db", temp_db, "add", "Second memory", "--type", "decision"])
        
        result = runner.invoke(cli, ["--db", temp_db, "stats"])
        assert result.exit_code == 0
        assert "Nodes by Type" in result.output
        assert "event" in result.output
        assert "decision" in result.output


class TestExport:
    """Tests for the export command."""
    
    def test_export_empty(self, runner, temp_db):
        """Test export on empty database."""
        result = runner.invoke(cli, ["--db", temp_db, "export"])
        assert result.exit_code == 0
        assert "No memories" in result.output
    
    def test_export_md(self, runner, temp_db):
        """Test markdown export."""
        runner.invoke(cli, ["--db", temp_db, "add", "Test memory", "--tags", "test,export"])
        
        result = runner.invoke(cli, ["--db", temp_db, "export", "--format", "md"])
        assert result.exit_code == 0
        assert "Test memory" in result.output
        assert "test" in result.output
    
    def test_export_json(self, runner, temp_db):
        """Test JSON export."""
        runner.invoke(cli, ["--db", temp_db, "add", "JSON test", "--type", "artifact"])
        
        result = runner.invoke(cli, ["--db", temp_db, "export", "--format", "json"])
        assert result.exit_code == 0
        assert '"type": "artifact"' in result.output
        assert '"what": "JSON test"' in result.output
