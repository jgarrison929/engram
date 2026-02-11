"""
Core data models for Engram memory graph.

5W+H indexed memory nodes with typed edges for traversal.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4


class EdgeType(Enum):
    """Relationship types between memory nodes."""
    
    # Causal
    CAUSED_BY = "caused_by"      # X was caused by Y
    LED_TO = "led_to"            # X led to Y
    
    # Temporal
    SUPERSEDES = "supersedes"    # X is a newer version of Y
    PRECEDED_BY = "preceded_by"  # X came after Y
    
    # Semantic
    RELATES_TO = "relates_to"    # General association
    CONTRADICTS = "contradicts"  # X conflicts with Y
    SUPPORTS = "supports"        # X reinforces Y
    
    # References
    MENTIONS = "mentions"        # X references Y (person, project, etc.)
    PART_OF = "part_of"          # X is a component of Y
    DERIVED_FROM = "derived_from"  # X was created from Y


class NodeType(Enum):
    """Categories of memory nodes."""
    
    EVENT = "event"           # Something that happened
    DECISION = "decision"     # A choice that was made
    ARTIFACT = "artifact"     # A thing that was created
    CONVERSATION = "conversation"  # A discussion
    INSIGHT = "insight"       # A realization or lesson learned
    PERSON = "person"         # A person reference
    PROJECT = "project"       # A project reference
    TASK = "task"             # A to-do or action item


@dataclass
class MemoryNode:
    """
    A single memory unit indexed by 5W+H.
    
    Attributes:
        id: Unique identifier
        type: Category of memory
        
        # 5W+H
        what: What happened / what is this
        when: Timestamp of the event
        where: Location or context (optional)
        who: People involved (optional)
        why: Reasoning or motivation (optional)
        how: Method or process (optional)
        
        # Metadata
        tags: Searchable labels
        artifacts: Linked files, URLs, images
        embedding: Vector embedding for semantic search
        confidence: How certain we are (0-1)
        
        # Timestamps
        created_at: When this memory was stored
        updated_at: Last modification
    """
    
    # Identity
    id: UUID = field(default_factory=uuid4)
    type: NodeType = NodeType.EVENT
    
    # 5W+H
    what: str = ""
    when: Optional[datetime] = None
    where: Optional[str] = None
    who: list[str] = field(default_factory=list)
    why: Optional[str] = None
    how: Optional[str] = None
    
    # Metadata
    tags: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)  # file paths, URLs
    embedding: Optional[list[float]] = None
    confidence: float = 1.0
    source: Optional[str] = None  # Where this memory came from
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def __post_init__(self):
        if self.when is None:
            self.when = self.created_at


@dataclass
class Edge:
    """
    A typed relationship between two memory nodes.
    
    Attributes:
        id: Unique identifier
        source_id: Origin node
        target_id: Destination node
        type: Relationship type
        weight: Strength of relationship (0-1)
        metadata: Additional context about the relationship
        created_at: When this edge was created
    """
    
    id: UUID = field(default_factory=uuid4)
    source_id: UUID = field(default_factory=uuid4)
    target_id: UUID = field(default_factory=uuid4)
    type: EdgeType = EdgeType.RELATES_TO
    weight: float = 1.0
    metadata: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class QueryResult:
    """Result from a memory query."""
    
    node: MemoryNode
    score: float = 1.0  # Relevance score
    path: list[UUID] = field(default_factory=list)  # Traversal path to this node
    hop_count: int = 0  # How many edges traversed
