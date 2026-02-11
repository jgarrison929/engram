#!/usr/bin/env python3
"""
Engram CLI - Command-line interface for memory operations.

Usage:
    engram add "What happened" --when "2026-02-10 14:30" --tags logo,design
    engram query "logo"
    engram query --since yesterday --until now
    engram path <from-id> <to-id>
    engram show <id>
    engram list --limit 10
"""

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID

try:
    import click
    from rich.console import Console
    from rich.table import Table
    from rich.tree import Tree
    from rich.panel import Panel
except ImportError:
    print("CLI dependencies not installed. Run: pip install click rich")
    sys.exit(1)

from engram.core import (
    MemoryNode,
    Edge,
    EdgeType,
    NodeType,
    SQLiteBackend,
)
from engram.query import MemoryTraverser


# Global console for rich output
console = Console()

# Default database path
DEFAULT_DB = Path.home() / ".engram" / "memory.db"


def get_storage(db_path: Optional[str] = None) -> SQLiteBackend:
    """Get or create storage backend."""
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    storage = SQLiteBackend(str(path))
    storage.initialize()
    return storage


def parse_datetime(value: str) -> datetime:
    """Parse flexible datetime input."""
    value = value.lower().strip()
    now = datetime.now()
    
    # Relative times
    if value == "now":
        return now
    if value == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if value == "yesterday":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if value.endswith(" ago"):
        # Parse "5 minutes ago", "2 hours ago", "3 days ago"
        parts = value[:-4].strip().split()
        if len(parts) == 2:
            amount, unit = int(parts[0]), parts[1]
            if unit.startswith("min"):
                return now - timedelta(minutes=amount)
            if unit.startswith("hour"):
                return now - timedelta(hours=amount)
            if unit.startswith("day"):
                return now - timedelta(days=amount)
    
    # ISO format or common formats
    for fmt in [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ]:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    
    raise ValueError(f"Cannot parse datetime: {value}")


def print_version(ctx, param, value):
    """Print version and exit."""
    if not value or ctx.resilient_parsing:
        return
    from engram import __version__
    click.echo(f"engram {__version__}")
    ctx.exit()


@click.group()
@click.option("--version", "-V", is_flag=True, callback=print_version, expose_value=False, is_eager=True, help="Show version and exit")
@click.option("--db", envvar="ENGRAM_DB", help="Database path (default: ~/.engram/memory.db)")
@click.pass_context
def cli(ctx, db):
    """Engram - Graph-based memory for AI agents."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = db


@cli.command()
@click.argument("what")
@click.option("--when", "-w", help="When it happened (default: now)")
@click.option("--who", "-p", multiple=True, help="People involved (repeatable)")
@click.option("--where", help="Context/location")
@click.option("--why", help="Reasoning")
@click.option("--how", help="Method/process")
@click.option("--tags", "-t", help="Comma-separated tags")
@click.option("--type", "node_type", type=click.Choice([t.value for t in NodeType]), default="event")
@click.option("--artifact", "-a", multiple=True, help="Linked files/URLs (repeatable)")
@click.option("--link-to", help="Node ID to link this to (creates LED_TO edge)")
@click.pass_context
def add(ctx, what, when, who, where, why, how, tags, node_type, artifact, link_to):
    """Add a new memory.
    
    Examples:
        engram add "Created the pitbull logo"
        engram add "Deployed to production" --when "2 hours ago" --tags deploy,pitbull
        engram add "Josh approved the design" --who Josh --type decision
    """
    storage = get_storage(ctx.obj.get("db"))
    
    # Parse inputs
    when_dt = parse_datetime(when) if when else datetime.now()
    tags_list = [t.strip() for t in tags.split(",")] if tags else []
    
    # Create node
    node = MemoryNode(
        type=NodeType(node_type),
        what=what,
        when=when_dt,
        where=where,
        who=list(who),
        why=why,
        how=how,
        tags=tags_list,
        artifacts=list(artifact),
    )
    
    node_id = storage.add_node(node)
    
    # Create edge if linking
    if link_to:
        try:
            target_id = UUID(link_to)
            edge = Edge(
                source_id=target_id,
                target_id=node_id,
                type=EdgeType.LED_TO,
            )
            storage.add_edge(edge)
            console.print(f"  ↳ Linked from {link_to[:8]}...", style="dim")
        except ValueError:
            console.print(f"  ⚠ Invalid link-to ID: {link_to}", style="yellow")
    
    console.print(f"✓ Added memory: [bold]{node_id}[/bold]")
    console.print(f"  {what[:60]}{'...' if len(what) > 60 else ''}", style="dim")
    
    storage.close()


@cli.command()
@click.argument("query", required=False)
@click.option("--since", "-s", help="Start time (e.g., 'yesterday', '2 hours ago')")
@click.option("--until", "-u", help="End time (default: now)")
@click.option("--tags", "-t", help="Filter by tags (comma-separated)")
@click.option("--hops", "-h", default=0, help="Traverse N hops from matches (default: 0)")
@click.option("--limit", "-n", default=20, help="Max results (default: 20)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
@click.pass_context
def query(ctx, query, since, until, tags, hops, limit, as_json):
    """Query memories.
    
    Examples:
        engram query "logo"
        engram query --since yesterday
        engram query --tags pitbull,design --hops 2
    """
    storage = get_storage(ctx.obj.get("db"))
    traverser = MemoryTraverser(storage)
    
    results = []
    
    # Text search
    if query:
        results = storage.query_by_text(query, limit=limit)
    
    # Tag filter
    elif tags:
        tag_list = [t.strip() for t in tags.split(",")]
        results = storage.query_by_tags(tag_list, limit=limit)
    
    # Time range
    elif since or until:
        since_dt = parse_datetime(since) if since else None
        until_dt = parse_datetime(until) if until else datetime.now()
        results = storage.query_by_time(since=since_dt, until=until_dt, limit=limit)
    
    else:
        # Default: recent memories
        results = storage.query_by_time(limit=limit)
    
    # Traverse if requested
    if hops > 0 and results:
        expanded = []
        seen = set()
        for node in results:
            if node.id not in seen:
                seen.add(node.id)
                expanded.append(node)
                # Traverse from this node
                related = traverser.traverse_bfs(node.id, max_hops=hops, include_start=False)
                for r in related:
                    if r.node.id not in seen:
                        seen.add(r.node.id)
                        expanded.append(r.node)
        results = expanded
    
    # Output
    if as_json:
        output = []
        for node in results:
            output.append({
                "id": str(node.id),
                "type": node.type.value,
                "what": node.what,
                "when": node.when.isoformat() if node.when else None,
                "who": node.who,
                "where": node.where,
                "why": node.why,
                "tags": node.tags,
            })
        print(json.dumps(output, indent=2))
    else:
        if not results:
            console.print("No memories found.", style="dim")
        else:
            table = Table(show_header=True, header_style="bold")
            table.add_column("When", style="cyan", width=16)
            table.add_column("What", style="white")
            table.add_column("Tags", style="green", width=20)
            table.add_column("ID", style="dim", width=10)
            
            for node in results:
                when_str = node.when.strftime("%m/%d %H:%M") if node.when else "?"
                tags_str = ", ".join(node.tags[:3]) + ("..." if len(node.tags) > 3 else "")
                table.add_row(
                    when_str,
                    node.what[:50] + ("..." if len(node.what) > 50 else ""),
                    tags_str,
                    str(node.id)[:8],
                )
            
            console.print(table)
            console.print(f"\n{len(results)} memories", style="dim")
    
    storage.close()


@cli.command()
@click.argument("node_id")
@click.pass_context
def show(ctx, node_id):
    """Show details of a specific memory.
    
    Example:
        engram show abc12345
    """
    storage = get_storage(ctx.obj.get("db"))
    
    # Handle partial IDs
    if len(node_id) < 36:
        # Search for matching ID prefix
        all_nodes = storage.query_by_time(limit=1000)
        matches = [n for n in all_nodes if str(n.id).startswith(node_id)]
        if len(matches) == 0:
            console.print(f"No memory found matching: {node_id}", style="red")
            storage.close()
            return
        elif len(matches) > 1:
            console.print(f"Multiple matches for {node_id}:", style="yellow")
            for m in matches[:5]:
                console.print(f"  {m.id} - {m.what[:40]}")
            storage.close()
            return
        node = matches[0]
    else:
        node = storage.get_node(UUID(node_id))
    
    if not node:
        console.print(f"Memory not found: {node_id}", style="red")
        storage.close()
        return
    
    # Display
    panel_content = []
    panel_content.append(f"[bold]What:[/bold] {node.what}")
    if node.when:
        panel_content.append(f"[bold]When:[/bold] {node.when.strftime('%Y-%m-%d %H:%M:%S')}")
    if node.who:
        panel_content.append(f"[bold]Who:[/bold] {', '.join(node.who)}")
    if node.where:
        panel_content.append(f"[bold]Where:[/bold] {node.where}")
    if node.why:
        panel_content.append(f"[bold]Why:[/bold] {node.why}")
    if node.how:
        panel_content.append(f"[bold]How:[/bold] {node.how}")
    if node.tags:
        panel_content.append(f"[bold]Tags:[/bold] {', '.join(node.tags)}")
    if node.artifacts:
        panel_content.append(f"[bold]Artifacts:[/bold] {', '.join(node.artifacts)}")
    panel_content.append(f"[bold]Type:[/bold] {node.type.value}")
    panel_content.append(f"[bold]ID:[/bold] {node.id}")
    
    console.print(Panel("\n".join(panel_content), title="Memory", border_style="blue"))
    
    # Show connections
    edges = storage.get_edges(node.id)
    if edges:
        console.print("\n[bold]Connections:[/bold]")
        for edge in edges:
            direction = "→" if edge.source_id == node.id else "←"
            other_id = edge.target_id if edge.source_id == node.id else edge.source_id
            other = storage.get_node(other_id)
            if other:
                console.print(f"  {direction} \\[{edge.type.value}] {other.what[:40]}... ({str(other_id)[:8]})")
    
    storage.close()


@cli.command()
@click.argument("from_id")
@click.argument("to_id")
@click.option("--max-hops", "-m", default=6, help="Maximum path length (default: 6)")
@click.pass_context
def path(ctx, from_id, to_id, max_hops):
    """Find the path between two memories (six degrees).
    
    Example:
        engram path abc123 def456
    """
    storage = get_storage(ctx.obj.get("db"))
    traverser = MemoryTraverser(storage)
    
    # Resolve partial IDs
    def resolve_id(partial):
        if len(partial) >= 36:
            return UUID(partial)
        all_nodes = storage.query_by_time(limit=1000)
        matches = [n for n in all_nodes if str(n.id).startswith(partial)]
        if len(matches) == 1:
            return matches[0].id
        raise ValueError(f"Cannot resolve ID: {partial}")
    
    try:
        from_uuid = resolve_id(from_id)
        to_uuid = resolve_id(to_id)
    except ValueError as e:
        console.print(str(e), style="red")
        storage.close()
        return
    
    path_nodes = traverser.find_path(from_uuid, to_uuid, max_hops=max_hops)
    
    if not path_nodes:
        console.print(f"No path found within {max_hops} hops.", style="yellow")
    else:
        console.print(f"\n[bold]Path ({len(path_nodes)} steps):[/bold]\n")
        for i, node in enumerate(path_nodes):
            prefix = "  " if i == 0 else "    ↓\n  "
            when_str = node.when.strftime("%m/%d %H:%M") if node.when else "?"
            console.print(f"{prefix}[cyan]{when_str}[/cyan] {node.what[:50]}")
    
    storage.close()


@cli.command()
@click.argument("from_id")
@click.option("--hops", "-h", default=2, help="How many hops to traverse (default: 2)")
@click.pass_context
def context(ctx, from_id, hops):
    """Show the context graph around a memory.
    
    Example:
        engram context abc123 --hops 3
    """
    storage = get_storage(ctx.obj.get("db"))
    traverser = MemoryTraverser(storage)
    
    # Resolve partial ID
    if len(from_id) < 36:
        all_nodes = storage.query_by_time(limit=1000)
        matches = [n for n in all_nodes if str(n.id).startswith(from_id)]
        if len(matches) != 1:
            console.print(f"Cannot resolve ID: {from_id}", style="red")
            storage.close()
            return
        start_node = matches[0]
    else:
        start_node = storage.get_node(UUID(from_id))
    
    if not start_node:
        console.print(f"Memory not found: {from_id}", style="red")
        storage.close()
        return
    
    results = traverser.traverse_bfs(start_node.id, max_hops=hops, include_start=True)
    
    # Build tree visualization
    tree = Tree(f"[bold]{start_node.what[:40]}...[/bold]")
    
    # Group by hop count
    by_hop = {}
    for r in results:
        if r.hop_count not in by_hop:
            by_hop[r.hop_count] = []
        by_hop[r.hop_count].append(r)
    
    # Add to tree
    for hop in sorted(by_hop.keys()):
        if hop == 0:
            continue
        hop_branch = tree.add(f"[dim]Hop {hop}[/dim]")
        for r in by_hop[hop]:
            when_str = r.node.when.strftime("%m/%d") if r.node.when else "?"
            hop_branch.add(f"[cyan]{when_str}[/cyan] {r.node.what[:40]}...")
    
    console.print(tree)
    console.print(f"\n{len(results)} memories in context", style="dim")
    
    storage.close()


@cli.command()
@click.argument("source_id")
@click.argument("target_id")
@click.option("--type", "-t", "edge_type", 
              type=click.Choice([e.value for e in EdgeType]), 
              default="relates_to",
              help="Relationship type")
@click.pass_context
def relate(ctx, source_id, target_id, edge_type):
    """Create a relationship between two memories.
    
    Relationship types:
      - caused_by: X was caused by Y
      - led_to: X led to Y
      - supersedes: X replaces Y (newer version)
      - preceded_by: X came after Y
      - relates_to: General association (default)
      - contradicts: X conflicts with Y
      - supports: X reinforces Y
      - mentions: X references Y
      - part_of: X is a component of Y
      - derived_from: X was created from Y
    
    Examples:
        engram relate abc123 def456 --type caused_by
        engram relate <decision-id> <event-id> --type led_to
    """
    storage = get_storage(ctx.obj.get("db"))
    
    # Resolve IDs (simplified - assumes full UUIDs for now)
    try:
        source_uuid = UUID(source_id) if len(source_id) >= 36 else None
        target_uuid = UUID(target_id) if len(target_id) >= 36 else None
        
        if not source_uuid or not target_uuid:
            # Try partial match
            all_nodes = storage.query_by_time(limit=1000)
            for n in all_nodes:
                if str(n.id).startswith(source_id):
                    source_uuid = n.id
                if str(n.id).startswith(target_id):
                    target_uuid = n.id
        
        if not source_uuid or not target_uuid:
            raise ValueError("Could not resolve IDs")
            
    except ValueError as e:
        console.print(f"Invalid ID: {e}", style="red")
        storage.close()
        return
    
    edge = Edge(
        source_id=source_uuid,
        target_id=target_uuid,
        type=EdgeType(edge_type),
    )
    
    storage.add_edge(edge)
    console.print(f"✓ Related: {str(source_uuid)[:8]} --[{edge_type}]--> {str(target_uuid)[:8]}")
    
    storage.close()


# Alias 'link' to 'relate' for backwards compatibility
@cli.command("link", hidden=True)
@click.argument("source_id")
@click.argument("target_id")
@click.option("--type", "-t", "edge_type", 
              type=click.Choice([e.value for e in EdgeType]), 
              default="relates_to")
@click.pass_context
def link(ctx, source_id, target_id, edge_type):
    """Alias for 'relate' (deprecated)."""
    ctx.invoke(relate, source_id=source_id, target_id=target_id, edge_type=edge_type)


@cli.command()
@click.argument("filepath", type=click.Path(exists=True))
@click.option("--dry-run", is_flag=True, help="Show what would be imported without saving")
@click.option("--tag", "-t", multiple=True, help="Add tags to all imported nodes")
@click.pass_context
def import_md(ctx, filepath, dry_run, tag):
    """Import a markdown file as memory nodes.
    
    Parses markdown sections (## headers) as separate memories.
    Each section becomes a node with:
      - what: The section content
      - tags: From the header + any --tag options
      - type: Inferred from content (FACT, LESSON, DECISION, etc.)
    
    Examples:
        engram import-md MEMORY.md
        engram import-md memory/2026-02-10.md --tag daily-log
        engram import-md notes.md --dry-run
    """
    import re
    
    storage = get_storage(ctx.obj.get("db"))
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split by ## headers
    sections = re.split(r'^## ', content, flags=re.MULTILINE)
    
    nodes_created = []
    
    for section in sections[1:]:  # Skip content before first ##
        if not section.strip():
            continue
            
        lines = section.strip().split('\n')
        header = lines[0].strip()
        body = '\n'.join(lines[1:]).strip()
        
        if not body:
            continue
        
        # Infer node type from header/content
        header_lower = header.lower()
        if any(w in header_lower for w in ['lesson', 'learned', 'insight']):
            node_type = NodeType.INSIGHT
        elif any(w in header_lower for w in ['decision', 'chose', 'decided']):
            node_type = NodeType.DECISION
        elif any(w in header_lower for w in ['todo', 'task', 'action']):
            node_type = NodeType.TASK
        elif any(w in header_lower for w in ['project', 'module', 'feature']):
            node_type = NodeType.PROJECT
        elif any(w in header_lower for w in ['person', 'who', 'contact']):
            node_type = NodeType.PERSON
        else:
            node_type = NodeType.EVENT
        
        # Create tags from header words + provided tags
        header_tags = [w.lower() for w in re.findall(r'\w+', header) if len(w) > 2]
        all_tags = list(set(header_tags + list(tag)))
        
        node = MemoryNode(
            type=node_type,
            what=f"{header}\n\n{body}",
            tags=all_tags,
        )
        
        if dry_run:
            console.print(Panel(
                f"[bold]{header}[/bold]\n\n"
                f"Type: {node_type.value}\n"
                f"Tags: {', '.join(all_tags)}\n"
                f"Content: {body[:200]}{'...' if len(body) > 200 else ''}",
                title=f"[dim]{str(node.id)[:8]}[/dim]"
            ))
        else:
            storage.add_node(node)
            nodes_created.append(node)
            console.print(f"✓ {str(node.id)[:8]}: {header[:50]}")
    
    if dry_run:
        console.print(f"\n[yellow]Dry run:[/yellow] Would create {len(sections) - 1} nodes")
    else:
        console.print(f"\n[green]Imported:[/green] {len(nodes_created)} nodes from {filepath}")
    
    storage.close()


@cli.command()
@click.pass_context
def stats(ctx):
    """Show memory graph statistics.
    
    Displays:
      - Total nodes by type
      - Total edges by type
      - Date range of memories
      - Most connected nodes
    
    Example:
        engram stats
    """
    from collections import Counter
    
    storage = get_storage(ctx.obj.get("db"))
    
    # Get all nodes and edges
    all_nodes = storage.query_by_time(limit=10000)
    
    if not all_nodes:
        console.print("[yellow]No memories stored yet.[/yellow]")
        storage.close()
        return
    
    # Count by type
    type_counts = Counter(n.type.value for n in all_nodes)
    
    # Get all edges
    edge_counts = Counter()
    node_edge_counts = Counter()
    
    for node in all_nodes:
        edges = storage.get_edges(node.id)
        for edge in edges:
            edge_counts[edge.type.value] += 1
            node_edge_counts[node.id] += 1
    
    # Date range
    dates = [n.when for n in all_nodes if n.when]
    min_date = min(dates) if dates else None
    max_date = max(dates) if dates else None
    
    # Build output
    console.print(Panel("[bold]Engram Memory Statistics[/bold]", style="blue"))
    
    # Node counts
    console.print("\n[bold]Nodes by Type:[/bold]")
    node_table = Table(show_header=False, box=None)
    node_table.add_column("Type", style="cyan")
    node_table.add_column("Count", justify="right")
    for ntype, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        node_table.add_row(ntype, str(count))
    node_table.add_row("[bold]Total[/bold]", f"[bold]{len(all_nodes)}[/bold]")
    console.print(node_table)
    
    # Edge counts
    if edge_counts:
        console.print("\n[bold]Edges by Type:[/bold]")
        edge_table = Table(show_header=False, box=None)
        edge_table.add_column("Type", style="green")
        edge_table.add_column("Count", justify="right")
        for etype, count in sorted(edge_counts.items(), key=lambda x: -x[1]):
            edge_table.add_row(etype, str(count))
        edge_table.add_row("[bold]Total[/bold]", f"[bold]{sum(edge_counts.values())}[/bold]")
        console.print(edge_table)
    else:
        console.print("\n[dim]No edges yet.[/dim]")
    
    # Date range
    if min_date and max_date:
        console.print(f"\n[bold]Date Range:[/bold] {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')}")
    
    # Most connected
    if node_edge_counts:
        console.print("\n[bold]Most Connected Nodes:[/bold]")
        for node_id, count in node_edge_counts.most_common(5):
            node = storage.get_node(node_id)
            if node:
                what_preview = node.what[:50] + "..." if len(node.what) > 50 else node.what
                console.print(f"  {str(node_id)[:8]}: {count} edges - {what_preview}")
    
    storage.close()


@cli.command()
@click.option("--format", "-f", "output_format", type=click.Choice(["json", "md"]), default="md", help="Output format")
@click.option("--since", help="Export nodes since this time")
@click.option("--limit", "-n", default=100, help="Max nodes to export")
@click.pass_context
def export(ctx, output_format, since, limit):
    """Export memories to JSON or Markdown.
    
    Examples:
        engram export > backup.md
        engram export --format json > memories.json
        engram export --since yesterday --format md
    """
    storage = get_storage(ctx.obj.get("db"))
    
    since_dt = parse_datetime(since) if since else None
    nodes = storage.query_by_time(since=since_dt, limit=limit)
    
    if not nodes:
        console.print("[yellow]No memories to export.[/yellow]")
        storage.close()
        return
    
    if output_format == "json":
        import json
        output = []
        for node in nodes:
            node_dict = {
                "id": str(node.id),
                "type": node.type.value,
                "what": node.what,
                "when": node.when.isoformat() if node.when else None,
                "where": node.where,
                "who": node.who,
                "why": node.why,
                "how": node.how,
                "tags": node.tags,
                "artifacts": node.artifacts,
            }
            # Get edges
            edges = storage.get_edges(node.id)
            if edges:
                node_dict["edges"] = [
                    {"target": str(e.target_id), "type": e.type.value}
                    for e in edges
                ]
            output.append(node_dict)
        print(json.dumps(output, indent=2))
    else:
        # Markdown format
        print("# Engram Memory Export\n")
        print(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
        print(f"Total: {len(nodes)} memories\n")
        print("---\n")
        
        for node in nodes:
            print(f"## {node.what[:80]}\n")
            print(f"- **ID:** `{str(node.id)[:8]}`")
            print(f"- **Type:** {node.type.value}")
            if node.when:
                print(f"- **When:** {node.when.strftime('%Y-%m-%d %H:%M')}")
            if node.tags:
                print(f"- **Tags:** {', '.join(node.tags)}")
            if node.who:
                print(f"- **Who:** {', '.join(node.who)}")
            if node.where:
                print(f"- **Where:** {node.where}")
            if node.why:
                print(f"- **Why:** {node.why}")
            if node.how:
                print(f"- **How:** {node.how}")
            
            # Edges
            edges = storage.get_edges(node.id)
            if edges:
                print(f"- **Edges:**")
                for e in edges:
                    print(f"  - {e.type.value} → `{str(e.target_id)[:8]}`")
            
            print()
    
    storage.close()


def main():
    cli(obj={})


if __name__ == "__main__":
    main()
