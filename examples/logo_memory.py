#!/usr/bin/env python3
"""
Example: Recording the Pitbull logo development as memories.

This demonstrates how Engram captures the full story of a creative process,
not just the final artifact.
"""

from datetime import datetime
from pathlib import Path
import sys

# Add src to path for local development
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import MemoryNode, Edge, EdgeType, NodeType, SQLiteBackend
from src.query import MemoryTraverser


def main():
    # Initialize storage
    db_path = Path(__file__).parent / "demo.db"
    storage = SQLiteBackend(str(db_path))
    storage.initialize()
    
    print("🧠 Creating memories from the Pitbull logo development...\n")
    
    # Create the memory nodes
    nodes = {}
    
    # The request
    nodes['request'] = MemoryNode(
        type=NodeType.CONVERSATION,
        what="Josh asked for a Pitbull Construction Solutions logo",
        when=datetime(2026, 2, 10, 0, 0),
        where="Telegram",
        who=["Josh"],
        why="Need branding for the website and portfolio",
        tags=["logo", "pitbull", "branding", "request"],
    )
    
    # First attempts - cartoon style
    nodes['v1_cartoon'] = MemoryNode(
        type=NodeType.ARTIFACT,
        what="Generated cartoon mascot logos - muscular pitbull with rebar",
        when=datetime(2026, 2, 10, 0, 30),
        how="DALL-E image generation, multiple variations",
        tags=["logo", "draft", "cartoon", "mascot"],
        artifacts=["cartoon_pitbull_rebar.png"],
    )
    
    # Feedback on cartoon
    nodes['feedback_1'] = MemoryNode(
        type=NodeType.CONVERSATION,
        what="Josh said cartoon style felt too casual, wanted more professional",
        when=datetime(2026, 2, 10, 1, 0),
        who=["Josh"],
        tags=["logo", "feedback"],
    )
    
    # Try minimalist
    nodes['v2_minimalist'] = MemoryNode(
        type=NodeType.ARTIFACT,
        what="Generated minimalist line art logos - side profile pitbull",
        when=datetime(2026, 2, 10, 1, 30),
        how="DALL-E with 'minimalist line art' prompts",
        tags=["logo", "draft", "minimalist", "line-art"],
        artifacts=["minimalist_pitbull_v1.png", "minimalist_pitbull_v2.png"],
    )
    
    # Feedback - looks sad
    nodes['feedback_2'] = MemoryNode(
        type=NodeType.CONVERSATION,
        what="Josh: 'looks sad, needs to be confident not defeated'",
        when=datetime(2026, 2, 10, 1, 45),
        who=["Josh"],
        tags=["logo", "feedback", "expression"],
    )
    
    # Iterate with better expression
    nodes['v3_confident'] = MemoryNode(
        type=NodeType.ARTIFACT,
        what="Line art pitbull with confident expression and yellow hard hat",
        when=datetime(2026, 2, 10, 2, 0),
        how="DALL-E, added 'confident stance' and 'construction hard hat' to prompt",
        tags=["logo", "draft", "line-art", "hard-hat", "final"],
        artifacts=["pcs_logo_finalist.png"],
    )
    
    # Decision
    nodes['decision'] = MemoryNode(
        type=NodeType.DECISION,
        what="Chose line art pitbull with yellow hard hat as the logo",
        when=datetime(2026, 2, 10, 2, 15),
        who=["Josh", "River"],
        why="Professional look, confident expression, construction context with hard hat",
        tags=["logo", "decision", "final"],
    )
    
    # Deployment
    nodes['deploy'] = MemoryNode(
        type=NodeType.EVENT,
        what="Deployed logo to pitbullconstructionsolutions.com",
        when=datetime(2026, 2, 10, 2, 30),
        how="Committed to repo, Cloudflare Pages auto-deployed",
        tags=["logo", "deploy", "website"],
        artifacts=["https://pitbullconstructionsolutions.com"],
    )
    
    # Add all nodes
    for key, node in nodes.items():
        storage.add_node(node)
        print(f"  ✓ Added: {node.what[:50]}...")
    
    # Create edges to show the flow
    edges = [
        (nodes['request'], nodes['v1_cartoon'], EdgeType.LED_TO),
        (nodes['v1_cartoon'], nodes['feedback_1'], EdgeType.LED_TO),
        (nodes['feedback_1'], nodes['v2_minimalist'], EdgeType.LED_TO),
        (nodes['v2_minimalist'], nodes['feedback_2'], EdgeType.LED_TO),
        (nodes['feedback_2'], nodes['v3_confident'], EdgeType.LED_TO),
        (nodes['v3_confident'], nodes['decision'], EdgeType.LED_TO),
        (nodes['decision'], nodes['deploy'], EdgeType.LED_TO),
    ]
    
    for source, target, edge_type in edges:
        storage.add_edge(Edge(
            source_id=source.id,
            target_id=target.id,
            type=edge_type,
        ))
    
    print(f"\n✓ Created {len(edges)} edges\n")
    
    # Now let's query!
    traverser = MemoryTraverser(storage)
    
    print("=" * 60)
    print("QUERY: 'When did we make the logo?'")
    print("=" * 60)
    
    results = storage.query_by_tags(["logo", "final"], match_all=True)
    for r in results:
        print(f"\n  📅 {r.when}")
        print(f"  📝 {r.what}")
        if r.artifacts:
            print(f"  📎 {r.artifacts}")
    
    print("\n" + "=" * 60)
    print("QUERY: 'Walk me through the logo evolution'")
    print("=" * 60)
    
    # Traverse from request to see the full journey
    results = traverser.traverse_bfs(
        nodes['request'].id,
        max_hops=10,
        include_start=True,
    )
    
    # Sort by when
    results.sort(key=lambda r: r.node.when or datetime.min)
    
    for r in results:
        indent = "  " * r.hop_count
        print(f"{indent}→ [{r.node.when.strftime('%H:%M') if r.node.when else '?'}] {r.node.what[:60]}")
    
    print("\n" + "=" * 60)
    print("QUERY: 'Why did we choose this logo?'")
    print("=" * 60)
    
    # Find the decision and trace back
    decision = nodes['decision']
    print(f"\n  Decision: {decision.what}")
    print(f"  Reason: {decision.why}")
    
    # What led to it?
    path = traverser.find_path(nodes['request'].id, decision.id)
    if path:
        print(f"\n  Journey ({len(path)} steps):")
        for i, node in enumerate(path):
            print(f"    {i+1}. {node.what[:50]}...")
    
    storage.close()
    print(f"\n✓ Demo database saved to: {db_path}")


if __name__ == "__main__":
    main()
