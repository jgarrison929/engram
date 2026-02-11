# Engram Agent Integration Design

> How River (and other agents) should use Engram for context-aware decision making

## Problem

1. **Context loss on compaction:** Heavy coding sessions lose 180K+ tokens per compaction
2. **Flat file memory:** MEMORY.md/daily logs lack causal connections
3. **Repeated mistakes:** Without "why" history, agents retry failed approaches
4. **Token waste:** Re-reading large files every session burns context

## Solution: Token-Efficient Engram Queries

### When to Query Engram

**Before major actions:**
- Starting a new task → `engram query "<task keywords>" --hops 1`
- Making architectural decisions → `engram query "decision <topic>"`
- Encountering errors → `engram query "error <error type>"`
- Working on a module → `engram query "module:<name>"`

**NOT every turn** - only when context might help.

### Query Patterns (Low Token Cost)

```bash
# Quick relevance check (returns IDs + snippets, ~50-100 tokens)
engram query "self-hosted runners" --limit 3

# If relevant, get full context (~200-500 tokens)
engram show <id>

# Trace causality for "why" questions
engram path <decision-id> <outcome-id>
```

### Logging Patterns (Write-Through)

**Always log to Engram when:**
1. Making a decision with reasoning
2. Completing a significant task
3. Encountering and solving a problem
4. Learning something new (insight)

**Template:**
```bash
engram add "<what happened>" \
  --type decision|event|insight \
  --why "<reasoning>" \
  --how "<method>" \
  --tags <relevant,tags>
```

**Link to prior context:**
```bash
engram add "<outcome>" --link-to <prior-decision-id>
```

## Integration Points

### 1. Session Start (Warm Context)

At session start, query recent relevant memories:
```bash
# Get last 7 days of activity
engram query --since "7 days ago" --limit 10

# Or tag-based for specific project
engram query --tags pitbull --since "3 days ago"
```

This replaces reading entire daily log files.

### 2. Pre-Action Check

Before executing potentially risky/repeated actions:
```python
# Pseudo-code for agent integration
def before_action(action_type, context):
    # Check if we've done this before
    results = engram.query(f"{action_type} {context}", limit=3)
    if results:
        for r in results:
            if r.type == "insight" or "failed" in r.what.lower():
                # We have relevant history - review it
                return engram.show(r.id)
    return None  # No relevant history, proceed
```

### 3. Post-Compaction Recovery

After context compaction, the compaction summary is limited. Engram preserves:
- Detailed reasoning chains
- Error messages and solutions
- The "why" behind decisions

Query Engram to recover context lost in compaction:
```bash
engram query --since "4 hours ago" --hops 2
```

### 4. Sub-Agent Handoff

When spawning sub-agents, pass relevant Engram context:
```bash
# Export relevant memories for sub-agent
engram query "module:contracts" --json > /tmp/context.json

# Sub-agent imports or queries same DB
```

## Token Budget

| Operation | Estimated Tokens |
|-----------|------------------|
| Query (3 results) | 50-100 |
| Show (1 memory) | 100-300 |
| Path (3-hop) | 200-500 |
| Add (with metadata) | 50-100 |

**Target:** <500 tokens per Engram interaction
**Savings:** Avoids re-reading 2000+ token daily logs

## Caching Strategy

For frequently accessed context:
1. Cache recent query results in session
2. Only re-query if >1 hour old or explicitly needed
3. Use `engram stats` for quick health check (no content)

## Implementation Phases

### Phase 1: Manual Integration (Current)
- Add memories manually during significant events
- Query before major decisions
- Log in daily files AND Engram (dual-write)

### Phase 2: Automatic Logging
- Hook into compaction events
- Auto-log decisions from conversation
- Parse and import new commits automatically

### Phase 3: Full Integration
- Engram query as standard pre-action step
- Replace daily log reading with Engram queries
- Sub-agent memory sharing via Engram

---

*Designed Feb 11, 2026 by River Banks Garrison*
