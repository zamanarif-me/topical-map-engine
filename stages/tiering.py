"""
Stage 6: Supplementary Nodes — Per-Pillar (reliable JSON parsing)

Per-pillar calls = smaller JSON output = no parsing errors.
Each pillar gets 3-4 supplementary nodes per cluster.
"""

import json
from typing import Optional
from pydantic import BaseModel

from models import Pillar, SupplementaryNode, Intent, FunnelStage
from stages._client import call_anthropic_structured
from stages.serp import SerpData


class _RawNode(BaseModel):
    id: str
    title: str
    parent_cluster_id: str
    intent: Intent
    funnel_stage: FunnelStage
    angle: Optional[str] = None


class SupplementaryResponse(BaseModel):
    supplementary_nodes: list[_RawNode]


SUPP_PROMPT = """You are a semantic SEO strategist.

Generate supplementary (Tier 3) nodes for ONE pillar's clusters.
Each cluster gets 3-4 nodes mixing these angles:
  - contradiction: "Why [belief] Is Wrong" or "The Real Reason [X]"
  - information_gain: "How [mechanism] affects [outcome]"
  - perspective: "[Topic] from a [Role] perspective"
  - lifecycle: "[Topic] After [Event/State]"

Rules:
- At least 1 contradiction node per cluster (MANDATORY)
- At least 1 information_gain node per cluster (MANDATORY)
- IDs must be unique — format: supp_[short_slug]
- Titles must be SPECIFIC and ENTITY-RICH

Output ONLY valid JSON — no trailing commas, no comments:
{
  "supplementary_nodes": [
    {
      "id": "supp_unique_slug",
      "title": "Specific Page Title Here",
      "parent_cluster_id": "cluster_id_here",
      "intent": "informational",
      "funnel_stage": "MOFU",
      "angle": "contradiction"
    }
  ]
}"""


def generate_supplementary_for_pillar(
    pillar: Pillar,
    serp_data: dict[str, SerpData] | None = None,
) -> Pillar:
    """Generate supplementary nodes for ONE pillar — small JSON, reliable."""

    cluster_list = [{"cluster_id": c.id, "title": c.title} for c in pillar.clusters]

    related_context = ""
    if serp_data and pillar.id in serp_data:
        related = serp_data[pillar.id].related_searches[:6]
        if related:
            related_context = "\nRelated searches (use as topic seeds):\n" + "\n".join(f"- {r}" for r in related)

    user_msg = (
        f"Pillar: {pillar.title}\n"
        f"Clusters: {json.dumps(cluster_list)}\n"
        f"{related_context}\n\n"
        "Generate 3-4 supplementary nodes per cluster.\n"
        "MANDATORY: at least 1 contradiction + 1 information_gain per cluster.\n"
        "Output ONLY valid JSON."
    )

    try:
        resp = call_anthropic_structured(
            system_prompt=SUPP_PROMPT,
            user_message=user_msg,
            response_model=SupplementaryResponse,
            max_tokens=4000,
        )
        cluster_lookup = {c.id: c for c in pillar.clusters}
        added = 0
        for node in resp.supplementary_nodes:
            cluster = cluster_lookup.get(node.parent_cluster_id)
            if cluster:
                cluster.supplementary_nodes.append(SupplementaryNode(
                    id=node.id,
                    title=node.title,
                    parent_cluster_id=node.parent_cluster_id,
                    intent=node.intent,
                    funnel_stage=node.funnel_stage,
                    angle=node.angle,
                ))
                added += 1
        print(f"    {added} nodes added")
    except Exception as e:
        print(f"    [tiering] Failed: {e}")

    return pillar


def generate_supplementary_for_all(
    pillars: list[Pillar],
    serp_data: dict[str, SerpData] | None = None,
    batch_size: int = 5,  # ignored — per-pillar
) -> list[Pillar]:
    """Generate supplementary nodes per pillar — reliable, no batch JSON issues."""
    for i, pillar in enumerate(pillars):
        print(f"  [{i+1}/{len(pillars)}] Supp: {pillar.title[:50]}")
        generate_supplementary_for_pillar(pillar, serp_data)
    return pillars
