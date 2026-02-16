"""
schema.py — Knowledge Graph Entity and Relationship Schema.

Defines the core entity types and relationship types for
Vietnamese historical knowledge graph.

Entity Types:
  - Person (birth, death, role, faction)
  - Event (time range, description, location)
  - Organization (name, type, active period)
  - Location (name, region, country)
  - Treaty (name, signed year, participants)

Relationship Types:
  - PARTICIPATED_IN, OCCURRED_AT, SIGNED_BY
  - CAUSED, BEFORE, AFTER, PART_OF
  - LED, FOUNDED, SUCCEEDED

Design:
  Start with in-memory graph → migrate to Neo4j/NetworkX later.
  KG is NOT primary retrieval — it's:
    ✅ Reasoning layer
    ✅ Constraint validator
    ✅ Multi-hop helper
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# ======================================================================
# ENTITY TYPES
# ======================================================================

class EntityType(str, Enum):
    """Core entity types for historical knowledge graph."""
    PERSON = "person"
    EVENT = "event"
    ORGANIZATION = "organization"
    LOCATION = "location"
    TREATY = "treaty"
    DYNASTY = "dynasty"
    WAR = "war"


@dataclass
class Entity:
    """
    Base entity in the knowledge graph.

    All entities have an ID, name, type, and optional temporal metadata.
    """
    id: str
    name: str
    entity_type: EntityType
    properties: Dict[str, Any] = field(default_factory=dict)

    # Temporal metadata (optional)
    start_year: Optional[int] = None
    end_year: Optional[int] = None

    # Aliases for entity linking
    aliases: List[str] = field(default_factory=list)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __repr__(self):
        return f"Entity({self.entity_type.value}: {self.name})"


@dataclass
class PersonEntity(Entity):
    """Person entity with biographical metadata."""
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    role: str = ""
    faction: str = ""

    def __post_init__(self):
        self.entity_type = EntityType.PERSON
        if self.birth_year:
            self.start_year = self.birth_year
        if self.death_year:
            self.end_year = self.death_year


@dataclass
class EventEntity(Entity):
    """Historical event entity."""
    description: str = ""
    location: str = ""
    event_type: str = ""  # battle, treaty, revolution, etc.

    def __post_init__(self):
        self.entity_type = EntityType.EVENT


@dataclass
class DynastyEntity(Entity):
    """Dynasty entity with succession metadata."""
    founder: str = ""
    capital: str = ""

    def __post_init__(self):
        self.entity_type = EntityType.DYNASTY


# ======================================================================
# RELATIONSHIP TYPES
# ======================================================================

class RelationType(str, Enum):
    """Core relationship types for historical reasoning."""
    # Participation
    PARTICIPATED_IN = "participated_in"
    LED = "led"
    FOUNDED = "founded"
    SIGNED_BY = "signed_by"

    # Temporal
    BEFORE = "before"
    AFTER = "after"
    DURING = "during"
    OVERLAPS = "overlaps"

    # Causal
    CAUSED = "caused"
    RESULTED_IN = "resulted_in"

    # Structural
    PART_OF = "part_of"
    OCCURRED_AT = "occurred_at"
    SUCCEEDED = "succeeded"

    # Association
    ALLIED_WITH = "allied_with"
    FOUGHT_AGAINST = "fought_against"


@dataclass
class Relation:
    """
    Directed relationship between two entities.

    Represents: source --[type]--> target
    Example: Võ Nguyên Giáp --LED--> Điện Biên Phủ
    """
    source_id: str
    target_id: str
    relation_type: RelationType
    properties: Dict[str, Any] = field(default_factory=dict)

    # Confidence score for extracted relations
    confidence: float = 1.0

    def __repr__(self):
        return (
            f"Relation({self.source_id} "
            f"--{self.relation_type.value}--> "
            f"{self.target_id})"
        )

    def __hash__(self):
        return hash((self.source_id, self.target_id, self.relation_type))

    def __eq__(self, other):
        if not isinstance(other, Relation):
            return False
        return (
            self.source_id == other.source_id
            and self.target_id == other.target_id
            and self.relation_type == other.relation_type
        )
