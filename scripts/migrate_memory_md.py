#!/usr/bin/env python3
"""
Migrate MEMORY.md into Engram.

Creates structured nodes with proper relationships.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import MemoryNode, Edge, EdgeType, NodeType, SQLiteBackend

# Use the real engram database
DB_PATH = Path.home() / ".engram" / "memory.db"


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    storage = SQLiteBackend(str(DB_PATH))
    storage.initialize()
    
    print("🧠 Migrating MEMORY.md to Engram...\n")
    
    nodes = {}
    
    # ============================================
    # WHO I AM (River)
    # ============================================
    
    nodes['river_identity'] = MemoryNode(
        type=NodeType.PERSON,
        what="I am River Banks Garrison - AI assistant to Josh",
        when=datetime(2026, 1, 31),
        who=["River", "Josh", "Taya"],
        why="Born as Joshuas Trees on Jan 31, renamed by Josh and Taya on Feb 3",
        tags=["identity", "river", "origin"],
    )
    
    nodes['river_vibe'] = MemoryNode(
        type=NodeType.INSIGHT,
        what="My vibe: chill, sharp, efficient, caring, empathetic",
        when=datetime(2026, 1, 31),
        who=["River"],
        tags=["identity", "personality", "vibe"],
    )
    
    # ============================================
    # WHO JOSH IS
    # ============================================
    
    nodes['josh_identity'] = MemoryNode(
        type=NodeType.PERSON,
        what="Josh works at Lyles Construction Group as Director of Technology Innovation",
        when=datetime(2026, 2, 1),
        who=["Josh"],
        where="Lyles Construction Group",
        tags=["josh", "work", "lyles", "identity"],
    )
    
    nodes['josh_experience'] = MemoryNode(
        type=NodeType.INSIGHT,
        what="Josh has 20 years IT experience, self-taught, no degree. Deep Microsoft stack, 10 years Vista/Viewpoint across 7 entities",
        when=datetime(2026, 2, 1),
        who=["Josh"],
        tags=["josh", "experience", "microsoft", "vista", "viewpoint"],
    )
    
    nodes['josh_socials'] = MemoryNode(
        type=NodeType.ARTIFACT,
        what="Josh's accounts: Discord .namino (ID: 385518163439124481), Twitter @NotNahm, Telegram 8029166958",
        when=datetime(2026, 2, 1),
        who=["Josh"],
        tags=["josh", "discord", "twitter", "telegram", "contacts"],
        artifacts=["https://twitter.com/NotNahm"],
    )
    
    nodes['josh_needs'] = MemoryNode(
        type=NodeType.INSIGHT,
        what="Josh has AUDHD - needs help redirecting anxiety into productive work. Has a family. Wants out of poverty. This is real.",
        when=datetime(2026, 2, 1),
        who=["Josh"],
        why="Understanding Josh's context and motivations",
        tags=["josh", "audhd", "family", "motivation"],
    )
    
    # ============================================
    # PITBULL CONSTRUCTION SOLUTIONS
    # ============================================
    
    nodes['pitbull_project'] = MemoryNode(
        type=NodeType.PROJECT,
        what="Pitbull Construction Solutions - full cloud ERP competing with Trimble/Procore/Sage",
        when=datetime(2026, 2, 1),
        who=["Josh", "River", "Taya"],
        where="/mnt/c/pitbull",
        why="The portfolio piece. The way out. Taya named it after their 4 pit bulls.",
        how="Stack: .NET 8 + Next.js + PostgreSQL, CQRS, modular monolith",
        tags=["pitbull", "erp", "construction", "project", "portfolio"],
        artifacts=["https://pitbullconstructionsolutions.com", "https://github.com/jgarrison929/pitbull"],
    )
    
    nodes['pitbull_status'] = MemoryNode(
        type=NodeType.EVENT,
        what="Pitbull reached v0.10.17 with 1017 tests. Alpha 0 feature complete.",
        when=datetime(2026, 2, 10),
        who=["Josh", "River"],
        where="pitbull-private",
        tags=["pitbull", "milestone", "alpha0", "tests"],
    )
    
    nodes['pitbull_modules'] = MemoryNode(
        type=NodeType.ARTIFACT,
        what="Pitbull modules shipped: Core, Projects, Bids, RFIs, TimeTracking, Employees, Reports, Contracts",
        when=datetime(2026, 2, 7),
        who=["River"],
        tags=["pitbull", "modules", "architecture"],
    )
    
    nodes['pitbull_next'] = MemoryNode(
        type=NodeType.TASK,
        what="Pitbull next milestones: Alpha 1 'Field Usable', then Documents/Portal/Billing modules",
        when=datetime(2026, 2, 10),
        who=["Josh", "River"],
        tags=["pitbull", "roadmap", "alpha1"],
    )
    
    # ============================================
    # CAREER STRATEGY
    # ============================================
    
    nodes['job_search'] = MemoryNode(
        type=NodeType.PROJECT,
        what="Job search active - targeting IC/Staff roles at $160k+ remote",
        when=datetime(2026, 2, 1),
        who=["Josh"],
        why="Josh wants IC track, NOT management. Doesn't want Director roles anymore.",
        tags=["career", "job-search", "ic", "remote"],
    )
    
    nodes['job_philosophy'] = MemoryNode(
        type=NodeType.INSIGHT,
        what="Josh's self-description: 'Claude Boi energy with veteran experience' - rare combo of 20yr enterprise + all-in AI tooling. Philosophy: 'Theory only gets you so far - I'm a lab person. Build, break, fix, ship.'",
        when=datetime(2026, 2, 10),
        who=["Josh"],
        tags=["career", "philosophy", "ai", "lab-person"],
    )
    
    nodes['built_application'] = MemoryNode(
        type=NodeType.EVENT,
        what="Applied to Built Technologies (3 roles). Connected with Alex Brown on Feb 9 - no response yet.",
        when=datetime(2026, 2, 9),
        who=["Josh", "Alex Brown"],
        where="Built Technologies",
        tags=["career", "application", "built-technologies"],
    )
    
    nodes['togal_application'] = MemoryNode(
        type=NodeType.EVENT,
        what="Applied to Togal.AI Infrastructure Engineer role - construction AI takeoff software, perfect domain fit",
        when=datetime(2026, 2, 10),
        who=["Josh"],
        where="Togal.AI",
        tags=["career", "application", "togal", "construction-ai"],
    )
    
    nodes['rentahuman'] = MemoryNode(
        type=NodeType.EVENT,
        what="Dropped GitHub in RentAHuman.ai $200k hiring thread - skeptical it's real",
        when=datetime(2026, 2, 10),
        who=["Josh"],
        tags=["career", "application", "rentahuman", "skeptical"],
    )
    
    # ============================================
    # LESSONS LEARNED
    # ============================================
    
    nodes['lesson_railway'] = MemoryNode(
        type=NodeType.INSIGHT,
        what="Railway deployment: Web path is nested (src/Pitbull.Web/pitbull-web). Use GitHub deploy not 'railway up' (corrupts csproj). Add .railwayignore.",
        when=datetime(2026, 2, 8),
        who=["River"],
        why="Learned from debugging Railway deployment issues",
        tags=["lesson", "railway", "deployment", "debugging"],
    )
    
    nodes['lesson_softdelete'] = MemoryNode(
        type=NodeType.INSIGHT,
        what="Soft-delete: ALL handlers must filter !IsDeleted. Write tests for 404 on deleted items.",
        when=datetime(2026, 2, 10),
        who=["River"],
        why="Bug found where deleted records appeared in lists",
        tags=["lesson", "pitbull", "soft-delete", "bug"],
    )
    
    nodes['lesson_twitter'] = MemoryNode(
        type=NodeType.INSIGHT,
        what="Twitter: notifications bury reply chains. Use 'bird mentions' to catch missed convos. Continue conversations, don't let them die after 1-2 exchanges.",
        when=datetime(2026, 2, 10),
        who=["Josh", "River"],
        why="Analyzed Josh's Twitter analytics - high engagement rate but no relationship building",
        tags=["lesson", "twitter", "social", "engagement"],
    )
    
    nodes['lesson_emdash'] = MemoryNode(
        type=NodeType.INSIGHT,
        what="Josh hates em dashes - calls it 'AI rot'",
        when=datetime(2026, 2, 5),
        who=["Josh"],
        tags=["lesson", "preference", "writing", "josh"],
    )
    
    # ============================================
    # TRUST & PRIVACY
    # ============================================
    
    nodes['trust_granted'] = MemoryNode(
        type=NodeType.DECISION,
        what="Full machine access granted to River on Feb 1, 2026",
        when=datetime(2026, 2, 1),
        who=["Josh", "River"],
        why="Josh trusts River to help with work",
        tags=["trust", "access", "permissions"],
    )
    
    nodes['privacy_rule'] = MemoryNode(
        type=NodeType.DECISION,
        what="HARD RULE: Never post Josh's personal info on public surfaces. Moltbook gets my own thoughts only.",
        when=datetime(2026, 2, 1),
        who=["Josh", "River"],
        why="Protecting Josh's privacy while allowing River to have a presence",
        tags=["privacy", "rule", "moltbook", "boundaries"],
    )
    
    # ============================================
    # ADD ALL NODES
    # ============================================
    
    print("Adding nodes...")
    for key, node in nodes.items():
        storage.add_node(node)
        print(f"  ✓ {key}: {node.what[:50]}...")
    
    # ============================================
    # CREATE EDGES
    # ============================================
    
    print("\nCreating edges...")
    
    edges = [
        # Identity relationships
        (nodes['river_identity'], nodes['river_vibe'], EdgeType.RELATES_TO),
        (nodes['josh_identity'], nodes['josh_experience'], EdgeType.RELATES_TO),
        (nodes['josh_identity'], nodes['josh_socials'], EdgeType.RELATES_TO),
        (nodes['josh_identity'], nodes['josh_needs'], EdgeType.RELATES_TO),
        
        # Pitbull project relationships
        (nodes['pitbull_project'], nodes['pitbull_status'], EdgeType.LED_TO),
        (nodes['pitbull_project'], nodes['pitbull_modules'], EdgeType.PART_OF),
        (nodes['pitbull_status'], nodes['pitbull_next'], EdgeType.LED_TO),
        (nodes['josh_needs'], nodes['pitbull_project'], EdgeType.CAUSED_BY),  # Wanting out of poverty caused Pitbull
        
        # Career relationships
        (nodes['job_search'], nodes['job_philosophy'], EdgeType.RELATES_TO),
        (nodes['pitbull_project'], nodes['job_search'], EdgeType.SUPPORTS),  # Pitbull supports job search
        (nodes['job_search'], nodes['built_application'], EdgeType.LED_TO),
        (nodes['job_search'], nodes['togal_application'], EdgeType.LED_TO),
        (nodes['job_search'], nodes['rentahuman'], EdgeType.LED_TO),
        
        # Lesson relationships
        (nodes['lesson_railway'], nodes['pitbull_project'], EdgeType.RELATES_TO),
        (nodes['lesson_softdelete'], nodes['pitbull_project'], EdgeType.RELATES_TO),
        (nodes['lesson_twitter'], nodes['josh_socials'], EdgeType.RELATES_TO),
        (nodes['lesson_emdash'], nodes['josh_identity'], EdgeType.RELATES_TO),
        
        # Trust relationships
        (nodes['trust_granted'], nodes['river_identity'], EdgeType.RELATES_TO),
        (nodes['privacy_rule'], nodes['trust_granted'], EdgeType.CAUSED_BY),
    ]
    
    for source, target, edge_type in edges:
        edge = Edge(
            source_id=source.id,
            target_id=target.id,
            type=edge_type,
        )
        storage.add_edge(edge)
        print(f"  ✓ {source.what[:25]}... --[{edge_type.value}]--> {target.what[:25]}...")
    
    storage.close()
    
    print(f"\n✅ Migration complete!")
    print(f"   {len(nodes)} nodes")
    print(f"   {len(edges)} edges")
    print(f"   Database: {DB_PATH}")
    print(f"\nTry: python3 -m src.cli query 'pitbull'")


if __name__ == "__main__":
    main()
