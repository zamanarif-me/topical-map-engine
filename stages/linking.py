"""
Stage 7: Internal Linking — Fully Optimized

Split into two parts:
  DETERMINISTIC (zero tokens):
    - pillar → cluster        (rule: every pillar links all its clusters)
    - cluster → pillar        (rule: every cluster links back to parent)
    - cluster → supplementary (rule: every cluster links its supp nodes)
    - supplementary → cluster (rule: every supp node links back to cluster)
    - homepage → pillar       (rule: priority 1 and 2 pillars)

  LLM — ONE single call for the entire map (not per-pillar):
    - entity bridges only     (requires reasoning — LLM needed)

Before: 10 LLM calls × ~5,000 output tokens = 50,000 tokens
After:  1 LLM call  × ~3,000 output tokens =  3,000 tokens
Saving: ~47,000 output tokens = ~$0.70
"""

import json

from models import Pillar, InternalLink, LinkingPlan, LinkRelationship
from stages._client import call_anthropic_structured, load_prompt
from pydantic import BaseModel


# ── Prompt for entity bridges only ───────────────────────────────────────────

ENTITY_BRIDGE_PROMPT = """You are a semantic SEO strategist.

Your task: given a topical map, identify ENTITY BRIDGE links only.

An entity bridge is a cross-pillar link where a cluster page links to a
DIFFERENT pillar because they share a key entity. These are the strategic
links that build topical authority across silos.

Rules:
- Each bridge must name the shared entity in reasoning (max 8 words)
- Generate 2-3 bridges per pillar (going outward to other pillars)
- Anchor text: 3-6 words, natural language
- Only link from CLUSTERS to other PILLARS (not pillar-to-pillar)

Output ONLY valid JSON:
{
  "links": [
    {
      "from_page_id": "cluster_id",
      "to_page_id": "pillar_id",
      "anchor_text": "natural anchor text here",
      "relationship": "entity_bridge",
      "reasoning": "Shared WooCommerce entity bridge.",
      "relationship_strength": 0.92
    }
  ]
}

relationship_strength scoring:
  0.90-1.00 = direct entity overlap (same core entity, e.g. WooCommerce → WooCommerce)
  0.70-0.89 = strong contextual overlap (e.g. Speed → Core Web Vitals)
  0.50-0.69 = moderate semantic connection (e.g. Security → Maintenance)
  0.30-0.49 = weak but valid connection (e.g. Development → Local Business)
"""


class _BridgeResponse(BaseModel):
    links: list[InternalLink]


# ── Deterministic link generators ─────────────────────────────────────────────

def _pillar_cluster_links(pillars: list[Pillar]) -> list[InternalLink]:
    """Every pillar links to all its clusters and back. Rule-based, zero tokens."""
    links = []
    for pillar in pillars:
        for cluster in pillar.clusters:
            # pillar → cluster
            links.append(InternalLink(
                from_page_id=pillar.id,
                to_page_id=cluster.id,
                anchor_text=cluster.title[:55],
                relationship=LinkRelationship.PILLAR_TO_CLUSTER,
                reasoning="Pillar to cluster.",
            ))
            # cluster → pillar
            links.append(InternalLink(
                from_page_id=cluster.id,
                to_page_id=pillar.id,
                anchor_text=pillar.title[:55],
                relationship=LinkRelationship.CLUSTER_TO_PILLAR,
                reasoning="Cluster to parent pillar.",
            ))
    return links


def _supplementary_links(pillars: list[Pillar]) -> list[InternalLink]:
    """Every cluster links its supplementary nodes and back. Rule-based, zero tokens."""
    links = []
    for pillar in pillars:
        for cluster in pillar.clusters:
            for node in cluster.supplementary_nodes:
                links.append(InternalLink(
                    from_page_id=cluster.id,
                    to_page_id=node.id,
                    anchor_text=node.title[:55],
                    relationship=LinkRelationship.CLUSTER_TO_SUPPLEMENTARY,
                    reasoning="Cluster to supplementary.",
                ))
                links.append(InternalLink(
                    from_page_id=node.id,
                    to_page_id=cluster.id,
                    anchor_text=cluster.title[:55],
                    relationship=LinkRelationship.SUPPLEMENTARY_TO_CLUSTER,
                    reasoning="Supplementary to parent cluster.",
                ))
    return links


def _homepage_links(pillars: list[Pillar]) -> list[str]:
    """Homepage links to priority 1 and 2 pillars. Rule-based."""
    return [
        p.id for p in sorted(pillars, key=lambda x: x.priority)
        if p.priority <= 2
    ]


# ── LLM: entity bridges only ──────────────────────────────────────────────────

def _generate_entity_bridges(pillars: list[Pillar]) -> list[InternalLink]:
    """
    ONE LLM call for the entire map — entity bridges only.
    Sends a compact map (pillar ID + title + top entities + cluster IDs).
    """
    # Build compact map — only what's needed for bridge reasoning
    compact_map = []
    for pillar in pillars:
        compact_map.append({
            "pillar_id":    pillar.id,
            "pillar_title": pillar.title,
            "entities":     pillar.related_entities[:5],
            "clusters": [
                {"id": c.id, "title": c.title, "entities": c.related_entities[:3]}
                for c in pillar.clusters
            ],
        })

    user_message = f"""Generate entity bridge links for this topical map.

```json
{json.dumps(compact_map, indent=2)}
```

Generate 2-3 entity bridge links per pillar (outward only).
Each bridge: a cluster from one pillar → a different pillar sharing an entity.
Output ONLY valid JSON."""

    try:
        response = call_anthropic_structured(
            system_prompt=ENTITY_BRIDGE_PROMPT,
            user_message=user_message,
            response_model=_BridgeResponse,
            max_tokens=3000,
        )
        return response.links
    except Exception as e:
        print(f"  [linking] Entity bridge generation failed: {e}. Skipping bridges.")
        return []


# ── Main builder ──────────────────────────────────────────────────────────────

def build_linking_plan(pillars: list[Pillar]) -> LinkingPlan:
    """
    Build the complete internal linking plan.

    Deterministic (0 tokens): pillar↔cluster, cluster↔supplementary, homepage
    LLM (1 call, ~3k tokens): entity bridges across pillars
    """
    all_links: list[InternalLink] = []

    # Deterministic — free
    all_links.extend(_pillar_cluster_links(pillars))
    all_links.extend(_supplementary_links(pillars))
    homepage_links = _homepage_links(pillars)

    # LLM — one call only
    bridges = _generate_entity_bridges(pillars)
    all_links.extend(bridges)

    # Deduplicate
    seen: set[tuple] = set()
    deduped: list[InternalLink] = []
    for link in all_links:
        key = (link.from_page_id, link.to_page_id, link.relationship)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(link)

    return LinkingPlan(links=deduped, homepage_links=homepage_links)
