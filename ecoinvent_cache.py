"""
ecoinvent_cache.py — Targeted extraction of ecoinvent processes.

Verified category path format from the database:
  "C:Manufacturing/24:Manufacture of basic metals/242:.../2420:..."
  "D:Electricity, gas, steam and air conditioning supply/35:.../351:.../3510:..."

Targets:
  metals      → C:.../24:Manufacture of basic metals  (includes 241, 242, 243)
  electricity → D:Electricity, gas, steam...           (includes 35, 351, 3510)
  inert_gases → by NAME only (argon, nitrogen) from any category
  waste       → by NAME only (metal scrap + recycling)
"""
import json
import time
from pathlib import Path

CACHE_FILE = Path(__file__).parent / "ecoinvent_cache.json"


def diagnose_categories(port: int, sample_size: int = 200) -> list[dict]:
    """Diagnostic: sample category strings from the database."""
    import olca_ipc as ipc
    import olca_schema as schema
    client = ipc.Client(port)
    all_procs = client.get_descriptors(schema.Process)
    samples = []
    seen = set()
    for p in all_procs:
        cat = p.category or "(none)"
        prefix = cat[:80]
        if prefix not in seen:
            seen.add(prefix)
            samples.append({"name": p.name or "", "category": cat})
        if len(samples) >= sample_size:
            break
    return samples


def _classify(category: str, name: str) -> str | None:
    """Classify process. Uses exact ISIC path prefix for metals/electricity,
    name-based matching for gases and scrap."""

    cat = category or ""
    name_lower = (name or "").lower()

    # ── METALS: category starts with or contains "/24:" ───────────────
    # Catches: 24:Manufacture of basic metals, 241:..., 242:..., 243:...
    if "/24:Manufacture of basic metals" in cat or cat.startswith("C:Manufacturing/24:"):
        return "metals"

    # ── ELECTRICITY: category contains "D:Electricity" ────────────────
    if cat.startswith("D:Electricity"):
        return "electricity"

    # ── INERT GASES: by name (they're scattered across 20:Chemicals etc) ──
    if any(g in name_lower for g in [
        "argon", "nitrogen, liquid", "nitrogen production",
        "air separation", "oxygen, liquid",
    ]):
        return "inert_gases"

    # ── SCRAP RECYCLING: by name, must be metal-specific ──────────────
    if any(s in name_lower for s in ["scrap", "recycling of"]):
        if any(m in name_lower for m in [
            "metal", "steel", "iron", "alumin", "copper",
            "nickel", "titanium", "chromium", "zinc", "tin",
        ]):
            return "waste_treatment"

    return None


def _extract_exchanges(client, process_id: str) -> dict:
    """Get input/output exchanges for a process."""
    try:
        import olca_schema as o
        proc = client.get(o.Process, process_id)
        if not proc or not proc.exchanges:
            return {"inputs": [], "outputs": []}
        inputs, outputs = [], []
        for ex in proc.exchanges:
            entry = {
                "flow": ex.flow.name if ex.flow else "",
                "amount": ex.amount or 0,
                "unit": ex.unit.name if ex.unit else "",
            }
            (inputs if ex.is_input else outputs).append(entry)
        return {"inputs": inputs, "outputs": outputs}
    except Exception:
        return {"inputs": [], "outputs": []}


def build_cache(port: int, progress_callback=None) -> dict:
    """Build the ecoinvent subset cache. Targets ~500-1500 processes."""
    import olca_ipc as ipc
    import olca_schema as schema

    client = ipc.Client(port)

    if progress_callback:
        progress_callback("Loading process list...", 2)

    all_procs = client.get_descriptors(schema.Process)
    total = len(all_procs)

    if progress_callback:
        progress_callback(f"Classifying {total} processes by ISIC folder...", 5)

    # Classify — this is fast, no IPC calls
    relevant = []
    counts = {"metals": 0, "electricity": 0, "inert_gases": 0, "waste_treatment": 0}
    for p in all_procs:
        group = _classify(p.category or "", p.name or "")
        if group:
            relevant.append((group, p))
            counts[group] += 1

    summary = ", ".join(f"{k}: {v}" for k, v in counts.items())

    if progress_callback:
        progress_callback(
            f"✅ Classified: {len(relevant)} of {total} processes match. ({summary}). "
            f"Now extracting exchange data (1 IPC call per process)...", 10
        )

    # Extract exchanges — this is the slow part
    cache = {
        "metadata": {
            "total_ecoinvent_processes": total,
            "cached_processes": len(relevant),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "group_counts": counts,
        },
        "electricity": [], "metals": [], "inert_gases": [], "waste_treatment": [],
    }

    errors = 0
    for i, (group, proc) in enumerate(relevant):
        geo = ""
        if "|" in (proc.name or ""):
            geo = proc.name.split("|")[-1].strip()

        # Extract exchanges with timeout protection
        try:
            exchanges = _extract_exchanges(client, proc.id)
        except Exception:
            exchanges = {"inputs": [], "outputs": []}
            errors += 1

        cache[group].append({
            "uuid": proc.id,
            "name": proc.name or "",
            "category": proc.category or "",
            "geography": geo,
            "description": proc.description or "",
            "exchanges": exchanges,
        })

        # Progress update every 50 processes (less frequent = less UI strain)
        if progress_callback and (i % 50 == 0 or i == len(relevant) - 1):
            pct = 10 + int(85 * (i + 1) / len(relevant))
            progress_callback(
                f"Extracting {i+1}/{len(relevant)}: {(proc.name or '')[:50]}...",
                min(pct, 96),
            )

        # Save intermediate checkpoint every 200 processes
        if i > 0 and i % 200 == 0:
            try:
                with open(CACHE_FILE, "w", encoding="utf-8") as f:
                    json.dump(cache, f, default=str)
            except Exception:
                pass

    if progress_callback:
        progress_callback(f"Saving final cache ({len(relevant)} processes)...", 97)

    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, default=str)

    if progress_callback:
        msg = f"Done! {len(relevant)} processes cached."
        if errors:
            msg += f" ({errors} had exchange extraction errors)"
        progress_callback(msg, 100)

    return cache


def load_cache() -> dict | None:
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_cache_stats() -> dict | None:
    cache = load_cache()
    if not cache:
        return None
    meta = cache.get("metadata", {})
    return {
        "timestamp": meta.get("timestamp", "unknown"),
        "total_ecoinvent": meta.get("total_ecoinvent_processes", 0),
        "cached": meta.get("cached_processes", 0),
        "electricity": len(cache.get("electricity", [])),
        "metals": len(cache.get("metals", [])),
        "inert_gases": len(cache.get("inert_gases", [])),
        "waste_treatment": len(cache.get("waste_treatment", [])),
    }