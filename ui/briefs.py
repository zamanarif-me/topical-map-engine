"""Briefs page — generate and download content briefs per pillar."""

import streamlit as st
from pathlib import Path


def render_briefs():
    output = st.session_state.get("output")

    if not output:
        st.warning("No topical map found. Generate one first.")
        if st.button("← Back to home"):
            st.session_state.page = "home"
            st.rerun()
        return

    tm = output.topical_map

    col_nav, col_title = st.columns([1, 5])
    with col_nav:
        if st.button("← Results"):
            st.session_state.page = "results"
            st.rerun()
    with col_title:
        st.markdown("## 📝 Content Brief Generator")
        st.markdown("Generate full content briefs for any pillar and its clusters.")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Pillar selector ───────────────────────────────────────────────────────
    pillar_map = {f"P{p.priority} — {p.title}": p for p in tm.pillars}
    preselected = st.session_state.get("brief_target_pillar_id")

    default_idx = 0
    if preselected:
        for i, p in enumerate(tm.pillars):
            if p.id == preselected:
                default_idx = i
                break

    selected_label = st.selectbox(
        "Select pillar",
        list(pillar_map.keys()),
        index=default_idx,
    )
    pillar = pillar_map[selected_label]

    col1, col2 = st.columns(2)
    with col1:
        max_clusters = st.slider(
            "Number of cluster briefs",
            min_value=0,
            max_value=len(pillar.clusters),
            value=min(3, len(pillar.clusters)),
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        total_briefs = 1 + max_clusters
        est_cost = 0.12 + max_clusters * 0.10
        st.markdown(f"**{total_briefs} briefs** · estimated cost **~${est_cost:.2f}**")

    # Cluster preview
    if max_clusters > 0:
        st.markdown("**Clusters that will get briefs:**")
        for c in pillar.clusters[:max_clusters]:
            st.markdown(f"  • {c.title}")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Generate button ───────────────────────────────────────────────────────
    brief_key = f"briefs_{pillar.id}_{max_clusters}"

    if st.button("🚀 Generate Briefs", use_container_width=True):
        output_dir = Path(st.session_state.get("output_dir", "streamlit_output")) / "briefs"

        progress = st.progress(0)
        status = st.empty()

        try:
            from stages.brief_batch import run_batch_for_pillar
            import builtins

            original_print = print
            def ui_print(*args, **kwargs):
                msg = " ".join(str(a) for a in args)
                status.markdown(f"*{msg}*")
                original_print(*args, **kwargs)

            builtins.print = ui_print

            package = run_batch_for_pillar(
                pillar=pillar,
                topical_map=tm,
                output_dir=output_dir,
                include_clusters=max_clusters > 0,
                max_clusters=max_clusters,
                delay_between_calls=0.5,
                auto_correct_ids=True,
            )
            st.session_state[brief_key] = package
            progress.progress(1.0)
            status.markdown("✅ **Briefs generated!**")

        except Exception as e:
            st.error(f"Brief generation failed: {e}")
            import traceback
            st.code(traceback.format_exc())
            return
        finally:
            builtins.print = original_print

    # ── Show results if available ─────────────────────────────────────────────
    package = st.session_state.get(brief_key)
    if package:
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)
        st.markdown(f"### Results: {package.total_generated} briefs")

        # Validation summary
        if package.validation:
            total_issues = sum(len(r.issues) for r in package.validation.values())
            if total_issues == 0:
                st.success(f"✅ All {package.total_generated} briefs validated — no broken page IDs.")
            else:
                st.warning(f"⚠️ {total_issues} broken page IDs found and auto-corrected.")

        # Download buttons
        st.markdown("**Download individual briefs:**")
        for path in package.get_markdown_paths():
            if path.exists() and not path.name.startswith("_"):
                st.download_button(
                    label=f"📄 {path.stem}",
                    data=path.read_text(),
                    file_name=path.name,
                    mime="text/markdown",
                    key=f"dl_{path.stem}",
                )

        # Also offer JSON bundle
        json_path = Path(st.session_state.get("output_dir", "streamlit_output")) / "briefs" / "all_briefs.json"
        if json_path.exists():
            st.download_button(
                label="📦 all_briefs.json (full bundle)",
                data=json_path.read_text(),
                file_name="all_briefs.json",
                mime="application/json",
                key="dl_all_briefs",
            )

        # Brief preview
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("**Preview:**")
        for page_id, brief in package.briefs.items():
            with st.expander(f"📄 {brief.page_title}"):
                st.markdown(f"**Information Gain:** {brief.information_gain_angle}")
                st.markdown(f"**Journey Stage:** `{brief.queries.journey_stage}`")
                st.markdown(f"**Word Count:** {brief.content_specs.recommended_word_count:,}")
                st.markdown(f"**Primary Query:** `{brief.queries.primary_query}`")
                st.markdown("")
                st.markdown("**Heading Structure:**")
                for h in brief.headings:
                    indent = "&nbsp;" * (int(h.level[1]) - 1) * 4
                    st.markdown(
                        f"{indent}**{h.level}:** {h.text}",
                        unsafe_allow_html=True,
                    )
                st.markdown("")
                st.markdown(f"**Semantic Bridges ({len(brief.semantic_bridges)}):**")
                for b in brief.semantic_bridges[:3]:
                    strength = float(b.relationship_strength) if b.relationship_strength else 0.0
                    st.markdown(f"  • [{strength:.2f}] `{b.link_destination}` — *{b.anchor_suggestion}*")
