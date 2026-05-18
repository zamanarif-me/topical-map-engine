"""Home page — hero + feature overview."""

import streamlit as st


def render_home():
    col1, col2 = st.columns([3, 2])

    with col1:
        st.markdown("""
<div class="hero-title">
    Topical Map<br>
    <em>Engine</em>
</div>
<div class="hero-subtitle">
    Generate Koray-framework semantic topical maps,
    query networks, and content briefs — powered by
    Anthropic, Serper, and Gemini.
</div>
""", unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        col_a, col_b = st.columns([1, 2])
        with col_a:
            if st.button("🗺️  New Project", use_container_width=True):
                st.session_state.page = "intake"
                st.rerun()

        if st.session_state.get("output"):
            with col_b:
                if st.button("📊  View Last Results", use_container_width=True):
                    st.session_state.page = "results"
                    st.rerun()

    with col2:
        st.markdown("""
<div style="display:flex; flex-direction:column; gap:0.8rem; padding-top:1rem;">

<div class="metric-card">
    <div class="metric-value">88%</div>
    <div class="metric-label">Koray Framework Coverage</div>
</div>

<div class="metric-card">
    <div class="metric-value">9</div>
    <div class="metric-label">Pipeline Stages</div>
</div>

<div class="metric-card">
    <div class="metric-value">~$1</div>
    <div class="metric-label">Cost per Topical Map</div>
</div>

</div>
""", unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # Feature grid
    st.markdown("### What it builds")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("""
**🏛️ Topical Map**
Pillar / Cluster / Supplementary hierarchy with intent tagging, funnel stages, and Core/Outer section distinction.
""")
    with c2:
        st.markdown("""
**🔗 Query Network**
Representative + represented queries enriched with real PAA data from Serper SERP pulls.
""")
    with c3:
        st.markdown("""
**📝 Content Briefs**
Per-page briefs with information gain angles, entity attribute maps, heading structures, and semantic bridges.
""")

    c4, c5, c6 = st.columns(3)
    with c4:
        st.markdown("""
**🌐 Internal Linking**
Directed link graph with entity bridge weights. Pillar↔cluster links generated deterministically.
""")
    with c5:
        st.markdown("""
**✅ Web Validation**
Topics validated against real SERP data — strong / medium / weak signal per pillar.
""")
    with c6:
        st.markdown("""
**📦 Export**
JSON + Markdown report for every run. Content briefs as individual downloadable files.
""")
