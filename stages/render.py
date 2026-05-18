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

    return {"json": json_path, "markdown": md_path}
