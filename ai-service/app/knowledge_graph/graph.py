"""
graph.py — In-Memory Knowledge Graph with Temporal Edges.

Lightweight graph implementation for historical reasoning.
NOT a database — designed for fast in-memory queries.

Features:
  ✅ Add entities and relations
  ✅ Temporal edge precomputation (BEFORE/AFTER)
  ✅ Multi-hop traversal
  ✅ Query by entity type, time range, relation type
  ✅ Path finding between entities

Future migration path: Neo4j / NetworkX
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from app.knowledge_graph.schema import (
    Entity,
    EntityType,
    Relation,
    RelationType,
)


class KnowledgeGraph:
    """
    In-memory knowledge graph for historical reasoning.

    Usage:
        kg = KnowledgeGraph()
        kg.add_entity(Entity(id="dbp", name="Điện Biên Phủ", ...))
        kg.add_entity(Entity(id="geneva", name="Hiệp định Genève", ...))
        kg.add_relation(Relation("dbp", "geneva", RelationType.CAUSED))

        # Query
        effects = kg.get_related("dbp", RelationType.CAUSED)
        path = kg.find_path("dbp", "us_intervention")
    """

    def __init__(self):
        # Entity storage
        self._entities: Dict[str, Entity] = {}

        # Adjacency lists (directed)
        self._outgoing: Dict[str, List[Relation]] = defaultdict(list)
        self._incoming: Dict[str, List[Relation]] = defaultdict(list)

        # Indexes
        self._by_type: Dict[EntityType, Set[str]] = defaultdict(set)
        self._by_name: Dict[str, str] = {}  # lowercase name → entity_id

    # ==================================================================
    # ENTITY OPERATIONS
    # ==================================================================

    def add_entity(self, entity: Entity) -> None:
        """Add an entity to the graph."""
        self._entities[entity.id] = entity
        self._by_type[entity.entity_type].add(entity.id)
        self._by_name[entity.name.lower()] = entity.id

        # Also index aliases
        for alias in entity.aliases:
            self._by_name[alias.lower()] = entity.id

    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        return self._entities.get(entity_id)

    def find_entity(self, name: str) -> Optional[Entity]:
        """Find entity by name (case-insensitive, alias-aware)."""
        name_lower = name.lower()
        entity_id = self._by_name.get(name_lower)
        if entity_id:
            return self._entities.get(entity_id)

        # Fuzzy: check if name is substring of any entity name
        for stored_name, eid in self._by_name.items():
            if name_lower in stored_name or stored_name in name_lower:
                return self._entities.get(eid)
        return None

    def get_entities_by_type(self, entity_type: EntityType) -> List[Entity]:
        """Get all entities of a given type."""
        return [
            self._entities[eid]
            for eid in self._by_type.get(entity_type, set())
            if eid in self._entities
        ]

    # ==================================================================
    # RELATION OPERATIONS
    # ==================================================================

    def add_relation(self, relation: Relation) -> None:
        """Add a directed relation between entities."""
        self._outgoing[relation.source_id].append(relation)
        self._incoming[relation.target_id].append(relation)

    def get_related(
        self,
        entity_id: str,
        relation_type: Optional[RelationType] = None,
        direction: str = "outgoing",
    ) -> List[Tuple[Entity, Relation]]:
        """
        Get entities related to the given entity.

        Args:
            entity_id: Source entity ID.
            relation_type: Filter by relation type (None = all).
            direction: "outgoing", "incoming", or "both".

        Returns:
            List of (related_entity, relation) tuples.
        """
        results = []

        if direction in ("outgoing", "both"):
            for rel in self._outgoing.get(entity_id, []):
                if relation_type and rel.relation_type != relation_type:
                    continue
                target = self._entities.get(rel.target_id)
                if target:
                    results.append((target, rel))

        if direction in ("incoming", "both"):
            for rel in self._incoming.get(entity_id, []):
                if relation_type and rel.relation_type != relation_type:
                    continue
                source = self._entities.get(rel.source_id)
                if source:
                    results.append((source, rel))

        return results

    # ==================================================================
    # TEMPORAL OPERATIONS
    # ==================================================================

    def precompute_temporal_edges(self) -> int:
        """
        Precompute BEFORE/AFTER temporal edges between all entities.

        Instead of computing at query time, precompute the timeline
        order for fast temporal queries.

        Returns:
            Number of temporal edges added.
        """
        entities_with_time = [
            e for e in self._entities.values()
            if e.start_year is not None
        ]

        # Sort by start year
        entities_with_time.sort(key=lambda e: e.start_year or 0)

        count = 0
        for i, e1 in enumerate(entities_with_time):
            for e2 in entities_with_time[i + 1:]:
                if (e1.end_year or e1.start_year or 0) < (e2.start_year or 0):
                    # e1 is strictly before e2
                    self.add_relation(Relation(
                        source_id=e1.id,
                        target_id=e2.id,
                        relation_type=RelationType.BEFORE,
                    ))
                    count += 1

        return count

    def get_events_in_range(
        self, start_year: int, end_year: int
    ) -> List[Entity]:
        """Get entities within a time range."""
        return [
            e for e in self._entities.values()
            if e.start_year is not None
            and start_year <= e.start_year <= end_year
        ]

    # ==================================================================
    # MULTI-HOP TRAVERSAL
    # ==================================================================

    def find_path(
        self,
        source_id: str,
        target_id: str,
        max_hops: int = 3,
    ) -> Optional[List[Tuple[Entity, Relation]]]:
        """
        Find shortest path between two entities (BFS).

        Used for multi-hop reasoning:
            "Sự kiện nào dẫn đến Hiệp định Genève?"
            → Điện Biên Phủ --CAUSED--> Genève

        Args:
            source_id: Start entity ID.
            target_id: End entity ID.
            max_hops: Maximum path length.

        Returns:
            Path as list of (entity, relation) tuples, or None.
        """
        if source_id == target_id:
            return []

        # BFS
        from collections import deque
        queue = deque([(source_id, [])])
        visited = {source_id}

        while queue:
            current_id, path = queue.popleft()

            if len(path) >= max_hops:
                continue

            for rel in self._outgoing.get(current_id, []):
                next_id = rel.target_id
                if next_id in visited:
                    continue

                next_entity = self._entities.get(next_id)
                if not next_entity:
                    continue

                new_path = path + [(next_entity, rel)]

                if next_id == target_id:
                    return new_path

                visited.add(next_id)
                queue.append((next_id, new_path))

        return None

    # ==================================================================
    # STATISTICS
    # ==================================================================

    @property
    def entity_count(self) -> int:
        return len(self._entities)

    @property
    def relation_count(self) -> int:
        return sum(len(rels) for rels in self._outgoing.values())

    def summary(self) -> Dict[str, Any]:
        """Graph statistics summary."""
        type_counts = {
            t.value: len(ids) for t, ids in self._by_type.items()
        }
        return {
            "total_entities": self.entity_count,
            "total_relations": self.relation_count,
            "entities_by_type": type_counts,
        }
