#!/usr/bin/env python3
"""
Example: Using AgentMemory for AI agent integration.

This shows how an AI agent might use Engram to maintain
persistent memory across sessions.
"""

import tempfile
from pathlib import Path

from engram import AgentMemory


def main():
    # Use a temporary database for this example
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "agent_memory.db")
        
        print("=== Agent Memory Example ===\n")
        
        with AgentMemory(db_path) as memory:
            # =====================================================
            # Session Start: Load Context
            # =====================================================
            print("1. Loading context from previous sessions...")
            context = memory.load_context(tags=["project"], days=30)
            print(f"   Found {len(context)} relevant memories\n")
            
            # =====================================================
            # Log Tasks as We Complete Them
            # =====================================================
            print("2. Logging completed tasks...")
            
            task1_id = memory.log_task(
                what="Set up project repository and CI/CD",
                tags=["project", "infrastructure", "setup"],
                artifacts=["github.com/example/repo", ".github/workflows/ci.yml"],
                how="Created GitHub repo, added actions workflow",
            )
            print(f"   ✓ Task logged: {str(task1_id)[:8]}")
            
            task2_id = memory.log_task(
                what="Implemented user authentication",
                tags=["project", "auth", "backend"],
                artifacts=["src/auth.py", "tests/test_auth.py"],
                link_to=task1_id,  # This follows from the setup task
            )
            print(f"   ✓ Task logged: {str(task2_id)[:8]}\n")
            
            # =====================================================
            # Log Insights/Lessons Learned
            # =====================================================
            print("3. Recording lessons learned...")
            
            # This auto-links to the last task (auth implementation)
            insight_id = memory.log_insight(
                what="JWT refresh tokens should be stored in httpOnly cookies, not localStorage",
                tags=["security", "auth", "best-practice"],
                why="localStorage is vulnerable to XSS attacks",
                how="Use httpOnly cookies with SameSite=Strict",
            )
            print(f"   ✓ Insight logged: {str(insight_id)[:8]}\n")
            
            # =====================================================
            # Log Decisions
            # =====================================================
            print("4. Recording architectural decisions...")
            
            decision_id = memory.log_decision(
                what="Use PostgreSQL instead of MongoDB",
                why="Better support for complex queries and joins; ACID compliance for financial data",
                alternatives=["MongoDB", "MySQL", "SQLite"],
                tags=["architecture", "database", "decision"],
            )
            print(f"   ✓ Decision logged: {str(decision_id)[:8]}\n")
            
            # =====================================================
            # Search and Query
            # =====================================================
            print("5. Searching memories...")
            
            auth_memories = memory.search("authentication")
            print(f"   Found {len(auth_memories)} memories about authentication")
            
            # =====================================================
            # Find Related Context
            # =====================================================
            print("\n6. Finding related memories...")
            
            related = memory.find_related(task2_id, max_hops=2)
            print(f"   Found {len(related)} memories related to auth implementation:")
            for r in related:
                what_preview = r.what[:50] + "..." if len(r.what) > 50 else r.what
                print(f"      - [{r.type.value}] {what_preview}")
            
            # =====================================================
            # Get Recent Tasks
            # =====================================================
            print("\n7. Getting recent tasks...")
            
            recent_tasks = memory.get_recent_tasks(limit=5)
            print(f"   {len(recent_tasks)} recent tasks:")
            for t in recent_tasks:
                print(f"      - {t.what[:50]}...")
            
            # =====================================================
            # Get Insights
            # =====================================================
            print("\n8. Getting security insights...")
            
            insights = memory.get_insights(tags=["security"])
            print(f"   {len(insights)} security insights:")
            for i in insights:
                print(f"      - {i.what[:60]}...")
            
        print("\n=== Done! ===")
        print("The AgentMemory context manager automatically closes the database.")


if __name__ == "__main__":
    main()
