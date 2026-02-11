# Engram Architecture Philosophy

> The "why" behind Engram's design — not what it does, but why it exists.

**Author:** Josh Garrison  
**Captured:** 2026-02-11  
**Status:** Foundational Document

---

## The Core Problem

AI agents have great recall but terrible memory.

Vector databases give you semantic similarity — "find things that sound like this." But human memory isn't a search engine. When you remember your first car, you don't just retrieve a fact. You traverse associations: the smell of the seats, the road trip where it broke down, the mechanic who fixed it, the lesson you learned about checking oil.

That traversal — the causal chain — is what current AI memory systems lose.

---

## Edge Types as Causal Logic

Engram's edge types aren't just labels. They're **directional traversal logic**.

| Edge | Direction | What It Means |
|------|-----------|---------------|
| `caused_by` | Walk backward | "Why did this happen?" |
| `led_to` | Walk forward | "What did this cause?" |
| `contradicts` | Evolution marker | "What did we used to believe?" |
| `supersedes` | Temporal chain | "What replaced this?" |

When you ask "why did we choose Postgres?" — you're not doing semantic search. You're walking backward through `caused_by` edges until you hit the original decision node with its reasoning.

When you ask "what happened after we deployed?" — you're walking forward through `led_to` edges.

**Contradiction isn't failure.** A `contradicts` edge means understanding evolved. The old belief wasn't wrong at the time — it was right given what we knew. The edge preserves that evolution instead of erasing it.

---

## The "Revisit A" Pattern

This is the killer use case vectors can't solve:

```
1. Tried approach A
2. Failed because of gap X
3. Pivoted to approach B
4. Time passes...
5. New technology Z fills gap X
6. A is now viable!
```

But you only know A is viable **if you remember why you abandoned it**.

Flat retrieval might surface "we tried A once." It won't tell you:
- Why A failed
- What specific gap blocked it
- That the gap has been filled

Engram preserves the causal chain:
```
A-attempt --[led_to]--> Failure --[caused_by]--> Gap-X
Gap-X --[superseded_by]--> Tech-Z
```

Now when Tech-Z arrives, you can trace back: "What did Gap-X block?" and rediscover A.

This is how senior engineers think. They don't just remember what failed — they remember *why*, and they notice when the constraints change.

---

## Vector + Graph: The Hybrid Model

Neither vectors nor graphs alone are sufficient.

| Approach | Strength | Weakness |
|----------|----------|----------|
| **Vectors only** | Great recall (semantic similarity) | Semantic soup — no "why" |
| **Graph only** | Perfect coherence (explicit links) | Can't find what you didn't link |
| **Vector + Graph** | Recall AND coherence | Complexity (worth it) |

**Vectors are for finding.** "What memories are relevant to this query?"

**Graphs are for understanding.** "How do these memories connect? What's the causal chain?"

Use vectors to locate the neighborhood. Use graphs to traverse the meaning.

---

## The Control Plane Analogy

Think of a Cisco 6500 series switch with a supervisor card.

**The supervisor card (control plane):**
- Maintains state
- Detects failures
- Ensures coherence
- Handles reconciliation
- NOT in the path for every packet

**The line cards (data plane):**
- Forward packets at wire speed
- Do the actual work
- Operate independently for normal traffic

**Engram is the supervisor card.**

Agents are the data plane — they do the work. Engram doesn't intercept every operation. It handles:
- **Boot:** Load relevant context for the session
- **Failures:** "Why did this break? Have we seen this before?"
- **State changes:** Major decisions, architectural shifts
- **Reconciliation:** "These facts conflict — which is current?"

You don't route every packet through the supervisor. You don't log every agent turn to Engram. But when state matters — when coherence matters — that's when Engram engages.

---

## The "Not Code" Principle

Git captures **what changed**.

Engram captures **why, because of what, leading to what**.

```
Git commit: "Refactored auth module to use JWT"

Engram nodes:
- Decision: "Switch from sessions to JWT"
  - why: "Scaling issues with session store at 10k concurrent"
  - caused_by: "Production incident 2026-01-15"
  - led_to: "Auth refactor PR #847"
  - influenced_by: "Research on stateless auth patterns"
```

Git is the source of truth for code. Engram is the source of truth for **narrative** — the human-readable story of why the code exists.

This isn't for machines to parse. It's for humans (and agents acting like humans) to understand context. Plain language. Reasoning. The stuff that doesn't fit in commit messages.

---

## Summary: Why Engram Exists

1. **Memory needs structure.** Not just "similar things" but "connected things."

2. **Causality matters.** The "why" is often more valuable than the "what."

3. **Understanding evolves.** Contradictions aren't bugs — they're the record of learning.

4. **Not everything needs memory.** Control plane, not data plane. State changes, not every operation.

5. **Narrative over logs.** Human reasoning, not machine traces.

Engram isn't trying to remember everything. It's trying to remember what matters, and more importantly, *why it mattered*.

---

## See Also

- [SPEC.md](./SPEC.md) — Technical specification
- [AGENT-INTEGRATION.md](./AGENT-INTEGRATION.md) — How agents use Engram
- [AGENT-MEMORY.md](./AGENT-MEMORY.md) — Memory patterns for AI agents
