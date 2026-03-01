"""
olca_client.py — All openLCA IPC communication.
Fixed: olca-ipc Client only takes port (not host), proper exchange/flow creation.
"""
from typing import Optional
import uuid

# Lazy import — olca-ipc may not be installed
_ipc = None
_schema = None

def _load_olca():
    global _ipc, _schema
    if _ipc is None:
        try:
            import olca_ipc as ipc
            import olca_schema as schema
            _ipc = ipc
            _schema = schema
        except ImportError:
            raise ImportError(
                "olca-ipc not installed. Run: pip install olca-ipc olca-schema"
            )
    return _ipc, _schema


def test_connection(port: int = 8080):
    """Test connection to openLCA IPC server. Returns (success, message)."""
    try:
        ipc, schema = _load_olca()
        client = ipc.Client(port)
        methods = client.get_descriptors(schema.ImpactMethod)
        return True, f"Connected. Found {len(methods)} LCIA methods."
    except ImportError as e:
        return False, str(e)
    except Exception as e:
        return False, f"Connection failed on port {port}: {e}"


def get_lcia_methods(port: int) -> list:
    try:
        ipc, schema = _load_olca()
        client = ipc.Client(port)
        return [m.name for m in client.get_descriptors(schema.ImpactMethod)]
    except Exception:
        return []


def search_processes(port: int, keywords: list[str], limit: int = 100) -> list:
    """Search openLCA processes by keywords. Returns list of {name, id, category}."""
    try:
        ipc, schema = _load_olca()
        client = ipc.Client(port)
        all_procs = client.get_descriptors(schema.Process)
        matches = []
        for p in all_procs:
            name_lower = (p.name or "").lower()
            if any(kw.lower() in name_lower for kw in keywords):
                geo = ""
                if "|" in (p.name or ""):
                    geo = p.name.split("|")[-1].strip()
                matches.append({"name": p.name, "id": p.id, "geography": geo})
                if len(matches) >= limit:
                    break
        return matches
    except Exception:
        return []


def find_process(port: int, name_fragment: str):
    """
    Find first process matching name fragment. Uses multi-keyword fuzzy search.
    e.g. "titanium, primary | GLO" tries: exact → "titanium" + "primary" + "GLO" → "titanium" alone
    Returns descriptor or None.
    """
    try:
        ipc, schema = _load_olca()
        client = ipc.Client(port)
        all_procs = client.get_descriptors(schema.Process)

        # 1. Try exact substring match
        frag_lower = name_fragment.lower().strip()
        for p in all_procs:
            if frag_lower in (p.name or "").lower():
                return p

        # 2. Try all keywords together (split on punctuation)
        import re
        keywords = [w.strip().lower() for w in re.split(r'[,|/\s]+', name_fragment) if len(w.strip()) > 1]
        if keywords:
            for p in all_procs:
                pname = (p.name or "").lower()
                if all(kw in pname for kw in keywords):
                    return p

        # 3. Try just the main keyword (first significant word)
        main_keywords = [kw for kw in keywords if kw not in ("glo", "rer", "de", "us", "cn", "fr", "gb")]
        if main_keywords:
            for p in all_procs:
                pname = (p.name or "").lower()
                if all(kw in pname for kw in main_keywords):
                    return p

        # 4. Try just the first keyword
        if main_keywords:
            for p in all_procs:
                if main_keywords[0] in (p.name or "").lower():
                    return p

        return None
    except Exception:
        return None


def list_matching_processes(port: int, keyword: str, limit: int = 20) -> list:
    """Debug helper: list all processes containing a keyword."""
    try:
        ipc, schema = _load_olca()
        client = ipc.Client(port)
        matches = []
        for p in client.get_descriptors(schema.Process):
            if keyword.lower() in (p.name or "").lower():
                matches.append(p.name)
                if len(matches) >= limit:
                    break
        return matches
    except Exception:
        return []


def build_and_calculate_by_uuid(port: int, wire_uuid: str,
                                 wire_amount_kg: float,
                                 lcia_method: str) -> dict:
    """
    Build product system from a process UUID and run LCA.
    
    This is the UUID-based approach: the AI matcher already identified the
    correct process and its UUID, so we use it directly — no name matching.
    
    Args:
        port: openLCA IPC port
        wire_uuid: UUID of the ecoinvent process (from AI matcher / cache)
        wire_amount_kg: amount in kg (wire_per_ml / 1000)
        lcia_method: LCIA method name substring (e.g. "ReCiPe 2016 Midpoint (H)")
    
    Returns {success, results, error}
    """
    try:
        ipc, o = _load_olca()
        client = ipc.Client(port)

        # ── 1. Create product system from the process UUID ────────────────
        # create_product_system auto-links all upstream providers
        ps = client.create_product_system(wire_uuid)

        ps_id = ps.id if hasattr(ps, 'id') else str(ps)

        if not ps_id:
            return {"success": False,
                    "error": f"Failed to create product system from UUID {wire_uuid}"}

        # ── 2. Find LCIA method ──────────────────────────────────────────
        method_ref = None
        for m in client.get_descriptors(o.ImpactMethod):
            if lcia_method.lower() in (m.name or "").lower():
                method_ref = m
                break

        if not method_ref:
            available = [m.name for m in client.get_descriptors(o.ImpactMethod)]
            recipe_avail = [n for n in available if "recipe" in n.lower()]
            return {"success": False,
                    "error": f"LCIA method '{lcia_method}' not found. "
                             f"Available ReCiPe: {recipe_avail[:5]}"}

        # ── 3. Run calculation ────────────────────────────────────────────
        setup = o.CalculationSetup()
        setup.target = o.Ref()
        setup.target.id = ps_id
        setup.target.ref_type = o.RefType.ProductSystem
        setup.impact_method = o.Ref()
        setup.impact_method.id = method_ref.id
        setup.impact_method.name = method_ref.name
        setup.amount = wire_amount_kg

        result = client.calculate(setup)
        result.wait_until_ready()

        # ── 4. Extract results ────────────────────────────────────────────
        impacts = {}
        for impact in result.get_total_impacts():
            cat_name = impact.impact_category.name or ""
            impacts[cat_name] = impact.amount

        result.dispose()

        if not impacts:
            return {"success": False,
                    "error": "Calculation returned no results. Check LCIA method."}

        return {"success": True, "results": impacts}

    except Exception as e:
        return {"success": False, "error": str(e)}