"""
LMD-W LCA Platform — Main Application
Supports Anthropic (Claude) and Perplexity as LLM backends.
Run: streamlit run app.py
"""
import streamlit as st
import plotly.express as px
import pandas as pd
from config import (
    MATERIALS, ELECTRICITY_GRIDS, ARGON_KG_PER_LITER,
    OLCA_PORT, LLM_PROVIDER, RECIPE_MIDPOINT_NF,
)

# ══════════════════════════════════════════════════════════════════════════
# APP CONFIG
# ══════════════════════════════════════════════════════════════════════════
st.set_page_config(page_title="LMD-W LCA Platform", page_icon="🔬", layout="wide")

st.markdown("""<style>
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0f172a,#1e293b)}
[data-testid="stSidebar"] *{color:#e2e8f0!important}
.metric-card{background:#fff;border-radius:10px;padding:1.2rem;
  box-shadow:0 2px 12px rgba(0,0,0,.08);border-left:4px solid #0f4c81;margin-bottom:1rem}
.stButton>button{background:linear-gradient(135deg,#0f4c81,#1a6b4a);
  color:#fff;border:none;border-radius:8px;padding:.5rem 1.5rem;font-weight:600}
</style>""", unsafe_allow_html=True)

# Session defaults
for key, default in [("olca_connected", False), ("olca_port", OLCA_PORT),
                      ("inventory", None), ("lca_results", None),
                      ("matched_flows", {}), ("chat_history", []),
                      ("llm_provider", LLM_PROVIDER)]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🔬 LMD-W LCA")
    st.markdown("---")

    page = st.radio("Navigate", [
        "🏠 Home", "🔌 Connection", "🤖 AI Matcher",
        "📋 Inventory", "⚙️ Calculate", "📊 Results",
    ])

    st.markdown("---")

    # LLM provider selector
    from ai_matcher import get_provider_status
    pstatus = get_provider_status()

    provider_options = []
    provider_labels = {}
    for name, info in pstatus.items():
        icon = "✅" if info["configured"] else "❌"
        label = f"{icon} {name.title()} ({info['model']})"
        provider_options.append(name)
        provider_labels[name] = label

    selected_idx = provider_options.index(st.session_state.llm_provider) if st.session_state.llm_provider in provider_options else 0
    chosen = st.selectbox(
        "🧠 LLM Provider",
        provider_options,
        index=selected_idx,
        format_func=lambda x: provider_labels.get(x, x),
    )
    st.session_state.llm_provider = chosen

    if not pstatus.get(chosen, {}).get("configured"):
        st.warning(f"Add {chosen.upper()}_API_KEY to .env")

    st.markdown("---")

    # Status indicators
    olca_icon = "🟢" if st.session_state.olca_connected else "🔴"
    st.caption(f"openLCA: {olca_icon} {'Connected' if st.session_state.olca_connected else 'Not connected'}")

    from ecoinvent_cache import get_cache_stats
    stats = get_cache_stats()
    if stats:
        st.caption(f"📦 Cache: {stats['cached']} processes")
    else:
        st.caption("📦 Cache: not built")

    matched = st.session_state.matched_flows
    if matched:
        st.markdown("---")
        st.caption("**Matched flows:**")
        for flow_type, info in matched.items():
            st.caption(f"✅ {flow_type}: {info.get('name','?')[:30]}")

    st.markdown("---")
    st.caption("**FU:** 1 ml printed part")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════════════════
def page_home():
    st.markdown("# 🔬 LMD-W Life Cycle Assessment Platform")
    st.markdown("Sustainability intelligence for Laser Metal Deposition — Wire.")
    st.markdown("---")

    cols = st.columns(4)
    for col, (label, val) in zip(cols, [
        ("Functional Unit", "1 ml"), ("Inputs", "Wire · Elec · Argon"),
        ("Output", "Scrap metal"), ("LCIA", "ReCiPe 2016"),
    ]):
        col.metric(label, val)

    st.markdown("---")
    st.markdown("### Workflow")
    for step, desc in [
        ("1. Connect + Cache", "Connect to openLCA IPC, build ecoinvent cache (one-time)"),
        ("2. AI Match", "Describe your materials — AI searches cached database with exchange data"),
        ("3. Inventory", "Enter wire/electricity/argon per 1 ml"),
        ("4. Calculate", "Build product system from matched UUIDs, run ReCiPe LCIA"),
        ("5. Results", "Midpoint, normalized, contribution analysis"),
    ]:
        st.markdown(f"**{step}** — {desc}")

    st.markdown("---")
    st.markdown("### Two-Stage AI Matching")
    st.markdown("""
    **Stage 1** (~$0.01): All process names from the relevant ecoinvent category are sent to the LLM. 
    It picks the top 5 candidates.
    
    **Stage 2** (~$0.01): For those 5, the full input/output exchange lists are sent. 
    The LLM examines actual material flows and confirms the best match with UUID.
    
    Supports **Anthropic Claude** and **Perplexity Sonar** — switch in the sidebar.
    """)


# ══════════════════════════════════════════════════════════════════════════
# PAGE: CONNECTION + CACHE
# ══════════════════════════════════════════════════════════════════════════
def page_connection():
    st.markdown("## 🔌 Connection & Setup")

    # ── LLM Status ────────────────────────────────────────────────────────
    st.markdown("### 🧠 LLM Provider Status")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Anthropic (Claude)**")
        if pstatus["anthropic"]["configured"]:
            st.success(f"✅ Key configured — model: `{pstatus['anthropic']['model']}`")
        else:
            st.error("❌ No API key. Add `ANTHROPIC_API_KEY` to `.env`")
    with col2:
        st.markdown("**Perplexity (Sonar)**")
        if pstatus["perplexity"]["configured"]:
            st.success(f"✅ Key configured — model: `{pstatus['perplexity']['model']}`")
        else:
            st.error("❌ No API key. Add `PERPLEXITY_API_KEY` to `.env`")

    st.caption(f"Active provider: **{st.session_state.llm_provider}** (change in sidebar)")

    # ── openLCA ───────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔌 openLCA Connection")
    st.info("In openLCA: **Window → Developer Tools → IPC Server → Start** (port 8080)")

    col1, col2 = st.columns(2)
    with col1:
        port = st.number_input("Port", value=st.session_state.olca_port, min_value=1000, max_value=65535)
        if st.button("🔗 Connect to openLCA"):
            from olca_client import test_connection, get_lcia_methods
            ok, msg = test_connection(int(port))
            if ok:
                st.session_state.olca_connected = True
                st.session_state.olca_port = int(port)
                st.session_state.lcia_methods = get_lcia_methods(int(port))
                st.success(f"✅ {msg}")
            else:
                st.session_state.olca_connected = False
                st.error(f"❌ {msg}")
    with col2:
        if st.session_state.olca_connected:
            st.success("**Connected ✅**")
            methods = st.session_state.get("lcia_methods", [])
            recipe = [m for m in methods if "recipe" in m.lower()]
            if recipe:
                for m in recipe[:5]:
                    st.caption(f"• {m}")
        else:
            st.warning("Not connected")

    st.session_state.selected_lcia = st.selectbox(
        "LCIA Method", ["ReCiPe 2016 Midpoint (H)", "ReCiPe 2016 Endpoint (H)"])

    # ── Cache Building ────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📦 ecoinvent Process Cache")
    st.markdown("""
    Extracts relevant processes (metals, electricity, gases, waste) with full exchange lists.
    **Run once** after loading a new ecoinvent database. Takes 5–15 minutes.
    """)

    from ecoinvent_cache import get_cache_stats as _stats, CACHE_FILE
    cache_stats = _stats()

    if cache_stats:
        st.success(f"✅ Cache exists (built: {cache_stats['timestamp']})")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Metals", cache_stats["metals"])
        c2.metric("Electricity", cache_stats["electricity"])
        c3.metric("Inert Gases", cache_stats["inert_gases"])
        c4.metric("Waste Treatment", cache_stats["waste_treatment"])
    else:
        st.warning("No cache. Build it to enable AI matching.")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🏗️ Build Cache", disabled=not st.session_state.olca_connected):
            from ecoinvent_cache import build_cache
            progress = st.progress(0)
            status_text = st.empty()

            def _update(msg, pct):
                status_text.text(msg)
                progress.progress(min(pct, 100))

            cache = build_cache(st.session_state.olca_port, progress_callback=_update)
            status_text.empty()
            progress.empty()
            n = cache.get("metadata", {}).get("cached_processes", 0)
            st.success(f"✅ {n} processes cached!")
            st.rerun()

    with col2:
        if cache_stats and st.button("🗑️ Delete Cache"):
            import os
            os.remove(CACHE_FILE)
            st.rerun()

    with col3:
        if st.button("🔍 Diagnose Categories", disabled=not st.session_state.olca_connected):
            from ecoinvent_cache import diagnose_categories
            with st.spinner("Sampling process categories..."):
                samples = diagnose_categories(st.session_state.olca_port, sample_size=150)
            st.session_state._cat_samples = samples

    # Show diagnostic results
    if st.session_state.get("_cat_samples"):
        with st.expander("🔍 Category format samples (from your database)", expanded=True):
            st.caption("These show what the `.category` field looks like in your ecoinvent version.")
            for s in st.session_state._cat_samples[:80]:
                st.text(f"CAT: {s['category']}\n  → {s['name'][:70]}")
                st.markdown("---")

    # ── Cache Browser ─────────────────────────────────────────────────────
    if cache_stats:
        with st.expander("🔎 Browse cached processes"):
            cat = st.selectbox("Category", ["metals", "electricity", "inert_gases", "waste_treatment"])
            from ecoinvent_cache import load_cache
            cache = load_cache()
            if cache:
                procs = cache.get(cat, [])
                filt = st.text_input("Filter", placeholder="e.g. titanium, medium voltage...")
                if filt:
                    procs = [p for p in procs if filt.lower() in p["name"].lower()]
                st.caption(f"{len(procs)} processes")
                for p in procs[:30]:
                    with st.expander(f"{p['name']} | {p.get('geography','')}"):
                        st.code(f"UUID: {p['uuid']}")
                        if p.get("description"):
                            st.caption(p["description"][:200])
                        ex = p.get("exchanges", {})
                        for label, flows in [("Inputs", ex.get("inputs", [])), ("Outputs", ex.get("outputs", []))]:
                            if flows:
                                st.markdown(f"**{label}:**")
                                for e in sorted(flows, key=lambda x: abs(x.get("amount", 0)), reverse=True)[:8]:
                                    st.caption(f"  {e['flow']}: {e['amount']:.4g} {e['unit']}")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: AI MATCHER
# ══════════════════════════════════════════════════════════════════════════
def page_ai_matcher():
    st.markdown("## 🤖 AI Process Matcher")

    provider = st.session_state.llm_provider
    pinfo = pstatus.get(provider, {})
    if pinfo.get("configured"):
        st.success(f"Using **{provider.title()}** ({pinfo['model']})")
    else:
        st.error(f"No API key for {provider}. Add it to `.env` or switch provider in sidebar.")
        return

    cache_stats = get_cache_stats()
    if not cache_stats:
        st.error("⚠️ No ecoinvent cache. Go to **Connection** page and build it first.")
        return

    st.caption(f"📦 {cache_stats['metals']} metals · {cache_stats['electricity']} electricity · "
               f"{cache_stats['inert_gases']} gases · {cache_stats['waste_treatment']} waste")

    # ── Flow selection ────────────────────────────────────────────────────
    category_map = {
        "🔩 Metal Wire (feedstock)": "metals",
        "⚡ Electricity": "electricity",
        "🌀 Shielding Gas (Argon/N₂)": "inert_gases",
        "♻️ Scrap Treatment": "waste_treatment",
    }
    flow_type = st.selectbox("Flow type", list(category_map.keys()))
    category = category_map[flow_type]

    placeholders = {
        "metals": "e.g. Ti-6Al-4V titanium alloy wire, aerospace grade, global supply",
        "electricity": "e.g. German grid mix, medium voltage, industrial manufacturing in Dortmund",
        "inert_gases": "e.g. Industrial argon, 99.999% purity, shielding gas for laser welding",
        "waste_treatment": "e.g. Titanium machining scrap, open-loop metal recycling",
    }
    description = st.text_area("Describe your process:", placeholder=placeholders.get(category, ""),
                                height=100)

    if st.button("🔍 Find Best Match", disabled=not description):
        with st.spinner(f"Stage 1: Scanning {category} ({provider})..."):
            from ai_matcher import match_process
            result = match_process(description, category)

        if "error" in result:
            st.error(result["error"])
            return

        # Stage 1 candidates
        candidates = result.get("stage1_candidates", [])
        if candidates:
            with st.expander(f"📋 Stage 1 candidates ({len(candidates)})", expanded=False):
                for c in candidates:
                    st.markdown(f"- **{c.get('name','')}** — {c.get('reason','')}")

        # Best match
        best = result.get("best_match")
        if best:
            st.markdown("---")
            st.markdown("### ✅ Best Match")
            st.markdown(f"**{best['name']}**")
            st.code(f"UUID: {best['uuid']}")
            st.markdown(f"Confidence: **{best.get('confidence', '?')}%** | Provider: {result.get('provider', provider)}")
            st.markdown(f"_{best.get('reason', '')}_")

            if result.get("warnings"):
                st.warning(f"⚠️ {result['warnings']}")

            alts = result.get("alternatives", [])
            if alts:
                with st.expander("Other options"):
                    for a in alts:
                        st.markdown(f"- **{a.get('name','')}** (`{a.get('uuid','')}`) — {a.get('reason','')}")

            flow_label = flow_type.split("(")[0].strip()
            for prefix in ["🔩 ", "⚡ ", "🌀 ", "♻️ "]:
                flow_label = flow_label.replace(prefix, "")
            flow_label = flow_label.strip()

            if st.button(f"✅ Use this for {flow_label}"):
                st.session_state.matched_flows[flow_label] = {
                    "uuid": best["uuid"],
                    "name": best["name"],
                    "confidence": best.get("confidence", 0),
                    "category": category,
                }
                st.success(f"Saved: **{best['name']}**")
                st.rerun()
        else:
            st.warning("No match found. Try rephrasing.")

    # ── Current selections ────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### Matched Flows")
    if not st.session_state.matched_flows:
        st.info("No flows matched yet.")
    else:
        for fname, info in st.session_state.matched_flows.items():
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"**{fname}:** {info['name']} (`{info['uuid'][:12]}...`) — {info.get('confidence','')}%")
            if c2.button("🗑️", key=f"rm_{fname}"):
                del st.session_state.matched_flows[fname]
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════
# PAGE: INVENTORY
# ══════════════════════════════════════════════════════════════════════════
def page_inventory():
    st.markdown("## 📋 Process Inventory")
    st.markdown("Enter measured data per **1 ml of final printed part**.")

    col1, col2 = st.columns(2)
    company = col1.text_input("Company", placeholder="e.g. AeroTech GmbH")
    study = col2.text_input("Study name", placeholder="e.g. Baseline 2024")

    material = st.selectbox("Wire alloy", list(MATERIALS.keys()))
    density = MATERIALS[material]["density"]
    st.caption(f"Density: {density} g/ml")

    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        wire_per_ml = st.number_input("Wire input (g/ml)", value=round(density * 1.4, 2),
                                       min_value=0.01, step=0.01)
        excess = (wire_per_ml - density) / density * 100
        st.caption(f"Theoretical min: {density} g/ml | Excess: {excess:.1f}%")
        argon_per_ml = st.number_input("Argon (L/ml)", value=0.85, min_value=0.0, step=0.05)

    with col2:
        elec_per_ml = st.number_input("Electricity (kWh/ml)", value=0.045, min_value=0.001, step=0.001)
        grid = st.selectbox("Grid", [f"{k} - {v}" for k, v in ELECTRICITY_GRIDS.items()])
        grid_code = grid.split(" - ")[0]
        scrap_pct = st.slider("Scrap ratio (%)", 0, 80, 30)

    scrap_mass = wire_per_ml * scrap_pct / 100

    st.markdown("---")
    summary = pd.DataFrame({
        "Flow": ["Metal wire", "Electricity", "Argon", "Scrap (output)"],
        "Value": [f"{wire_per_ml:.3f} g", f"{elec_per_ml:.4f} kWh",
                  f"{argon_per_ml:.3f} L", f"{scrap_mass:.3f} g"],
    })
    st.dataframe(summary, use_container_width=True, hide_index=True)

    if st.button("💾 Save Inventory"):
        st.session_state.inventory = {
            "company": company, "study": study, "material": material,
            "density": density, "wire_per_ml": wire_per_ml,
            "elec_per_ml": elec_per_ml, "grid_code": grid_code,
            "argon_per_ml": argon_per_ml, "scrap_pct": scrap_pct,
            "scrap_mass": scrap_mass,
        }
        st.success("✅ Saved. Proceed to Calculate →")


# ══════════════════════════════════════════════════════════════════════════
# PAGE: CALCULATE
# ══════════════════════════════════════════════════════════════════════════
def page_calculate():
    st.markdown("## ⚙️ Build & Calculate")

    inv = st.session_state.inventory
    matched = st.session_state.matched_flows

    checks = [
        ("openLCA connected", st.session_state.olca_connected),
        ("Inventory saved", inv is not None),
        ("Wire process matched", "Metal Wire" in matched),
        ("Electricity matched", "Electricity" in matched),
    ]

    st.markdown("### Pre-flight checks")
    all_ok = True
    for label, ok in checks:
        st.markdown(f"{'✅' if ok else '❌'} {label}")
        if not ok:
            all_ok = False

    for optional in ["Shielding Gas", "Scrap Treatment"]:
        if optional in matched:
            st.markdown(f"✅ {optional} matched")
        else:
            st.caption(f"ℹ️ {optional} not matched (optional)")

    if not all_ok:
        st.warning("Complete required steps first.")
        return

    st.markdown("---")
    st.markdown("### Matched UUIDs")
    for fname, info in matched.items():
        st.markdown(f"- **{fname}:** `{info['uuid']}` — {info['name']}")

    lcia = st.session_state.get("selected_lcia", "ReCiPe 2016 Midpoint (H)")
    st.markdown(f"- **LCIA:** {lcia}")
    st.markdown("---")

    if st.button("🚀 Build & Calculate in openLCA"):
        with st.spinner("Building product system and calculating..."):
            from olca_client import build_and_calculate_by_uuid
            result = build_and_calculate_by_uuid(
                port=st.session_state.olca_port,
                wire_uuid=matched["Metal Wire"]["uuid"],
                wire_amount_kg=inv["wire_per_ml"] / 1000.0,
                lcia_method=lcia,
            )
        if result["success"]:
            st.session_state.lca_results = result["results"]
            st.success("✅ Done! Go to Results →")
            st.balloons()
        else:
            st.error(f"Error: {result['error']}")

    st.markdown("---")
    if st.button("📥 Load demo results"):
        st.session_state.lca_results = _demo_results()
        st.success("Demo loaded.")


def _demo_results():
    return {
        "Global warming": 3.44, "Fine particulate matter formation": 0.023,
        "Fossil resource scarcity": 0.95, "Human carcinogenic toxicity": 4.20,
        "Human non-carcinogenic toxicity": 35.0, "Terrestrial acidification": 0.076,
        "Freshwater eutrophication": 0.0036, "Marine eutrophication": 0.00046,
        "Terrestrial ecotoxicity": 179.0, "Freshwater ecotoxicity": 1.32,
        "Marine ecotoxicity": 1.79, "Ionizing radiation": 0.80, "Land use": 0.12,
        "Mineral resource scarcity": 0.58, "Stratospheric ozone depletion": 2.1e-6,
        "Ozone formation, Human health": 0.0095,
        "Ozone formation, Terrestrial ecosystems": 0.0099, "Water consumption": 0.25,
    }


# ══════════════════════════════════════════════════════════════════════════
# PAGE: RESULTS
# ══════════════════════════════════════════════════════════════════════════
def page_results():
    st.markdown("## 📊 LCA Results")

    results = st.session_state.lca_results
    if not results:
        st.info("No results yet. Run a calculation first.")
        return

    inv = st.session_state.inventory or {}
    st.caption(f"Company: {inv.get('company','—')} | Material: {inv.get('material','—')} | FU: 1 ml")

    tab1, tab2, tab3 = st.tabs(["📊 Midpoint", "🎯 Normalized", "📄 Export"])

    with tab1:
        rows = [{"Category": k, "Value": v} for k, v in results.items() if isinstance(v, (int, float))]
        df = pd.DataFrame(rows).sort_values("Value", ascending=True)
        df["Relative"] = df["Value"].abs() / df["Value"].abs().max()
        fig = px.bar(df, x="Relative", y="Category", orientation="h",
                     color="Relative", color_continuous_scale="Blues", height=550)
        fig.update_layout(showlegend=False, coloraxis_showscale=False,
                          plot_bgcolor="white", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(df[["Category", "Value"]].style.format({"Value": "{:.5g}"}),
                      use_container_width=True, hide_index=True)

    with tab2:
        st.markdown("### Normalized Midpoint Results")
        st.caption("ReCiPe 2016 World (2010) H per person/yr")

        norm_rows = []
        for cat, val in results.items():
            if cat in RECIPE_MIDPOINT_NF and isinstance(val, (int, float)):
                nv = val / RECIPE_MIDPOINT_NF[cat]
                norm_rows.append({"Category": cat, "Characterized": val, "Normalized": nv})

        if norm_rows:
            ndf = pd.DataFrame(norm_rows).sort_values("Normalized", ascending=False)
            total = ndf["Normalized"].sum()
            ndf["Share %"] = (ndf["Normalized"] / total * 100).round(2)

            fig2 = px.bar(ndf.head(10), x="Normalized", y="Category", orientation="h",
                           color="Share %", color_continuous_scale="Reds", height=400)
            fig2.update_layout(plot_bgcolor="white", yaxis_title="")
            st.plotly_chart(fig2, use_container_width=True)
            st.dataframe(ndf[["Category", "Characterized", "Normalized", "Share %"]].style.format({
                "Characterized": "{:.5g}", "Normalized": "{:.4e}", "Share %": "{:.1f}%"
            }), use_container_width=True, hide_index=True)
            st.info(f"🔥 **Top:** {ndf.iloc[0]['Category']} ({ndf.iloc[0]['Share %']:.1f}%)")

    with tab3:
        export_df = pd.DataFrame([{"Category": k, "Value": v} for k, v in results.items()
                                   if isinstance(v, (int, float))])
        csv = export_df.to_csv(index=False)
        st.download_button("📥 CSV", csv, "lca_results.csv", "text/csv")
        st.dataframe(export_df, use_container_width=True, hide_index=True)


# ══════════════════════════════════════════════════════════════════════════
# ROUTING
# ══════════════════════════════════════════════════════════════════════════
{"🏠 Home": page_home, "🔌 Connection": page_connection, "🤖 AI Matcher": page_ai_matcher,
 "📋 Inventory": page_inventory, "⚙️ Calculate": page_calculate, "📊 Results": page_results}[page]()