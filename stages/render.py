"""
Stage 8: Render.

Pure Python — no API calls. Takes the assembled EngineOutput and produces:
1. A JSON file with the complete structured data
2. A Markdown report suitable for sharing with a client

The rendering is intentionally template-driven (Jinja2) so non-engineers
can adjust the report format without touching code.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from models import EngineOutput, LinkRelationship


def _build_template_context(output: EngineOutput) -> dict:
    """Pre-compute derived data the template needs."""
    # Pillar title lookup for friendly homepage link display
    pillar_titles = {p.id: p.title for p in output.topical_map.pillars}

    # Count links by relationship type
    link_counts: dict[str, int] = defaultdict(int)
    for link in output.linking_plan.links:
        link_counts[link.relationship.value] += 1

    # Entity bridges (the strategic cross-pillar links)
    entity_bridges = [
        link for link in output.linking_plan.links
        if link.relationship == LinkRelationship.ENTITY_BRIDGE
    ]

    # Group links by pillar (links where either end is in the pillar's subtree)
    pillar_subtree_ids: dict[str, set[str]] = {}
    for pillar in output.topical_map.pillars:
        ids = {pillar.id}
        for c in pillar.clusters:
            ids.add(c.id)
            for s in c.supplementary_nodes:
                ids.add(s.id)
        pillar_subtree_ids[pillar.id] = ids

    links_by_pillar: dict[str, list] = defaultdict(list)
    for link in output.linking_plan.links:
        for pillar_id, subtree in pillar_subtree_ids.items():
            if link.from_page_id in subtree or link.to_page_id in subtree:
                links_by_pillar[pillar_id].append(link)

    return {
        "output": output,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "pillar_titles": pillar_titles,
        "link_counts": dict(link_counts),
        "entity_bridges": entity_bridges,
        "links_by_pillar": links_by_pillar,
    }


def render_markdown(output: EngineOutput, templates_dir: str | Path | None = None) -> str:
    """Render the output to a Markdown report."""
    if templates_dir is None:
        templates_dir = Path(__file__).parent.parent / "templates"

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=select_autoescape(disabled_extensions=("md", "j2")),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.md.j2")
    context = _build_template_context(output)
    return template.render(**context)


def save_outputs(output: EngineOutput, output_dir: str | Path) -> dict[str, Path]:
    """Save both JSON and Markdown to output_dir. Returns the paths."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "topical_map.json"
    md_path = out_dir / "topical_map_report.md"

    # JSON
    json_path.write_text(json.dumps(output.model_dump(mode="json"), indent=2))

    # Markdown
    md_path.write_text(render_markdown(output))

    # CSV (Koray format)
    csv_path = out_dir / "topical_map.csv"
    csv_path.write_text(render_koray_csv(output), encoding="utf-8-sig")  # utf-8-sig for Excel

    return {"json": json_path, "markdown": md_path, "csv": csv_path}


def render_koray_csv(output: EngineOutput) -> str:
    """
    Export topical map as Koray-format CSV.

    Columns (matching the user's original CSV):
      Contextual Vector | Contextual Hierarchy | Contextual Connection | Query Terms | Volume

    Structure:
      H1  → Pillar page
      H2  → Cluster page
      H3  → Supplementary node
    """
    import csv, io
    out = io.StringIO()
    writer = csv.writer(out)

    # Header — exact match to original CSV
    writer.writerow([
        "Contextual Vector",
        "Contextual Hierarchy",
        "Contextual Connection",
        "Query Terms",
        "Volume",
    ])

    tm = output.topical_map

    # Site-level central entity
    writer.writerow([
        tm.central_entity.primary,
        "site_entity",
        tm.central_entity.source_context[:120],
        "",
        "",
    ])

    for pillar in tm.pillars:
        # H1 — Pillar
        pillar_queries = " | ".join(q.text for q in pillar.representative_queries[:3])
        writer.writerow([
            pillar.title,
            "h1",
            f"[{pillar.intent.value}] [{pillar.funnel_stage.value}] Priority {pillar.priority}",
            pillar_queries,
            "",
        ])

        for cluster in pillar.clusters:
            # H2 — Cluster
            cluster_queries = " | ".join(q.text for q in cluster.represented_queries[:3])
            writer.writerow([
                cluster.title,
                "h2",
                pillar.title,
                cluster_queries,
                "",
            ])

            # H3 — Supplementary nodes
            for node in cluster.supplementary_nodes:
                angle = f"[{node.angle}] " if node.angle else ""
                writer.writerow([
                    node.title,
                    "h3",
                    cluster.title,
                    f"{angle}{node.funnel_stage.value}",
                    "",
                ])

        # Blank separator between pillars
        writer.writerow(["", "", "", "", ""])

    return out.getvalue()
