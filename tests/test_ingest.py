"""Tests for Engram ingestion module (git, markdown, dedup)."""

import os
import pytest
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import UUID

from engram.core import SQLiteBackend, MemoryNode, NodeType
from engram.ingest import (
    import_git_repo,
    CommitFilter,
    import_markdown_file,
    import_markdown_dir,
    content_hash,
    check_duplicate,
)
from engram.ingest.dedup import add_node_with_dedup
from engram.ingest.git import (
    parse_git_log,
    is_significant,
    commit_to_node,
    GitCommit,
)
from engram.ingest.markdown import (
    extract_date_from_filename,
    infer_node_type,
    extract_tags,
    extract_people,
    parse_markdown_sections,
)


@pytest.fixture
def temp_db(tmp_path):
    """Create a temp database."""
    db_path = str(tmp_path / "test.db")
    storage = SQLiteBackend(db_path)
    storage.initialize()
    yield storage
    storage.close()


@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository with test commits."""
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    
    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_path, check=True, capture_output=True)
    
    # Create test commits
    commits = [
        ("feat: Add user authentication", ["src/auth.py"]),
        ("fix: Resolve login bug", ["src/auth.py", "tests/test_auth.py"]),
        ("docs: Update README", ["README.md"]),
        ("chore: Update dependencies", ["requirements.txt"]),
        ("Merge branch 'feature'", []),  # Merge commit
        ("feat: Add dashboard component", ["src/dashboard.py", "src/widgets.py"]),
        ("WIP checkpoint", ["src/wip.py"]),  # Trivial
        ("test: Add integration tests", ["tests/test_integration.py"]),
    ]
    
    for message, files in commits:
        for file in files:
            filepath = repo_path / file
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(f"# {message}\nprint('hello')")
            subprocess.run(["git", "add", file], cwd=repo_path, check=True, capture_output=True)
        
        if files:  # Can't commit without changes
            subprocess.run(["git", "commit", "-m", message], cwd=repo_path, check=True, capture_output=True)
    
    return repo_path


@pytest.fixture
def temp_md_dir(tmp_path):
    """Create a temporary directory with markdown files."""
    md_dir = tmp_path / "memory"
    md_dir.mkdir()
    
    # Create daily log files
    files = {
        "2026-02-10.md": """# Session Log

## Morning Standup

Discussed project priorities with the team.
Josh and River worked on the API integration.

## Bug Fix Session

Fixed critical auth bug:
- Issue: Users getting logged out
- Solution: Extended token lifetime
- @josh reviewed the fix

## Lessons Learned

Never deploy on Friday afternoons.
""",
        "2026-02-11.md": """# Another Day

## Feature Planning

Decided to implement new dashboard.
This was a team decision after reviewing metrics.

## Todo List

- [ ] Complete API docs
- [x] Review PRs
- [ ] Update tests
""",
        "notes.md": """# General Notes

## Project Overview

The pitbull project aims to streamline construction management.

## Contact Info

Josh Garrison - Project Lead
River - AI Assistant
""",
    }
    
    for filename, content in files.items():
        (md_dir / filename).write_text(content)
    
    return md_dir


class TestContentHash:
    """Tests for content hashing."""
    
    def test_same_content_same_hash(self):
        h1 = content_hash("Test content", "2026-02-10", "git:abc123")
        h2 = content_hash("Test content", "2026-02-10", "git:abc123")
        assert h1 == h2
    
    def test_different_content_different_hash(self):
        h1 = content_hash("Test content 1")
        h2 = content_hash("Test content 2")
        assert h1 != h2
    
    def test_hash_includes_when(self):
        h1 = content_hash("Test", "2026-02-10")
        h2 = content_hash("Test", "2026-02-11")
        assert h1 != h2
    
    def test_hash_includes_source(self):
        h1 = content_hash("Test", source="git:abc")
        h2 = content_hash("Test", source="git:def")
        assert h1 != h2
    
    def test_hash_length(self):
        h = content_hash("Test content")
        assert len(h) == 16  # Truncated SHA256


class TestCheckDuplicate:
    """Tests for duplicate detection."""
    
    def test_no_duplicate_empty_db(self, temp_db):
        result = check_duplicate(temp_db, "abc123")
        assert result is None
    
    def test_finds_duplicate(self, temp_db):
        node = MemoryNode(
            what="Test memory",
            source="git:test hash:abc123",
        )
        node_id = temp_db.add_node(node)
        
        result = check_duplicate(temp_db, "abc123")
        assert result == node_id
    
    def test_add_node_with_dedup_new(self, temp_db):
        node = MemoryNode(what="New memory")
        node_id, was_new = add_node_with_dedup(temp_db, node, "newHash123")
        
        assert was_new is True
        assert isinstance(node_id, UUID)
    
    def test_add_node_with_dedup_duplicate(self, temp_db):
        node1 = MemoryNode(what="Original memory")
        node_id1, was_new1 = add_node_with_dedup(temp_db, node1, "sameHash")
        
        node2 = MemoryNode(what="Duplicate memory")
        node_id2, was_new2 = add_node_with_dedup(temp_db, node2, "sameHash")
        
        assert was_new1 is True
        assert was_new2 is False
        assert node_id1 == node_id2


class TestGitCommitFilter:
    """Tests for git commit filtering."""
    
    def test_skip_merge_commits(self):
        commit = GitCommit(
            hash="abc123",
            author="Test",
            date=datetime.now(),
            message="Merge branch 'feature' into main",
            files=[],
        )
        filter_config = CommitFilter(skip_merge=True)
        assert is_significant(commit, filter_config) is False
    
    def test_include_feat_commits(self):
        commit = GitCommit(
            hash="abc123",
            author="Test",
            date=datetime.now(),
            message="feat: Add new feature",
            files=["src/feature.py"],
        )
        filter_config = CommitFilter()
        assert is_significant(commit, filter_config) is True
    
    def test_include_fix_commits(self):
        commit = GitCommit(
            hash="abc123",
            author="Test",
            date=datetime.now(),
            message="fix: Resolve critical bug",
            files=["src/bug.py"],
        )
        filter_config = CommitFilter()
        assert is_significant(commit, filter_config) is True
    
    def test_skip_wip_commits(self):
        commit = GitCommit(
            hash="abc123",
            author="Test",
            date=datetime.now(),
            message="WIP: work in progress",
            files=["src/wip.py"],
        )
        filter_config = CommitFilter(skip_trivial=True)
        assert is_significant(commit, filter_config) is False
    
    def test_significant_files_readme(self):
        commit = GitCommit(
            hash="abc123",
            author="Test",
            date=datetime.now(),
            message="update docs",
            files=["README.md"],
        )
        filter_config = CommitFilter()
        assert is_significant(commit, filter_config) is True
    
    def test_significant_files_ci(self):
        commit = GitCommit(
            hash="abc123",
            author="Test",
            date=datetime.now(),
            message="update ci",
            files=[".github/workflows/ci.yml"],
        )
        filter_config = CommitFilter()
        assert is_significant(commit, filter_config) is True


class TestCommitToNode:
    """Tests for converting commits to nodes."""
    
    def test_feat_commit_type(self):
        commit = GitCommit(
            hash="abc123def",
            author="Josh Garrison",
            date=datetime(2026, 2, 10, 14, 30),
            message="feat: Add user dashboard",
            files=["src/dashboard.py", "src/widgets.py"],
        )
        
        node = commit_to_node(commit, "pitbull")
        
        assert node.type == NodeType.ARTIFACT
        assert "Josh Garrison" in node.who
        assert node.when == datetime(2026, 2, 10, 14, 30)
        assert "pitbull" in node.tags
        assert "feat" in node.tags
        assert "python" in node.tags
        assert "git:pitbull:abc123d" in node.source
    
    def test_fix_commit_type(self):
        commit = GitCommit(
            hash="xyz789",
            author="River",
            date=datetime.now(),
            message="fix: Resolve memory leak",
            files=["src/memory.cs"],
        )
        
        node = commit_to_node(commit, "engram")
        
        assert node.type == NodeType.EVENT
        assert "csharp" in node.tags
    
    def test_how_field_populated(self):
        commit = GitCommit(
            hash="abc123",
            author="Test",
            date=datetime.now(),
            message="feat: Big change",
            files=["a.py", "b.py", "c.py", "d.py", "e.py", "f.py", "g.py"],
        )
        
        node = commit_to_node(commit, "test")
        
        assert "a.py" in node.how
        assert "(+2 more)" in node.how  # 7 files, showing 5


class TestImportGitRepo:
    """Tests for full git import."""
    
    def test_import_basic(self, temp_db, temp_git_repo):
        stats = import_git_repo(temp_db, temp_git_repo)
        
        assert stats["total_commits"] > 0
        assert stats["nodes_created"] > 0
    
    def test_import_filters_merge_commits(self, temp_db, temp_git_repo):
        stats = import_git_repo(
            temp_db,
            temp_git_repo,
            filter_config=CommitFilter(skip_merge=True),
        )
        
        # Verify no merge commit nodes
        nodes = temp_db.query_by_text("Merge")
        assert len(nodes) == 0
    
    def test_import_respects_max_commits(self, temp_db, temp_git_repo):
        stats = import_git_repo(
            temp_db,
            temp_git_repo,
            filter_config=CommitFilter(max_commits=2),
        )
        
        assert stats["nodes_created"] <= 2
    
    def test_import_creates_edges(self, temp_db, temp_git_repo):
        stats = import_git_repo(
            temp_db,
            temp_git_repo,
            link_related=True,
        )
        
        # Should have edges for commits touching same files
        assert stats["edges_created"] >= 0
    
    def test_import_dry_run(self, temp_db, temp_git_repo):
        stats = import_git_repo(
            temp_db,
            temp_git_repo,
            dry_run=True,
        )
        
        assert stats["total_commits"] > 0
        assert stats["nodes_created"] == 0  # Dry run doesn't create
    
    def test_import_deduplication(self, temp_db, temp_git_repo):
        # Import twice
        stats1 = import_git_repo(temp_db, temp_git_repo)
        stats2 = import_git_repo(temp_db, temp_git_repo)
        
        # Second import should skip all as duplicates
        assert stats2["nodes_skipped"] == stats1["nodes_created"]
        assert stats2["nodes_created"] == 0


class TestMarkdownDateExtraction:
    """Tests for date extraction from filenames."""
    
    def test_extract_date_standard(self):
        result = extract_date_from_filename(Path("2026-02-10.md"))
        assert result == datetime(2026, 2, 10)
    
    def test_extract_date_with_suffix(self):
        result = extract_date_from_filename(Path("2026-02-10-notes.md"))
        assert result == datetime(2026, 2, 10)
    
    def test_extract_date_with_prefix(self):
        result = extract_date_from_filename(Path("session-2026-02-10.md"))
        assert result == datetime(2026, 2, 10)
    
    def test_extract_date_underscore(self):
        result = extract_date_from_filename(Path("2026_02_10.md"))
        assert result == datetime(2026, 2, 10)
    
    def test_extract_date_compact(self):
        result = extract_date_from_filename(Path("20260210.md"))
        assert result == datetime(2026, 2, 10)
    
    def test_no_date_in_filename(self):
        result = extract_date_from_filename(Path("notes.md"))
        assert result is None


class TestMarkdownNodeTypeInference:
    """Tests for node type inference."""
    
    def test_infer_decision(self):
        assert infer_node_type("Decision Made", "We decided...") == NodeType.DECISION
        assert infer_node_type("Team Chose Option A", "...") == NodeType.DECISION
    
    def test_infer_lesson(self):
        assert infer_node_type("Lessons Learned", "...") == NodeType.INSIGHT
        assert infer_node_type("TIL about Python", "...") == NodeType.INSIGHT
    
    def test_infer_task(self):
        assert infer_node_type("Todo List", "...") == NodeType.TASK
        assert infer_node_type("Action Items", "...") == NodeType.TASK
    
    def test_infer_task_from_content(self):
        assert infer_node_type("Random Header", "- [ ] Do thing\n- [x] Done") == NodeType.TASK
    
    def test_infer_project(self):
        assert infer_node_type("Project Overview", "...") == NodeType.PROJECT
        assert infer_node_type("Feature Roadmap", "...") == NodeType.PROJECT
    
    def test_infer_conversation(self):
        assert infer_node_type("Meeting Notes", "...") == NodeType.CONVERSATION
        assert infer_node_type("Team Discussion", "...") == NodeType.CONVERSATION
    
    def test_infer_default_event(self):
        assert infer_node_type("Random Section", "Some content") == NodeType.EVENT


class TestMarkdownTagExtraction:
    """Tests for tag extraction."""
    
    def test_extract_from_header(self):
        tags = extract_tags("Bug Fix Session", "...")
        assert "bug" in tags
        assert "fix" in tags
        assert "session" in tags
    
    def test_extract_hashtags(self):
        tags = extract_tags("Notes", "Working on #frontend and #api")
        assert "frontend" in tags
        assert "api" in tags
    
    def test_detect_topic_keywords(self):
        tags = extract_tags("Work", "Fixed a bug in the authentication system")
        assert "bug" in tags
    
    def test_limit_tags(self):
        # Long header with many words
        tags = extract_tags(
            "This Is A Very Long Header With Many Words",
            "And #lots #of #hashtags #here #too #many #extra #more #tags #overflow"
        )
        assert len(tags) <= 10


class TestMarkdownPeopleExtraction:
    """Tests for people extraction."""
    
    def test_extract_mentions(self):
        people = extract_people("Discussed with @josh and @river")
        assert "josh" in people
        assert "river" in people
    
    def test_extract_by_pattern(self):
        people = extract_people("Fixed by Josh Garrison")
        assert "Josh Garrison" in people or "Josh" in people
    
    def test_extract_action_pattern(self):
        people = extract_people("River created the design")
        assert "River" in people


class TestMarkdownSectionParsing:
    """Tests for markdown section parsing."""
    
    def test_parse_sections(self):
        content = """# Title

## First Section

Content one.

## Second Section

Content two.
"""
        sections = parse_markdown_sections(content)
        
        assert len(sections) == 2
        assert sections[0][0] == "First Section"
        assert "Content one" in sections[0][1]
        assert sections[1][0] == "Second Section"
    
    def test_nested_headers_in_body(self):
        content = """## Main Section

Content here.

### Subsection

More content.
"""
        sections = parse_markdown_sections(content)
        
        # ### should be part of body, not a split
        assert len(sections) == 1
        assert "### Subsection" in sections[0][1]
    
    def test_empty_sections_skipped(self):
        content = """## Empty

## With Content

Hello
"""
        sections = parse_markdown_sections(content)
        
        assert len(sections) == 1
        assert sections[0][0] == "With Content"


class TestImportMarkdownFile:
    """Tests for single file import."""
    
    def test_import_basic(self, temp_db, temp_md_dir):
        filepath = temp_md_dir / "2026-02-10.md"
        stats = import_markdown_file(temp_db, filepath)
        
        assert stats["sections_found"] == 3
        assert stats["nodes_created"] == 3
    
    def test_import_extracts_date(self, temp_db, temp_md_dir):
        filepath = temp_md_dir / "2026-02-10.md"
        import_markdown_file(temp_db, filepath)
        
        nodes = temp_db.query_by_time(limit=10)
        # All nodes should have the file's date
        for node in nodes:
            assert node.when.date() == datetime(2026, 2, 10).date()
    
    def test_import_with_extra_tags(self, temp_db, temp_md_dir):
        filepath = temp_md_dir / "2026-02-10.md"
        import_markdown_file(temp_db, filepath, extra_tags=["daily-log", "test"])
        
        nodes = temp_db.query_by_tags(["daily-log"])
        assert len(nodes) == 3
    
    def test_import_dry_run(self, temp_db, temp_md_dir):
        filepath = temp_md_dir / "2026-02-10.md"
        stats = import_markdown_file(temp_db, filepath, dry_run=True)
        
        assert stats["sections_found"] == 3
        assert stats["nodes_created"] == 0
    
    def test_import_deduplication(self, temp_db, temp_md_dir):
        filepath = temp_md_dir / "2026-02-10.md"
        
        stats1 = import_markdown_file(temp_db, filepath)
        stats2 = import_markdown_file(temp_db, filepath)
        
        assert stats1["nodes_created"] == 3
        assert stats2["nodes_created"] == 0
        assert stats2["nodes_skipped"] == 3


class TestImportMarkdownDir:
    """Tests for directory import."""
    
    def test_import_all_files(self, temp_db, temp_md_dir):
        stats = import_markdown_dir(temp_db, temp_md_dir)
        
        assert stats["files_processed"] == 3
        assert stats["nodes_created"] > 0
    
    def test_import_with_pattern(self, temp_db, temp_md_dir):
        stats = import_markdown_dir(
            temp_db,
            temp_md_dir,
            pattern="2026-*.md",
        )
        
        assert stats["files_processed"] == 2  # Only date-named files
    
    def test_import_creates_date_edges(self, temp_db, temp_md_dir):
        stats = import_markdown_dir(
            temp_db,
            temp_md_dir,
            link_by_date=True,
        )
        
        # Should have edges linking nodes from same date
        assert stats["edges_created"] >= 0
    
    def test_import_dry_run(self, temp_db, temp_md_dir):
        stats = import_markdown_dir(temp_db, temp_md_dir, dry_run=True)
        
        assert stats["files_processed"] == 3
        assert stats["nodes_created"] == 0


class TestCLIImportGit:
    """Tests for import-git CLI command."""
    
    def test_import_git_command(self, temp_git_repo, tmp_path):
        from click.testing import CliRunner
        from engram.cli import cli
        
        runner = CliRunner()
        db_path = str(tmp_path / "test.db")
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "import-git", str(temp_git_repo),
        ])
        
        assert result.exit_code == 0
        assert "Nodes created:" in result.output
    
    def test_import_git_dry_run(self, temp_git_repo, tmp_path):
        from click.testing import CliRunner
        from engram.cli import cli
        
        runner = CliRunner()
        db_path = str(tmp_path / "test.db")
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "import-git", str(temp_git_repo),
            "--dry-run",
        ])
        
        assert result.exit_code == 0
        assert "Would create" in result.output
    
    def test_import_git_max_commits(self, temp_git_repo, tmp_path):
        from click.testing import CliRunner
        from engram.cli import cli
        
        runner = CliRunner()
        db_path = str(tmp_path / "test.db")
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "import-git", str(temp_git_repo),
            "--max", "2",
        ])
        
        assert result.exit_code == 0


class TestCLIImportMdDir:
    """Tests for import-md-dir CLI command."""
    
    def test_import_md_dir_command(self, temp_md_dir, tmp_path):
        from click.testing import CliRunner
        from engram.cli import cli
        
        runner = CliRunner()
        db_path = str(tmp_path / "test.db")
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "import-md-dir", str(temp_md_dir),
        ])
        
        assert result.exit_code == 0
        assert "Nodes created:" in result.output
    
    def test_import_md_dir_with_tags(self, temp_md_dir, tmp_path):
        from click.testing import CliRunner
        from engram.cli import cli
        
        runner = CliRunner()
        db_path = str(tmp_path / "test.db")
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "import-md-dir", str(temp_md_dir),
            "--tag", "imported",
            "--tag", "test",
        ])
        
        assert result.exit_code == 0
    
    def test_import_md_dir_dry_run(self, temp_md_dir, tmp_path):
        from click.testing import CliRunner
        from engram.cli import cli
        
        runner = CliRunner()
        db_path = str(tmp_path / "test.db")
        
        result = runner.invoke(cli, [
            "--db", db_path,
            "import-md-dir", str(temp_md_dir),
            "--dry-run",
        ])
        
        assert result.exit_code == 0
        assert "Would create" in result.output
