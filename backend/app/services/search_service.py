import math
import time
from typing import List, Optional, Tuple
from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.models.common import Point3D
from app.models.poi import POIRecord
from app.models.search import SearchResponse, SearchResultItem
from app.services.venue_service import VenueNotFoundError, venue_service
from app.utils.logger import logger


class SearchService:
    """Typo-tolerant, weighted fuzzy search engine over indoor POIs."""

    WEIGHT_NAME = 1.00
    WEIGHT_TAGS = 0.85
    WEIGHT_CATEGORY = 0.70
    WEIGHT_DESCRIPTION = 0.50

    MIN_SCORE_THRESHOLD = 45.0

    def search(
        self,
        db: Session,
        venue_id: str,
        query: str,
        category_filter: Optional[str] = None,
        user_position: Optional[Point3D] = None,
        limit: int = 10,
        sort_by: str = "relevance",  # "relevance" or "distance"
    ) -> SearchResponse:
        start_time = time.perf_counter()

        # 1. Verify venue exists
        venue_service.get_venue(venue_id)

        clean_query = query.strip() if query else ""
        clean_query_lower = clean_query.lower()

        # 2. Retrieve POIs from database (with optional category filter)
        db_query = db.query(POIRecord).filter(POIRecord.venue_id == venue_id)
        if category_filter:
            db_query = db_query.filter(POIRecord.category == category_filter.lower().strip())
        records = db_query.all()

        # 3. Handle empty query edge case
        if not clean_query:
            if category_filter:
                # Return all records in this category
                results = []
                for r in records[:limit]:
                    dist = self._calc_distance(r, user_position)
                    results.append(
                        SearchResultItem(
                            id=r.id,
                            venue_id=r.venue_id,
                            name=r.name,
                            category=r.category,
                            description=r.description,
                            position=r.position,
                            tags=r.tags,
                            floor=r.floor,
                            score=100.0,
                            matched_field="category",
                            distance=dist,
                        )
                    )
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return SearchResponse(
                    query=clean_query,
                    venue_id=venue_id,
                    category_filter=category_filter,
                    total_results=len(results),
                    results=results,
                    execution_time_ms=round(elapsed_ms, 3),
                )
            else:
                elapsed_ms = (time.perf_counter() - start_time) * 1000.0
                return SearchResponse(
                    query=clean_query,
                    venue_id=venue_id,
                    category_filter=category_filter,
                    total_results=0,
                    results=[],
                    execution_time_ms=round(elapsed_ms, 3),
                )

        # 4. Fuzzy Match & Score each POI
        scored_items: List[SearchResultItem] = []

        for record in records:
            score, matched_field = self._compute_relevance_score(
                clean_query_lower, record
            )

            if score >= self.MIN_SCORE_THRESHOLD:
                dist = self._calc_distance(record, user_position)
                scored_items.append(
                    SearchResultItem(
                        id=record.id,
                        venue_id=record.venue_id,
                        name=record.name,
                        category=record.category,
                        description=record.description,
                        position=record.position,
                        tags=record.tags,
                        floor=record.floor,
                        score=score,
                        matched_field=matched_field,
                        distance=dist,
                    )
                )

        # 5. Sorting
        if sort_by == "distance" and user_position is not None:
            # Sort by distance first, then score
            scored_items.sort(
                key=lambda item: (
                    item.distance if item.distance is not None else float("inf"),
                    -item.score,
                )
            )
        else:
            # Sort by relevance score descending; secondary sort by distance if available
            scored_items.sort(
                key=lambda item: (
                    -item.score,
                    item.distance if item.distance is not None else 0.0,
                )
            )

        trimmed_results = scored_items[:limit]
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0

        return SearchResponse(
            query=clean_query,
            venue_id=venue_id,
            category_filter=category_filter,
            total_results=len(trimmed_results),
            results=trimmed_results,
            execution_time_ms=round(elapsed_ms, 3),
        )

    def _compute_relevance_score(
        self, query: str, record: POIRecord
    ) -> Tuple[float, str]:
        """Compute weighted relevance score across name, tags, category, and description."""
        name_lower = record.name.lower()
        category_lower = record.category.lower()
        desc_lower = (record.description or "").lower()
        tags = [t.lower() for t in record.tags]

        # 1. Name Match
        name_ratio = fuzz.WRatio(query, name_lower)
        if query == name_lower:
            name_ratio = 100.0
        elif query in name_lower:
            name_ratio = max(name_ratio, 92.0)
        score_name = name_ratio * self.WEIGHT_NAME

        # 2. Tag Match
        tag_scores = []
        for tag in tags:
            tr = fuzz.WRatio(query, tag)
            if query == tag:
                tr = 100.0
            elif query in tag:
                tr = max(tr, 90.0)
            tag_scores.append(tr)
        best_tag_ratio = max(tag_scores) if tag_scores else 0.0
        score_tags = best_tag_ratio * self.WEIGHT_TAGS

        # 3. Category Match
        cat_ratio = fuzz.WRatio(query, category_lower)
        if query == category_lower:
            cat_ratio = 100.0
        elif query in category_lower:
            cat_ratio = max(cat_ratio, 85.0)
        score_category = cat_ratio * self.WEIGHT_CATEGORY

        # 4. Description Match (use partial_ratio for paragraph text)
        desc_ratio = fuzz.partial_ratio(query, desc_lower) if desc_lower else 0.0
        if query in desc_lower:
            desc_ratio = max(desc_ratio, 80.0)
        score_desc = desc_ratio * self.WEIGHT_DESCRIPTION

        # Find dominant matched field
        candidates = [
            (score_name, "name"),
            (score_tags, "tags"),
            (score_category, "category"),
            (score_desc, "description"),
        ]
        candidates.sort(key=lambda x: x[0], reverse=True)
        top_score, matched_field = candidates[0]

        return round(top_score, 2), matched_field

    def _calc_distance(
        self, record: POIRecord, user_position: Optional[Point3D]
    ) -> Optional[float]:
        if user_position is None:
            return None
        dx = record.pos_x - user_position.x
        dy = record.pos_y - user_position.y
        dz = record.pos_z - user_position.z
        return round(math.sqrt(dx * dx + dy * dy + dz * dz), 3)


search_service = SearchService()
