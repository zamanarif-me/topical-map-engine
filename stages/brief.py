"""
Stage 9: Content Brief Generator

Takes any page from the topical map (pillar or cluster) and generates
a complete content brief following:
  - Koray's information gain + entity attribute methodology
  - NeuronWriter's brief structure
  - 12-step process from the user's reference .md file

This is the final deliverable layer — what a writer actually uses.
"""

import json
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from models import Pillar, Cluster, TopicalMap
from stages._client import call_anthropic_structured, load_prompt


# ── Output Models ─────────────────────────────────────────────────────────────

class QuerySet(BaseModel):
    primary_query: str
    secondary_queries: list[str]
    question_queries: list[str]
    journey_stage: str


class EntityAttributeMap(BaseModel):
    core_attributes: list[str]
    performance_states: list[str]
    failure_modes: list[str]
    dependencies: list[str]
    optimization_levers: list[str]


class HeadingNode(BaseModel):
    level: str          # H1, H2, H3, H4
    text: str
    semantic_purpose: str  # what user need this heading serves


class NLPTerms(BaseModel):
    must_include: list[str]
    should_include: list[str]
    semantic_variants: list[str]


class ContentSpecs(BaseModel):
    recommended_word_count: int
    content_format: str
    reading_level: str
    pov: str
    e_e_a_t_signals: list[str]


class SERPTarget(BaseModel):
    featured_snippet: bool
    featured_snippet_section: Optional[str] = None
    featured_snippet_format: Optional[str] = None
    people_also_ask: list[str]
    schema_markup: str


class SemanticBridge(BaseModel):
    bridge_point: str
    link_destination: str
    anchor_suggestion: str
    shared_entity: str
    relationship_strength: float


class NextDestination(BaseModel):
    next_page_id: str
    next_page_title: str
    transition_reason: str
    transition_anchor: str


class EEATRequirements(BaseModel):
    author_expertise: str
    experience_signals: list[str]
    trust_signals: list[str]
    ymyl_considerations: Optional[str] = None


class ContentBrief(BaseModel):
    """Complete content brief for one page."""
    page_id: str
    page_title: str
    page_type: str                    # pillar | cluster | supplementary
    parent_pillar: Optional[str] = None
    central_entity: str
    section_type: str                 # CORE | OUTER
    information_gain_angle: str
    queries: QuerySet
    entity_attribute_map: EntityAttributeMap
    headings: list[HeadingNode]
    nlp_terms: NLPTerms
    content_specs: ContentSpecs
    serp_target: SERPTarget
    semantic_bridges: list[SemanticBridge]
    next_destination: NextDestination
    eeat_requirements: EEATRequirements
    quality_checklist: dict[str, bool]


# ── Context builders ──────────────────────────────────────────────────────────

def _build_pillar_context(pillar: Pillar, topical_map: TopicalMap) -> dict:
    """Build context dict for a pillar brief."""
    # Other pillars for semantic bridge identification
    other_pillars = [
        {"id": p.id, "title": p.title, "entities": p.related_entities[:4]}
        for p in topical_map.pillars
        if p.id != pillar.id
    ]

    return {
        "page_id":        pillar.id,
        "page_title":     pillar.title,
        "page_type":      "pillar",
        "central_entity": pillar.related_entities[0] if pillar.related_entities else pillar.title,
        "intent":         pillar.intent.value,
        "funnel_stage":   pillar.funnel_stage.value,
        "commercial_value": pillar.commercial_value,
        "related_entities": pillar.related_entities,
        "clusters": [
            {"id": c.id, "title": c.title, "intent": c.intent.value}
            for c in pillar.clusters[:8]
        ],
        "representative_queries": [q.text for q in pillar.representative_queries[:3]],
        "other_pillars_for_bridges": other_pillars[:6],
    }


def _build_cluster_context(
    cluster: Cluster,
    parent_pillar: Pillar,
    topical_map: TopicalMap,
) -> dict:
    """Build context dict for a cluster brief."""
    other_pillars = [
        {"id": p.id, "title": p.title, "entities": p.related_entities[:4]}
        for p in topical_map.pillars
        if p.id != parent_pillar.id
    ]

    return {
        "page_id":          cluster.id,
        "page_title":       cluster.title,
        "page_type":        "cluster",
        "parent_pillar_id": parent_pillar.id,
        "parent_pillar":    parent_pillar.title,
        "central_entity":   cluster.related_entities[0] if cluster.related_entities else cluster.title,
        "intent":           cluster.intent.value,
        "funnel_stage":     cluster.funnel_stage.value,
        "related_entities": cluster.related_entities,
        "represented_queries": [q.text for q in cluster.represented_queries[:5]],
        "supplementary_nodes": [
            {"id": s.id, "title": s.title, "angle": s.angle}
            for s in cluster.supplementary_nodes[:6]
        ],
        "sibling_clusters": [
            {"id": c.id, "title": c.title}
            for c in parent_pillar.clusters
            if c.id != cluster.id
        ][:5],
        "other_pillars_for_bridges": other_pillars[:6],
    }


# ── Main generator ────────────────────────────────────────────────────────────

def generate_brief_for_pillar(
    pillar: Pillar,
    topical_map: TopicalMap,
    serp_context: str = "",
) -> ContentBrief:
    """Generate a full content brief for a pillar page."""
    system_prompt = load_prompt("content_brief")
    context = _build_pillar_context(pillar, topical_map)

    user_message = f"""Generate a complete content brief for this PILLAR page.

# Page Context
```json
{json.dumps(context, indent=2)}
```

{f"# SERP Data{chr(10)}{serp_context}" if serp_context else ""}

Apply maximum information gain — the H1 must be differentiated from generic competitor titles.
Expand entity attributes deeply — cover failure modes, performance states, dependencies.
Design 2-3 semantic bridges to other pillars via shared entities.
Output ONLY valid JSON matching the ContentBrief schema."""

    return call_anthropic_structured(
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=ContentBrief,
        max_tokens=8000,
    )


def generate_brief_for_cluster(
    cluster: Cluster,
    parent_pillar: Pillar,
    topical_map: TopicalMap,
    serp_context: str = "",
) -> ContentBrief:
    """Generate a full content brief for a cluster page."""
    system_prompt = load_prompt("content_brief")
    context = _build_cluster_context(cluster, parent_pillar, topical_map)

    user_message = f"""Generate a complete content brief for this CLUSTER page.

# Page Context
```json
{json.dumps(context, indent=2)}
```

{f"# SERP Data{chr(10)}{serp_context}" if serp_context else ""}

This is a supporting page under the "{parent_pillar.title}" pillar.
Apply information gain — what unique angle does this cluster cover that the pillar doesn't?
Include at least one contradiction/myth-busting H2.
Design the next_destination to point toward either the parent pillar or a sibling cluster.
Output ONLY valid JSON matching the ContentBrief schema."""

    return call_anthropic_structured(
        system_prompt=system_prompt,
        user_message=user_message,
        response_model=ContentBrief,
        max_tokens=8000,
    )


# ── Batch generator ───────────────────────────────────────────────────────────

def generate_briefs_for_pillar_and_clusters(
    pillar: Pillar,
    topical_map: TopicalMap,
    include_clusters: bool = True,
    max_clusters: int = 3,
) -> dict[str, ContentBrief]:
    """
    Generate briefs for a pillar and its top clusters.

    Returns dict keyed by page_id.

    max_clusters: how many cluster briefs to generate (cost control).
    Set to 0 for pillar-only.
    """
    briefs: dict[str, ContentBrief] = {}

    print(f"  Generating pillar brief: {pillar.title}")
    try:
        brief = generate_brief_for_pillar(pillar, topical_map)
        briefs[pillar.id] = brief
        print(f"    ✓ Pillar brief done")
    except Exception as e:
        print(f"    ✗ Pillar brief failed: {e}")

    if include_clusters and max_clusters > 0:
        # Prioritize BOFU clusters (highest commercial value)
        priority_clusters = sorted(
            pillar.clusters,
            key=lambda c: 0 if c.funnel_stage.value == "BOFU" else 1,
        )[:max_clusters]

        for cluster in priority_clusters:
            print(f"  Generating cluster brief: {cluster.title}")
            try:
                brief = generate_brief_for_cluster(cluster, pillar, topical_map)
                briefs[cluster.id] = brief
                print(f"    ✓ Cluster brief done")
            except Exception as e:
                print(f"    ✗ Cluster brief failed: {e}")

    return briefs


# ── Render ────────────────────────────────────────────────────────────────────

def save_brief_as_markdown(brief: ContentBrief, output_path: str | Path) -> Path:
    """Render a content brief as a human-readable Markdown file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Content Brief: {brief.page_title}",
        f"",
        f"**Page ID:** `{brief.page_id}`  ",
        f"**Type:** {brief.page_type} | **Section:** {brief.section_type}  ",
        f"**Central Entity:** {brief.central_entity}  ",
        f"**Journey Stage:** {brief.queries.journey_stage}  ",
        f"",
        f"---",
        f"",
        f"## Information Gain Angle",
        f"",
        f"> {brief.information_gain_angle}",
        f"",
        f"---",
        f"",
        f"## Target Queries",
        f"",
        f"**Primary:** `{brief.queries.primary_query}`",
        f"",
        f"**Secondary:**",
    ] + [f"- `{q}`" for q in brief.queries.secondary_queries] + [
        f"",
        f"**Questions (PAA):**",
    ] + [f"- {q}" for q in brief.queries.question_queries] + [
        f"",
        f"---",
        f"",
        f"## Entity Attribute Map",
        f"",
        f"**Core Attributes:**",
    ] + [f"- {a}" for a in brief.entity_attribute_map.core_attributes] + [
        f"",
        f"**Performance States:**",
    ] + [f"- {a}" for a in brief.entity_attribute_map.performance_states] + [
        f"",
        f"**Failure Modes:**",
    ] + [f"- {a}" for a in brief.entity_attribute_map.failure_modes] + [
        f"",
        f"**Dependencies:**",
    ] + [f"- {a}" for a in brief.entity_attribute_map.dependencies] + [
        f"",
        f"**Optimization Levers:**",
    ] + [f"- {a}" for a in brief.entity_attribute_map.optimization_levers] + [
        f"",
        f"---",
        f"",
        f"## Content Structure",
        f"",
    ]

    for h in brief.headings:
        indent = "  " * (int(h.level[1]) - 1)
        lines.append(f"{indent}**{h.level}:** {h.text}")
        lines.append(f"{indent}*Purpose: {h.semantic_purpose}*")
        lines.append("")

    lines += [
        f"---",
        f"",
        f"## NLP Terms",
        f"",
        f"**Must Include (3-5x):** {', '.join(brief.nlp_terms.must_include)}",
        f"",
        f"**Should Include (1-2x):** {', '.join(brief.nlp_terms.should_include)}",
        f"",
        f"**Semantic Variants:** {', '.join(brief.nlp_terms.semantic_variants)}",
        f"",
        f"---",
        f"",
        f"## Content Specifications",
        f"",
        f"- **Word Count:** {brief.content_specs.recommended_word_count:,}",
        f"- **Format:** {brief.content_specs.content_format}",
        f"- **Reading Level:** {brief.content_specs.reading_level}",
        f"- **POV:** {brief.content_specs.pov}",
        f"- **E-E-A-T Signals:** {', '.join(brief.content_specs.e_e_a_t_signals)}",
        f"",
        f"---",
        f"",
        f"## SERP Feature Targets",
        f"",
        f"- **Featured Snippet:** {'Yes' if brief.serp_target.featured_snippet else 'No'}",
    ]

    if brief.serp_target.featured_snippet:
        lines += [
            f"  - Section: {brief.serp_target.featured_snippet_section}",
            f"  - Format: {brief.serp_target.featured_snippet_format}",
        ]

    lines += [
        f"- **Schema:** {brief.serp_target.schema_markup}",
        f"- **PAA to answer:**",
    ] + [f"  - {q}" for q in brief.serp_target.people_also_ask] + [
        f"",
        f"---",
        f"",
        f"## Semantic Bridges (Cross-Pillar Links)",
        f"",
    ]

    for bridge in brief.semantic_bridges:
        lines += [
            f"**When:** {bridge.bridge_point}",
            f"**Link to:** `{bridge.link_destination}`",
            f"**Anchor:** *\"{bridge.anchor_suggestion}\"*",
            f"**Shared entity:** {bridge.shared_entity} | **Strength:** {bridge.relationship_strength:.2f}",
            f"",
        ]

    lines += [
        f"---",
        f"",
        f"## Next Best Destination",
        f"",
        f"**Next page:** [{brief.next_destination.next_page_title}] (`{brief.next_destination.next_page_id}`)",
        f"",
        f"**Why:** {brief.next_destination.transition_reason}",
        f"",
        f"**CTA:** *\"{brief.next_destination.transition_anchor}\"*",
        f"",
        f"---",
        f"",
        f"## E-E-A-T Requirements",
        f"",
        f"**Author expertise:** {brief.eeat_requirements.author_expertise}",
        f"",
        f"**Experience signals:**",
    ] + [f"- {s}" for s in brief.eeat_requirements.experience_signals] + [
        f"",
        f"**Trust signals:**",
    ] + [f"- {s}" for s in brief.eeat_requirements.trust_signals] + [
        f"",
        f"---",
        f"",
        f"## Quality Checklist",
        f"",
    ] + [
        f"- [{'x' if v else ' '}] {k.replace('_', ' ').title()}"
        for k, v in brief.quality_checklist.items()
    ]

    path.write_text("\n".join(lines))
    return path


def save_briefs(
    briefs: dict[str, ContentBrief],
    output_dir: str | Path,
) -> list[Path]:
    """Save all briefs as individual Markdown files."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    saved = []
    for page_id, brief in briefs.items():
        path = save_brief_as_markdown(
            brief,
            output_dir / f"brief_{page_id}.md"
        )
        saved.append(path)

    # Also save all briefs as one JSON
    json_path = output_dir / "all_briefs.json"
    json_path.write_text(json.dumps(
        {pid: b.model_dump(mode="json") for pid, b in briefs.items()},
        indent=2,
    ))
    saved.append(json_path)

    return saved
