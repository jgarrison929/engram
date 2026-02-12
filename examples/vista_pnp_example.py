#!/usr/bin/env python3
"""
Example: The Vista/PnP Pattern - Understanding Why Projects Exist

This example demonstrates Engram's tree/root model using a real-world scenario:
- Vista: A legacy system with limitations (the costing gap)
- PnPv4: A project created to address Vista's limitations
- PnPv5: A successor project that builds on PnPv4's foundation

The Tree/Root Model:
    🌳 TREES = Projects (Vista, PnPv4, PnPv5, Pitbull, etc.)
    🌿 BRANCHES = Project-specific knowledge (can't cross trees)
    🌱 ROOTS = Shared knowledge, the "why" (crosses projects)

Key insight: Roots are the connective tissue between projects. They capture
the fundamental problems/insights that explain why projects exist and how
they relate to each other.

Usage:
    python examples/vista_pnp_example.py
    
    # Or via CLI demo flag (if implemented):
    engram --demo vista-pnp
"""

import tempfile
from pathlib import Path

from engram.core import (
    MemoryNode,
    Edge,
    EdgeType,
    NodeType,
    KnowledgeScope,
    SQLiteBackend,
)
from engram.query import MemoryTraverser


def create_vista_tree(storage: SQLiteBackend) -> dict:
    """Create the Vista project tree.
    
    Vista is a legacy costing system that only supports monthly rollups.
    This creates a fundamental gap that other projects need to address.
    """
    print("\n🌳 Creating Vista Tree...")
    
    # The Vista project node (the tree itself)
    vista = MemoryNode(
        type=NodeType.PROJECT,
        what="Vista - Legacy costing and financials system",
        project="vista",
        scope=KnowledgeScope.BRANCH,
        tags=["system", "legacy", "costing", "financials"],
        why="Core financial system of record for the organization",
    )
    vista_id = storage.add_node(vista)
    print(f"  ✓ Vista project: {str(vista_id)[:8]}")
    
    # Branch: Vista's costing architecture (project-specific fact)
    vista_monthly = MemoryNode(
        type=NodeType.ARTIFACT,
        what="Vista costing only supports monthly rollups",
        project="vista",
        scope=KnowledgeScope.BRANCH,
        tags=["costing", "limitation", "architecture"],
        why="Legacy architecture decision - monthly batches were standard in 2005",
        how="Batch processing runs on the 1st of each month",
    )
    vista_monthly_id = storage.add_node(vista_monthly)
    print(f"  ✓ Monthly limitation: {str(vista_monthly_id)[:8]}")
    
    # 🌱 ROOT: The costing gap - this is SHARED knowledge that other projects can address
    costing_gap = MemoryNode(
        type=NodeType.INSIGHT,
        what="Vista costing gap: Cannot do weekly or daily cost analysis",
        project="vista",
        scope=KnowledgeScope.ROOT,  # <-- This is a ROOT (shared knowledge)
        tags=["costing", "gap", "requirement"],
        why="Business needs real-time cost visibility, not just monthly snapshots",
        how="Users manually export to Excel for weekly analysis - error-prone and slow",
    )
    costing_gap_id = storage.add_node(costing_gap)
    print(f"  🌱 Costing gap (ROOT): {str(costing_gap_id)[:8]}")
    
    # Edge: The branch EXPOSES the root (monthly limitation reveals the gap)
    edge = Edge(
        source_id=vista_monthly_id,
        target_id=costing_gap_id,
        type=EdgeType.EXPOSES_ROOT,
        metadata={"context": "limitation exposes fundamental gap"},
    )
    storage.add_edge(edge)
    
    # Edge: Monthly limitation is PART_OF Vista
    edge2 = Edge(
        source_id=vista_monthly_id,
        target_id=vista_id,
        type=EdgeType.PART_OF,
    )
    storage.add_edge(edge2)
    
    return {
        "project_id": vista_id,
        "monthly_id": vista_monthly_id,
        "costing_gap_id": costing_gap_id,
    }


def create_pnpv4_tree(storage: SQLiteBackend, vista_refs: dict) -> dict:
    """Create the PnPv4 project tree.
    
    PnPv4 was created specifically to address the Vista costing gap.
    It introduces weekly rollups as a solution.
    """
    print("\n🌳 Creating PnPv4 Tree...")
    
    # The PnPv4 project node
    pnpv4 = MemoryNode(
        type=NodeType.PROJECT,
        what="PnPv4 - Pick and Pack version 4 with costing integration",
        project="pnpv4",
        scope=KnowledgeScope.BRANCH,
        tags=["system", "warehouse", "costing"],
        why="Replace manual costing processes with automated weekly rollups",
    )
    pnpv4_id = storage.add_node(pnpv4)
    print(f"  ✓ PnPv4 project: {str(pnpv4_id)[:8]}")
    
    # Branch: PnPv4's weekly costing feature
    weekly_rollups = MemoryNode(
        type=NodeType.ARTIFACT,
        what="PnPv4 implements weekly costing rollups",
        project="pnpv4",
        scope=KnowledgeScope.BRANCH,
        tags=["costing", "feature", "weekly"],
        why="Fills the gap that Vista couldn't address",
        how="Automated batch runs every Sunday night, aggregates pick costs",
    )
    weekly_rollups_id = storage.add_node(weekly_rollups)
    print(f"  ✓ Weekly rollups feature: {str(weekly_rollups_id)[:8]}")
    
    # 🌱 ROOT: The insight that weekly granularity is achievable
    weekly_insight = MemoryNode(
        type=NodeType.INSIGHT,
        what="Weekly costing granularity is sufficient for operational decisions",
        project="pnpv4",
        scope=KnowledgeScope.ROOT,  # <-- Shared insight
        tags=["costing", "insight", "granularity"],
        why="Daily is too volatile, monthly too slow; weekly hits the sweet spot",
    )
    weekly_insight_id = storage.add_node(weekly_insight)
    print(f"  🌱 Weekly insight (ROOT): {str(weekly_insight_id)[:8]}")
    
    # Decision: Why PnPv4 was created
    decision = MemoryNode(
        type=NodeType.DECISION,
        what="Build PnPv4 to solve Vista costing limitations",
        project="pnpv4",
        scope=KnowledgeScope.BRANCH,
        tags=["decision", "architecture"],
        why="Vista can't be modified; need greenfield solution for costing",
        how="New system that integrates with Vista via nightly data sync",
        who=["Josh", "Architecture Team"],
    )
    decision_id = storage.add_node(decision)
    print(f"  ✓ Creation decision: {str(decision_id)[:8]}")
    
    # === EDGES: Connect PnPv4 to Vista's root ===
    
    # PnPv4 ADDRESSES_ROOT the Vista costing gap
    # This is the key cross-project connection!
    edge = Edge(
        source_id=weekly_rollups_id,
        target_id=vista_refs["costing_gap_id"],
        type=EdgeType.ADDRESSES_ROOT,
        metadata={"how": "weekly rollups fill the monthly-only gap"},
    )
    storage.add_edge(edge)
    print(f"  🔗 Connected: PnPv4 weekly rollups ADDRESSES Vista costing gap")
    
    # Weekly rollups EXPOSES the weekly insight
    edge2 = Edge(
        source_id=weekly_rollups_id,
        target_id=weekly_insight_id,
        type=EdgeType.EXPOSES_ROOT,
    )
    storage.add_edge(edge2)
    
    # Decision CAUSED_BY the costing gap
    edge3 = Edge(
        source_id=decision_id,
        target_id=vista_refs["costing_gap_id"],
        type=EdgeType.CAUSED_BY,
    )
    storage.add_edge(edge3)
    
    return {
        "project_id": pnpv4_id,
        "weekly_rollups_id": weekly_rollups_id,
        "weekly_insight_id": weekly_insight_id,
        "decision_id": decision_id,
    }


def create_pnpv5_tree(storage: SQLiteBackend, pnpv4_refs: dict, vista_refs: dict) -> dict:
    """Create the PnPv5 project tree.
    
    PnPv5 builds on PnPv4's foundation and adds real-time costing.
    It's the evolution of the solution to Vista's original gap.
    """
    print("\n🌳 Creating PnPv5 Tree...")
    
    # The PnPv5 project node
    pnpv5 = MemoryNode(
        type=NodeType.PROJECT,
        what="PnPv5 - Next generation with real-time costing",
        project="pnpv5",
        scope=KnowledgeScope.BRANCH,
        tags=["system", "warehouse", "costing", "realtime"],
        why="Evolution of PnPv4 with real-time capabilities",
    )
    pnpv5_id = storage.add_node(pnpv5)
    print(f"  ✓ PnPv5 project: {str(pnpv5_id)[:8]}")
    
    # Branch: Real-time costing feature
    realtime = MemoryNode(
        type=NodeType.ARTIFACT,
        what="PnPv5 implements real-time cost streaming",
        project="pnpv5",
        scope=KnowledgeScope.BRANCH,
        tags=["costing", "feature", "realtime", "streaming"],
        why="Weekly wasn't fast enough for some use cases",
        how="Event-driven architecture with cost calculations on every pick",
    )
    realtime_id = storage.add_node(realtime)
    print(f"  ✓ Real-time costing: {str(realtime_id)[:8]}")
    
    # 🌱 ROOT: Event-driven costing pattern
    event_pattern = MemoryNode(
        type=NodeType.INSIGHT,
        what="Event-driven architecture enables real-time costing without batch lag",
        project="pnpv5",
        scope=KnowledgeScope.ROOT,
        tags=["architecture", "pattern", "event-driven"],
        why="Batch processing will always have latency; events give immediate feedback",
    )
    event_pattern_id = storage.add_node(event_pattern)
    print(f"  🌱 Event pattern (ROOT): {str(event_pattern_id)[:8]}")
    
    # === EDGES ===
    
    # PnPv5 SUPERSEDES PnPv4 (evolution)
    edge = Edge(
        source_id=pnpv5_id,
        target_id=pnpv4_refs["project_id"],
        type=EdgeType.SUPERSEDES,
        metadata={"type": "major version evolution"},
    )
    storage.add_edge(edge)
    print(f"  🔗 PnPv5 SUPERSEDES PnPv4")
    
    # PnPv5 also ADDRESSES the original Vista costing gap
    edge2 = Edge(
        source_id=realtime_id,
        target_id=vista_refs["costing_gap_id"],
        type=EdgeType.ADDRESSES_ROOT,
        metadata={"how": "real-time streaming is the ultimate answer to batch limitations"},
    )
    storage.add_edge(edge2)
    print(f"  🔗 PnPv5 real-time ADDRESSES Vista costing gap")
    
    # Real-time feature EXPOSES the event-driven pattern
    edge3 = Edge(
        source_id=realtime_id,
        target_id=event_pattern_id,
        type=EdgeType.EXPOSES_ROOT,
    )
    storage.add_edge(edge3)
    
    # PnPv5 DERIVED_FROM PnPv4's weekly insight
    edge4 = Edge(
        source_id=pnpv5_id,
        target_id=pnpv4_refs["weekly_insight_id"],
        type=EdgeType.DERIVED_FROM,
        metadata={"evolution": "weekly was good, but real-time is better"},
    )
    storage.add_edge(edge4)
    
    return {
        "project_id": pnpv5_id,
        "realtime_id": realtime_id,
        "event_pattern_id": event_pattern_id,
    }


def query_why_pnpv5_exists(storage: SQLiteBackend, traverser: MemoryTraverser, pnpv5_refs: dict):
    """
    Query: "Why does PnPv5 exist?"
    
    Trace backwards through the graph to find the root causes.
    This demonstrates how Engram can answer "why" questions by
    following edges back to their roots.
    """
    print("\n" + "=" * 60)
    print("🔍 QUERY: Why does PnPv5 exist?")
    print("=" * 60)
    
    # Start from PnPv5 project node and traverse backwards
    pnpv5_node = storage.get_node(pnpv5_refs["project_id"])
    print(f"\nStarting from: {pnpv5_node.what}")
    
    # Follow SUPERSEDES edge back to PnPv4
    supersedes_edges = storage.get_edges(
        pnpv5_refs["project_id"], 
        direction="outgoing",
        edge_type=EdgeType.SUPERSEDES
    )
    
    if supersedes_edges:
        predecessor = storage.get_node(supersedes_edges[0].target_id)
        print(f"\n1️⃣  PnPv5 supersedes: {predecessor.what}")
    
    # Follow DERIVED_FROM to find the insight it built on
    derived_edges = storage.get_edges(
        pnpv5_refs["project_id"],
        direction="outgoing",
        edge_type=EdgeType.DERIVED_FROM
    )
    
    if derived_edges:
        insight = storage.get_node(derived_edges[0].target_id)
        print(f"\n2️⃣  PnPv5 derived from insight: {insight.what}")
    
    # Follow ADDRESSES_ROOT to find the original problem
    addresses_edges = storage.get_edges(
        pnpv5_refs["realtime_id"],
        direction="outgoing",
        edge_type=EdgeType.ADDRESSES_ROOT
    )
    
    if addresses_edges:
        root = storage.get_node(addresses_edges[0].target_id)
        print(f"\n3️⃣  PnPv5 ultimately addresses ROOT: {root.what}")
        print(f"    Why this matters: {root.why}")
        print(f"    From project: {root.project}")
    
    print("\n📌 ANSWER: PnPv5 exists because...")
    print("   - It evolved from PnPv4's weekly costing solution")
    print("   - Which was created to address Vista's fundamental costing gap")
    print("   - Vista could only do monthly costing, but business needed more granularity")
    print("   - The chain: Vista gap → PnPv4 weekly → PnPv5 real-time")


def query_what_addresses_costing_gap(storage: SQLiteBackend, vista_refs: dict):
    """
    Query: "What addresses the Vista costing gap?"
    
    Find all solutions that address this root cause.
    This demonstrates how a single ROOT can connect multiple projects.
    """
    print("\n" + "=" * 60)
    print("🔍 QUERY: What addresses the Vista costing gap?")
    print("=" * 60)
    
    root = storage.get_node(vista_refs["costing_gap_id"])
    print(f"\nThe ROOT: {root.what}")
    print(f"  Why: {root.why}")
    print(f"  Scope: 🌱 {root.scope.value} (shared knowledge)")
    
    # Find all edges pointing TO this root with ADDRESSES_ROOT
    incoming = storage.get_edges(
        vista_refs["costing_gap_id"],
        direction="incoming",
        edge_type=EdgeType.ADDRESSES_ROOT
    )
    
    print(f"\n📊 Found {len(incoming)} solutions that address this gap:\n")
    
    for i, edge in enumerate(incoming, 1):
        solution = storage.get_node(edge.source_id)
        print(f"  {i}. [{solution.project}] {solution.what}")
        if solution.how:
            print(f"     How: {solution.how}")
        if edge.metadata.get("how"):
            print(f"     Connection: {edge.metadata['how']}")
        print()
    
    print("📌 ANSWER: The Vista costing gap is addressed by:")
    print("   - PnPv4's weekly rollups (first solution)")
    print("   - PnPv5's real-time streaming (evolved solution)")
    print("   Both projects exist because of this single root cause!")


def query_roots_across_projects(storage: SQLiteBackend):
    """
    Query: "What shared knowledge (roots) exists across all projects?"
    
    Roots are the connective tissue - the fundamental insights and
    problems that explain relationships between projects.
    """
    print("\n" + "=" * 60)
    print("🔍 QUERY: What shared knowledge (roots) exists?")
    print("=" * 60)
    
    # Get all root-scoped nodes
    roots = storage.query_roots_only()
    
    print(f"\n🌱 Found {len(roots)} ROOT nodes (shared knowledge):\n")
    
    for root in roots:
        print(f"  Project: {root.project or 'global'}")
        print(f"  What: {root.what}")
        if root.why:
            print(f"  Why: {root.why}")
        
        # Count what addresses/exposes this root
        incoming = storage.get_edges(root.id, direction="incoming")
        if incoming:
            print(f"  Connected by: {len(incoming)} edges")
        print()
    
    print("📌 These roots explain WHY different projects exist and relate to each other.")


def main():
    """Run the Vista/PnP example."""
    print("=" * 60)
    print("🌳 ENGRAM: Vista/PnP Pattern Example")
    print("=" * 60)
    print("""
This example demonstrates the tree/root model:
  • Trees = Projects (Vista, PnPv4, PnPv5)
  • Branches = Project-specific knowledge
  • Roots = Shared knowledge (the WHY)

We'll show how PnPv5's existence traces back to Vista's costing gap.
""")
    
    # Use a temporary database for this example
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "vista_pnp.db")
        storage = SQLiteBackend(db_path)
        storage.initialize()
        traverser = MemoryTraverser(storage)
        
        try:
            # Create the project trees
            vista_refs = create_vista_tree(storage)
            pnpv4_refs = create_pnpv4_tree(storage, vista_refs)
            pnpv5_refs = create_pnpv5_tree(storage, pnpv4_refs, vista_refs)
            
            # Show project statistics
            print("\n" + "-" * 60)
            stats = storage.get_project_stats()
            print("\n📊 Project Statistics:")
            for proj in stats['projects']:
                print(f"  {proj['name']}: {proj['node_count']} nodes "
                      f"({proj['branch_count']} branches, {proj['root_count']} roots)")
            print(f"  Total shared roots: {stats['total_roots']}")
            
            # Run the queries
            query_why_pnpv5_exists(storage, traverser, pnpv5_refs)
            query_what_addresses_costing_gap(storage, vista_refs)
            query_roots_across_projects(storage)
            
            print("\n" + "=" * 60)
            print("✅ Example complete!")
            print("=" * 60)
            print("""
Key takeaways:
  1. ROOTS capture the fundamental "why" that transcends individual projects
  2. Multiple projects can ADDRESS_ROOT the same problem
  3. You can trace any project back to its root causes
  4. This enables questions like "Why does X exist?" and "What solves Y?"

Try it yourself:
  engram add "New feature" --project myproject --scope branch
  engram add "Why we built it" --project myproject --scope root
  engram query --roots-only
  engram trees
""")
            
        finally:
            storage.close()


if __name__ == "__main__":
    main()
