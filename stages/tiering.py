from typing import Optional
"""
Stage 6: Supplementary Nodes — Batched (cost optimized)

Before: 10 separate LLM calls = ~30,000 output tokens
After:  2 batched calls = ~10,000 output tokens
Saving: ~20,000 output tokens = ~$0.30
"""

import json
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


class _PillarNodes(BaseModel):
    pillar_id: str
    supplementary_nodes: list[_RawNode]


class BatchSupplementaryResponse(BaseModel):
    pillars: list[_PillarNodes]


BATCH_SUPP_PROMPT = """You are a semantic SEO strategist.

For each pillar, generate 3-5 supplementary (Tier 3) nodes per cluster.
Mix angles: contradiction, information_gain, perspective, lifecycle.
At least 1 contradiction per cluster. At least 1 information_gain per cluster.
These are supporting pages — NOT money pages, NOT major sub-topics.
Each node: specific title, parent_cluster_id, intent, funnel_stage.

ID format: supp_<short_slug> (unique across ALL pillars in this batch).

Output ONLY valid JSON:
{
  "pillars": [
    {
      "pillar_id": "pillar_id",
      "supplementary_nodes": [
        {
          "id": "supp_unique_slug",
          "title": "Specific Supplementary Page Title",
          "parent_cluster_id": "cluster_id",
          "intent": "informational",
          "funnel_stage": "TOFU"
        }
      ]
    }
  ]
}"""


def _build_pillar_context(
    pillar: Pillar,
    serp_data: dict[str, SerpData] | None,
) -> dict:
    ctx = {
        "pillar_id": pillar.id,
        "title":     pillar.title,
        "clusters": [
            {"cluster_id": c.id, "title": c.title}
            for c in pillar.clusters
        ],
    }
    # Add related searches as topic seeds
    if serp_data and pillar.id in serp_data:
        related = serp_data[pillar.id].related_searches[:6]
        if related:
            ctx["topic_seeds"] = related
    return ctx


def generate_supplementary_for_all(
    pillars: list[Pillar],
    serp_data: dict[str, SerpData] | None = None,
    batch_size: int = 5,
) -> list[Pillar]:
    """Generate supplementary nodes for all pillars in batches."""

    for i in range(0, len(pillars), batch_size):
        batch = pillars[i : i + batch_size]
        batch_ctx = [_build_pillar_context(p, serp_data) for p in batch]

        user_message = f"""Generate supplementary nodes for these {len(batch)} pillars.
3-5 nodes per cluster, all node IDs must be unique.

```json
{json.dumps(batch_ctx, indent=2)}
```

Output ONLY valid JSON."""

        try:
            response = call_anthropic_structured(
                system_prompt=BATCH_SUPP_PROMPT,
                user_message=user_message,
                response_model=BatchSupplementaryResponse,
                max_tokens=6000,
            )

            result_map = {r.pillar_id: r for r in response.pillars}

            for pillar in batch:
                result = result_map.get(pillar.id)
                if not result:
                    continue
                cluster_lookup = {c.id: c for c in pillar.clusters}
                for node in result.supplementary_nodes:
                    cluster = cluster_lookup.get(node.parent_cluster_id)
                    if cluster:
                        cluster.supplementary_nodes.append(SupplementaryNode(
                            id=node.id,
                            title=node.title,
                            parent_cluster_id=node.parent_cluster_id,
                            intent=node.intent,
                            funnel_stage=node.funnel_stage,
                        ))

        except Exception as e:
            print(f"  [tiering] Batch {i//batch_size + 1} failed: {e}")

    return pillars
