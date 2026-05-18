"""
Stage 6: Supplementary Nodes — Per-Pillar (robust JSON parsing)
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

Generate supplementary (Tier 3) nodes for the given pillar's clusters.
Each cluster gets 2-3 nodes. Mix these angles: contradiction, information_gain, perspective.
At least 1 contradiction node per cluster.

CRITICAL: Output ONLY valid JSON. No trailing commas. No comments.

Format:
{
  "supplementary_nodes": [
    {
      "id": "supp_unique_slug",
      "title": "Specific Page Title",
      "parent_cluster_id": "cluster_id_here",
      "intent": "informational",
      "funnel_stage": "MOFU",
      "angle": "contradiction"
    }
  ]
}"""


def generate_supplementary_for_pillar(
    pillar: Pillar,
    serp_data: dict | None = None,
) -> Pillar:
    related_context = ""
    if serp_data and pillar.id in serp_data:
        related = serp_data[pillar.id].related_searches[:6]
        if related:
            related_context = "\nRelated searches for inspiration:\n" + "\n".join(f"- {r}" for r in related)

    cluster_list = [{"cluster_id": c.id, "title": c.title} for c in pillar.clusters]

    user_msg = (
        f"Pillar: {pillar.title}\n"
        f"Clusters: {json.dumps(cluster_list)}\n"
        f"{related_context}\n"
        "Generate 2-3 supplementary nodes per cluster.\n"
        "IDs must be unique — use format: supp_[short_unique_slug]\n"
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
    except Exception as e:
        print(f"    [tiering] Pillar failed: {e}")

    return pillar


def generate_supplementary_for_all(
    pillars: list[Pillar],
    serp_data: dict | None = None,
    batch_size: int = 5,
) -> list[Pillar]:
    for i, pillar in enumerate(pillars):
        print(f"  [{i+1}/{len(pillars)}] Supp: {pillar.title[:50]}")
        generate_supplementary_for_pillar(pillar, serp_data)
    return pillars
