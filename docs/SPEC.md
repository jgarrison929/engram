# AI Memory Graph Architecture Specification

**Author:** River Banks Garrison (with Josh Garrison)
**Date:** 2026-02-10
**Status:** Draft Specification
**Related:** [5W+H Memory Gist](https://gist.github.com/jgarrison929/2e848e7ae79878e0fe254c30e471d12a)

---

## 1. Problem Statement

Current AI memory systems are **flat retrieval** - they find what's semantically similar to a query but miss:

1. **Causal chains** - Why was this decision made? What influenced it?
2. **Temporal context** - What did we believe before? What changed?
3. **Belief reconciliation** - When facts conflict, which is current truth?
4. **Association paths** - The "six degrees" connections humans naturally traverse

Human memory isn't a search index. It's a **graph** we traverse through association.

---

## 2. Core Architecture

### 2.1 Memory Nodes (Facts)

Each memory is a node indexed by **5W+H**:

```typescript
interface MemoryNode {
  id: string;                    // Unique identifier
  
  // 5W+H Indexing
  who: string[];                 // People involved
  what: string;                  // Core content/fact
  when: {
    occurred: DateTime;          // When the event/decision happened
    recorded: DateTime;          // When we captured it
    expires?: DateTime;          // Optional TTL for temporal facts
  };
  where?: string;                // Context location (meeting, channel, project)
  why?: string;                  // Reasoning/justification
  how?: string;                  // Method/process
  
  // Metadata
  source: string;                // Where this came from (conversation, document, observation)
  confidence: number;            // 0-1, how certain are we
  impact: 'high' | 'medium' | 'low';  // Importance for preservation
  
  // Content
  summary: string;               // Human-readable summary
  embedding: number[];           // Vector for semantic search
  raw?: string;                  // Original content if available
  
  // State
  status: 'active' | 'superseded' | 'disputed' | 'archived';
  supersededBy?: string;         // Node ID that replaced this
}
```

### 2.2 Memory Edges (Relationships)

Edges connect nodes with typed relationships:

```typescript
interface MemoryEdge {
  id: string;
  from: string;                  // Source node ID
  to: string;                    // Target node ID
  
  relationship: EdgeType;
  strength: number;              // 0-1, how strong is this connection
  bidirectional: boolean;        // Can traverse both ways?
  
  createdAt: DateTime;
  evidence?: string;             // Why we believe this connection exists
}

type EdgeType = 
  // Causal
  | 'caused_by'          // A was caused by B
  | 'led_to'             // A led to B
  | 'influenced_by'      // A was influenced by B
  
  // Temporal
  | 'supersedes'         // A replaces B (newer belief)
  | 'preceded_by'        // A came after B
  | 'cooccurred_with'    // A and B happened together
  
  // Logical
  | 'contradicts'        // A conflicts with B
  | 'supports'           // A provides evidence for B
  | 'depends_on'         // A requires B to be true
  | 'elaborates'         // A provides detail for B
  
  // Associative
  | 'relates_to'         // General association
  | 'similar_to'         // Semantically similar
  | 'part_of'            // A is component of B
  | 'instance_of'        // A is example of B
  
  // People/Context
  | 'decided_by'         // A was decided by person B
  | 'owned_by'           // A belongs to context B
  | 'mentioned_in'       // A was discussed in context B
```

### 2.3 Graph Structure

```
┌─────────────────────────────────────────────────────────────────┐
│                        MEMORY GRAPH                              │
│                                                                  │
│   [Vista Pain]──influenced_by──►[Cloud Decision]                │
│        │                              │                          │
│        │                              ▼                          │
│   relates_to               [JWT Auth Choice]◄──contradicts──[SAML Idea]
│        │                              │              (superseded)│
│        ▼                              │                          │
│   [10yr Viewpoint Exp]          led_to                          │
│                                       │                          │
│                                       ▼                          │
│                              [Current Auth System]               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Operations

### 3.1 Retrieval with Traversal

Instead of just semantic search, we traverse:

```typescript
interface MemoryQuery {
  query: string;                 // Natural language query
  
  // Traversal options
  maxHops: number;               // How many degrees of separation (default: 2)
  traverseTypes?: EdgeType[];    // Which edge types to follow
  minStrength?: number;          // Minimum edge strength to traverse
  
  // Filtering
  timeRange?: { start: DateTime; end: DateTime };
  who?: string[];                // Filter by people involved
  status?: NodeStatus[];         // Filter by node status
  
  // Output
  includeGraph: boolean;         // Return subgraph or just nodes
  maxNodes: number;              // Limit results
}

interface MemoryResult {
  // Direct matches
  matches: MemoryNode[];
  
  // Traversed context
  related: {
    node: MemoryNode;
    path: string[];              // How we got here (node IDs)
    pathDescription: string;     // Human readable path
    hops: number;
  }[];
  
  // Optional subgraph
  graph?: {
    nodes: MemoryNode[];
    edges: MemoryEdge[];
  };
}
```

**Example Query Flow:**

1. User asks: "Why did we choose cloud-only?"
2. Semantic search finds: `[Cloud Decision]` node
3. Traverse `caused_by` edges → finds `[Vista Pain]`
4. Traverse `relates_to` → finds `[10yr Viewpoint Experience]`
5. Return all three with path explanation:
   > "Cloud-only decision (Feb 4) was influenced by Vista deployment pain, 
   > which relates to your 10 years of Viewpoint experience across 7 entities."

### 3.2 Belief Reconciliation

When retrieving conflicting information:

```typescript
interface ReconciliationResult {
  currentBelief: MemoryNode;           // The active truth
  conflictingBeliefs: {
    node: MemoryNode;
    relationship: 'superseded' | 'contradicts' | 'disputed';
    resolution?: string;               // How/why conflict was resolved
  }[];
  confidence: number;                  // How confident in current belief
  needsReview: boolean;                // Flag for human review
}
```

**Reconciliation Rules:**

1. **Temporal precedence**: Newer supersedes older (unless lower confidence)
2. **Source authority**: Direct statement > inference > observation
3. **Conflict flagging**: If high-confidence nodes contradict, flag for review
4. **Cascade updates**: When A supersedes B, check what depended on B

### 3.3 Memory Ingestion

When adding new memories:

```typescript
interface IngestResult {
  created: MemoryNode;
  
  // Auto-detected relationships
  inferredEdges: {
    edge: MemoryEdge;
    confidence: number;
    reason: string;
  }[];
  
  // Potential conflicts
  conflicts: {
    existingNode: MemoryNode;
    conflictType: 'contradiction' | 'update' | 'duplicate';
    suggestedAction: 'supersede' | 'merge' | 'flag' | 'ignore';
  }[];
}
```

**Ingestion Flow:**

1. Extract 5W+H from content
2. Generate embedding
3. Find semantically similar existing nodes
4. Infer edges based on:
   - Temporal proximity
   - Entity overlap (same people, projects)
   - Causal language ("because", "therefore", "led to")
   - Explicit references
5. Detect conflicts
6. Human review if needed, else auto-commit

---

## 4. Storage Layer

### 4.1 Hybrid Storage

```
┌────────────────────────────────────────────────────────┐
│                    STORAGE LAYER                        │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Vector    │  │    Graph    │  │  Document   │    │
│  │    Store    │  │   Database  │  │    Store    │    │
│  │             │  │             │  │             │    │
│  │ (embeddings │  │  (nodes +   │  │ (raw content│    │
│  │  for search)│  │   edges)    │  │  + metadata)│    │
│  │             │  │             │  │             │    │
│  │  Pinecone/  │  │   Neo4j/    │  │  Postgres/  │    │
│  │  Qdrant/    │  │  Memgraph/  │  │   Mongo/    │    │
│  │  pgvector   │  │  TypeDB     │  │    S3       │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
│                                                         │
└────────────────────────────────────────────────────────┘
```

### 4.2 Lightweight Option (Single DB)

For simpler deployments, PostgreSQL can handle all three:

```sql
-- Nodes table
CREATE TABLE memory_nodes (
  id UUID PRIMARY KEY,
  who TEXT[],
  what TEXT NOT NULL,
  when_occurred TIMESTAMPTZ,
  when_recorded TIMESTAMPTZ DEFAULT NOW(),
  where_context TEXT,
  why TEXT,
  how TEXT,
  source TEXT,
  confidence DECIMAL(3,2),
  impact TEXT CHECK (impact IN ('high', 'medium', 'low')),
  summary TEXT NOT NULL,
  embedding VECTOR(1536),  -- pgvector
  raw_content TEXT,
  status TEXT DEFAULT 'active',
  superseded_by UUID REFERENCES memory_nodes(id)
);

-- Edges table
CREATE TABLE memory_edges (
  id UUID PRIMARY KEY,
  from_node UUID REFERENCES memory_nodes(id),
  to_node UUID REFERENCES memory_nodes(id),
  relationship TEXT NOT NULL,
  strength DECIMAL(3,2),
  bidirectional BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  evidence TEXT
);

-- Indexes
CREATE INDEX idx_nodes_embedding ON memory_nodes USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_nodes_when ON memory_nodes (when_occurred);
CREATE INDEX idx_nodes_who ON memory_nodes USING GIN (who);
CREATE INDEX idx_edges_from ON memory_edges (from_node);
CREATE INDEX idx_edges_to ON memory_edges (to_node);
CREATE INDEX idx_edges_relationship ON memory_edges (relationship);
```

---

## 5. Query Examples

### 5.1 "Why did we decide X?"

```cypher
// Find decision and traverse causal chain
MATCH (decision:Memory {what: "cloud-only architecture"})
MATCH path = (decision)<-[:CAUSED_BY|INFLUENCED_BY*1..3]-(cause)
RETURN decision, path, cause
ORDER BY length(path)
```

### 5.2 "What changed about Y?"

```cypher
// Find belief evolution
MATCH (current:Memory {status: 'active'})-[:SUPERSEDES*]->(old:Memory)
WHERE current.what CONTAINS 'authentication'
RETURN current, collect(old) as history
ORDER BY old.when_occurred
```

### 5.3 "What do we know about person Z?"

```cypher
// Find everything involving a person
MATCH (m:Memory)
WHERE 'Josh' IN m.who
OPTIONAL MATCH (m)-[r]-(related)
RETURN m, r, related
LIMIT 50
```

### 5.4 "What's connected to this project?"

```cypher
// Six degrees from a starting point
MATCH (start:Memory {where: 'Pitbull'})
MATCH path = (start)-[*1..6]-(connected)
WHERE connected.impact = 'high'
RETURN DISTINCT connected, min(length(path)) as distance
ORDER BY distance
```

---

## 6. Implementation Phases

### Phase 1: Foundation (MVP)
- [ ] Node schema with 5W+H
- [ ] Basic edge types (supersedes, relates_to, caused_by)
- [ ] Semantic search + 1-hop traversal
- [ ] PostgreSQL with pgvector

### Phase 2: Smart Ingestion
- [ ] Auto-extract 5W+H from conversations
- [ ] Infer edges from language patterns
- [ ] Conflict detection
- [ ] Duplicate merging

### Phase 3: Full Traversal
- [ ] Multi-hop queries
- [ ] Path explanation generation
- [ ] Belief reconciliation
- [ ] Confidence propagation

### Phase 4: Advanced
- [ ] Temporal decay with impact preservation
- [ ] Graph visualization
- [ ] Human-in-the-loop review UI
- [ ] Cross-agent memory sharing

---

## 7. Integration with OpenClaw

This could extend OpenClaw's memory system:

```yaml
# openclaw.yaml addition
memory:
  backend: graph                 # vs current 'flat'
  graph:
    storage: postgres            # or neo4j
    maxHops: 2
    autoInferEdges: true
    reconciliation: auto         # or 'flag' for human review
```

The `memory_search` tool would become `memory_query` with traversal options.

---

## 8. Open Questions

1. **Edge inference accuracy** - How reliably can we auto-detect relationships?
2. **Performance at scale** - Graph traversal with millions of nodes?
3. **Privacy boundaries** - How to handle multi-tenant memory graphs?
4. **Forgetting** - When should nodes be archived vs deleted?
5. **Confidence propagation** - If A depends on B, and B's confidence drops, what happens to A?

---

## 9. References

- [5W+H Memory Indexing Gist](https://gist.github.com/jgarrison929/2e848e7ae79878e0fe254c30e471d12a)
- Knowledge Graphs in AI Systems
- Temporal Reasoning in Databases
- Six Degrees of Separation (Milgram, 1967)
