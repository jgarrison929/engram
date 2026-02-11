"""
Storage backends for Engram.

Abstracts persistence so we can swap SQLite/Postgres/Neo4j.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from .models import MemoryNode, Edge, EdgeType, QueryResult


class StorageBackend(ABC):
    """Abstract base for storage backends."""
    
    @abstractmethod
    def initialize(self) -> None:
        """Set up storage (create tables, indexes, etc.)."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Clean up resources."""
        pass
    
    # Node operations
    @abstractmethod
    def add_node(self, node: MemoryNode) -> UUID:
        """Store a memory node. Returns the node ID."""
        pass
    
    @abstractmethod
    def get_node(self, node_id: UUID) -> Optional[MemoryNode]:
        """Retrieve a node by ID."""
        pass
    
    @abstractmethod
    def update_node(self, node: MemoryNode) -> bool:
        """Update an existing node. Returns success."""
        pass
    
    @abstractmethod
    def delete_node(self, node_id: UUID) -> bool:
        """Delete a node and its edges. Returns success."""
        pass
    
    # Edge operations
    @abstractmethod
    def add_edge(self, edge: Edge) -> UUID:
        """Create a relationship between nodes."""
        pass
    
    @abstractmethod
    def get_edges(
        self,
        node_id: UUID,
        direction: str = "both",  # "outgoing", "incoming", "both"
        edge_type: Optional[EdgeType] = None
    ) -> list[Edge]:
        """Get edges connected to a node."""
        pass
    
    @abstractmethod
    def delete_edge(self, edge_id: UUID) -> bool:
        """Remove an edge."""
        pass
    
    # Query operations
    @abstractmethod
    def query_by_time(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100
    ) -> list[MemoryNode]:
        """Find nodes within a time range."""
        pass
    
    @abstractmethod
    def query_by_tags(
        self,
        tags: list[str],
        match_all: bool = False,
        limit: int = 100
    ) -> list[MemoryNode]:
        """Find nodes with specific tags."""
        pass
    
    @abstractmethod
    def query_by_text(
        self,
        query: str,
        limit: int = 100
    ) -> list[MemoryNode]:
        """Full-text search across node content."""
        pass
    
    @abstractmethod
    def query_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7
    ) -> list[QueryResult]:
        """Semantic similarity search."""
        pass


class SQLiteBackend(StorageBackend):
    """SQLite storage backend - good for local/single-agent use."""
    
    def __init__(self, db_path: str = "engram.db"):
        self.db_path = db_path
        self.conn = None
    
    def initialize(self) -> None:
        import sqlite3
        import json
        
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # Enable JSON functions
        self.conn.execute("PRAGMA journal_mode=WAL")
        
        # Create tables
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                what TEXT NOT NULL,
                when_ts TEXT,
                where_ctx TEXT,
                who TEXT,  -- JSON array
                why TEXT,
                how TEXT,
                tags TEXT,  -- JSON array
                artifacts TEXT,  -- JSON array
                embedding BLOB,  -- Serialized float array
                confidence REAL DEFAULT 1.0,
                source TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS edges (
                id TEXT PRIMARY KEY,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                type TEXT NOT NULL,
                weight REAL DEFAULT 1.0,
                metadata TEXT,  -- JSON
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
            );
            
            -- Indexes for common queries
            CREATE INDEX IF NOT EXISTS idx_nodes_when ON nodes(when_ts);
            CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
            CREATE INDEX IF NOT EXISTS idx_nodes_created ON nodes(created_at);
            CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
            CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
            CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(type);
            
            -- Full-text search
            CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                what, why, how, tags,
                content='nodes',
                content_rowid='rowid'
            );
            
            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
                INSERT INTO nodes_fts(rowid, what, why, how, tags)
                VALUES (NEW.rowid, NEW.what, NEW.why, NEW.how, NEW.tags);
            END;
            
            CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
                INSERT INTO nodes_fts(nodes_fts, rowid, what, why, how, tags)
                VALUES ('delete', OLD.rowid, OLD.what, OLD.why, OLD.how, OLD.tags);
            END;
            
            CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
                INSERT INTO nodes_fts(nodes_fts, rowid, what, why, how, tags)
                VALUES ('delete', OLD.rowid, OLD.what, OLD.why, OLD.how, OLD.tags);
                INSERT INTO nodes_fts(rowid, what, why, how, tags)
                VALUES (NEW.rowid, NEW.what, NEW.why, NEW.how, NEW.tags);
            END;
        """)
        
        self.conn.commit()
    
    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def add_node(self, node: MemoryNode) -> UUID:
        import json
        
        self.conn.execute("""
            INSERT INTO nodes (id, type, what, when_ts, where_ctx, who, why, how,
                             tags, artifacts, embedding, confidence, source,
                             created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(node.id),
            node.type.value,
            node.what,
            node.when.isoformat() if node.when else None,
            node.where,
            json.dumps(node.who),
            node.why,
            node.how,
            json.dumps(node.tags),
            json.dumps(node.artifacts),
            self._serialize_embedding(node.embedding),
            node.confidence,
            node.source,
            node.created_at.isoformat(),
            node.updated_at.isoformat()
        ))
        self.conn.commit()
        return node.id
    
    def get_node(self, node_id: UUID) -> Optional[MemoryNode]:
        import json
        from .models import NodeType
        
        row = self.conn.execute(
            "SELECT * FROM nodes WHERE id = ?",
            (str(node_id),)
        ).fetchone()
        
        if not row:
            return None
        
        return MemoryNode(
            id=UUID(row['id']),
            type=NodeType(row['type']),
            what=row['what'],
            when=datetime.fromisoformat(row['when_ts']) if row['when_ts'] else None,
            where=row['where_ctx'],
            who=json.loads(row['who']) if row['who'] else [],
            why=row['why'],
            how=row['how'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            artifacts=json.loads(row['artifacts']) if row['artifacts'] else [],
            embedding=self._deserialize_embedding(row['embedding']),
            confidence=row['confidence'],
            source=row['source'],
            created_at=datetime.fromisoformat(row['created_at']),
            updated_at=datetime.fromisoformat(row['updated_at'])
        )
    
    def update_node(self, node: MemoryNode) -> bool:
        import json
        
        node.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
        
        cursor = self.conn.execute("""
            UPDATE nodes SET
                type = ?, what = ?, when_ts = ?, where_ctx = ?, who = ?,
                why = ?, how = ?, tags = ?, artifacts = ?, embedding = ?,
                confidence = ?, source = ?, updated_at = ?
            WHERE id = ?
        """, (
            node.type.value,
            node.what,
            node.when.isoformat() if node.when else None,
            node.where,
            json.dumps(node.who),
            node.why,
            node.how,
            json.dumps(node.tags),
            json.dumps(node.artifacts),
            self._serialize_embedding(node.embedding),
            node.confidence,
            node.source,
            node.updated_at.isoformat(),
            str(node.id)
        ))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_node(self, node_id: UUID) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM nodes WHERE id = ?",
            (str(node_id),)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def add_edge(self, edge: Edge) -> UUID:
        import json
        
        self.conn.execute("""
            INSERT INTO edges (id, source_id, target_id, type, weight, metadata, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(edge.id),
            str(edge.source_id),
            str(edge.target_id),
            edge.type.value,
            edge.weight,
            json.dumps(edge.metadata),
            edge.created_at.isoformat()
        ))
        self.conn.commit()
        return edge.id
    
    def get_edges(
        self,
        node_id: UUID,
        direction: str = "both",
        edge_type: Optional[EdgeType] = None
    ) -> list[Edge]:
        import json
        
        node_str = str(node_id)
        
        if direction == "outgoing":
            query = "SELECT * FROM edges WHERE source_id = ?"
            params = [node_str]
        elif direction == "incoming":
            query = "SELECT * FROM edges WHERE target_id = ?"
            params = [node_str]
        else:  # both
            query = "SELECT * FROM edges WHERE source_id = ? OR target_id = ?"
            params = [node_str, node_str]
        
        if edge_type:
            query += " AND type = ?"
            params.append(edge_type.value)
        
        rows = self.conn.execute(query, params).fetchall()
        
        return [
            Edge(
                id=UUID(row['id']),
                source_id=UUID(row['source_id']),
                target_id=UUID(row['target_id']),
                type=EdgeType(row['type']),
                weight=row['weight'],
                metadata=json.loads(row['metadata']) if row['metadata'] else {},
                created_at=datetime.fromisoformat(row['created_at'])
            )
            for row in rows
        ]
    
    def delete_edge(self, edge_id: UUID) -> bool:
        cursor = self.conn.execute(
            "DELETE FROM edges WHERE id = ?",
            (str(edge_id),)
        )
        self.conn.commit()
        return cursor.rowcount > 0
    
    def query_by_time(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 100
    ) -> list[MemoryNode]:
        query = "SELECT id FROM nodes WHERE 1=1"
        params = []
        
        if since:
            query += " AND when_ts >= ?"
            params.append(since.isoformat())
        if until:
            query += " AND when_ts <= ?"
            params.append(until.isoformat())
        
        query += " ORDER BY when_ts DESC LIMIT ?"
        params.append(limit)
        
        rows = self.conn.execute(query, params).fetchall()
        return [self.get_node(UUID(row['id'])) for row in rows]
    
    def query_by_tags(
        self,
        tags: list[str],
        match_all: bool = False,
        limit: int = 100
    ) -> list[MemoryNode]:
        # Simple implementation - can optimize with JSON functions
        all_nodes = self.conn.execute(
            "SELECT id, tags FROM nodes LIMIT ?",
            (limit * 10,)  # Over-fetch then filter
        ).fetchall()
        
        import json
        results = []
        for row in all_nodes:
            node_tags = set(json.loads(row['tags']) if row['tags'] else [])
            search_tags = set(tags)
            
            if match_all:
                if search_tags.issubset(node_tags):
                    results.append(UUID(row['id']))
            else:
                if search_tags & node_tags:
                    results.append(UUID(row['id']))
            
            if len(results) >= limit:
                break
        
        return [self.get_node(nid) for nid in results]
    
    def query_by_text(
        self,
        query: str,
        limit: int = 100
    ) -> list[MemoryNode]:
        rows = self.conn.execute("""
            SELECT nodes.id FROM nodes
            JOIN nodes_fts ON nodes.rowid = nodes_fts.rowid
            WHERE nodes_fts MATCH ?
            LIMIT ?
        """, (query, limit)).fetchall()
        
        return [self.get_node(UUID(row['id'])) for row in rows]
    
    def query_by_embedding(
        self,
        embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7
    ) -> list[QueryResult]:
        # TODO: Implement with numpy for cosine similarity
        # For now, return empty - embeddings are a Phase 2 feature
        return []
    
    def _serialize_embedding(self, embedding: Optional[list[float]]) -> Optional[bytes]:
        if embedding is None:
            return None
        import struct
        return struct.pack(f'{len(embedding)}f', *embedding)
    
    def _deserialize_embedding(self, data: Optional[bytes]) -> Optional[list[float]]:
        if data is None:
            return None
        import struct
        count = len(data) // 4
        return list(struct.unpack(f'{count}f', data))
