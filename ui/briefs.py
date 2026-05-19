"""Briefs page."""
import streamlit as st
from pathlib import Path


def render_briefs():
    output = st.session_state.get("output")
    output_dir = st.session_state.get("output_dir", "streamlit_output")

    if not output:
        st.warning("No topical map found. Generate one first.")
        if st.button("← Back to home"):
            st.session_state.page = "home"
            st.rerun()
        return

    tm = output.topical_map

    if st.button("← Results"):
        st.session_state.page = "results"
        st.rerun()

    st.markdown("## 📝 Content Brief Generator")

    pillar_map = {f"P{p.priority} — {p.title}": p for p in tm.pillars}
    selected_label = st.selectbox("Select pillar", list(pillar_map.keys()))
    pillar = pillar_map[selected_label]

    max_clusters = st.slider("Cluster briefs", 0, min(len(pillar.clusters), 5), min(2, len(pillar.clusters)))

    total = 1 + max_clusters
    st.markdown(f"**{total} briefs** · ~${0.12 + max_clusters * 0.10:.2f}")

    package_key = f"pkg_{pillar.id}_{max_clusters}"

    if st.button("🚀 Generate Briefs", use_container_width=True):
        from stages.brief import generate_brief_for_pillar, generate_brief_for_cluster, save_briefs
        briefs = {}
        errors = {}

        with st.status("Generating...", expanded=True) as s:
            st.write(f"📄 Pillar: {pillar.title[:60]}")
            try:
                briefs[pillar.id] = generate_brief_for_pillar(pillar, tm)
                st.write("  ✅ Done")
            except Exception as e:
                errors[pillar.id] = str(e)
                st.write(f"  ❌ {str(e)[:80]}")

            for i, cluster in enumerate(pillar.clusters[:max_clusters]):
                st.write(f"📄 Cluster {i+1}: {cluster.title[:55]}")
                try:
                    briefs[cluster.id] = generate_brief_for_cluster(cluster, pillar, tm)
                    st.write("  ✅ Done")
                except Exception as e:
                    errors[cluster.id] = str(e)
                    st.write(f"  ❌ {str(e)[:80]}")

            if briefs:
                paths = save_briefs(briefs, Path(output_dir) / "briefs")
                st.session_state[package_key] = {"briefs": briefs, "paths": paths}
                s.update(label=f"✅ {len(briefs)} briefs done!", state="complete")
            else:
                s.update(label="❌ All failed", state="error")

    pkg = st.session_state.get(package_key)
    if pkg:
        st.markdown("### Download")
        for path in pkg["paths"]:
            p = Path(path)
            if p.exists() and p.suffix == ".md" and not p.name.startswith("_"):
                st.download_button(f"📄 {p.stem}", p.read_text(), p.name, "text/markdown", key=f"dl_{p.stem}")
