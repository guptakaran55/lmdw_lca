import olca_ipc as ipc
import olca_schema as schema

client = ipc.Client(8080)
all_procs = client.get_descriptors(schema.Process)

# Count how many match each filter
metals = 0
electricity = 0
no_cat = 0
samples = {"metals": [], "electricity": [], "unmatched_24": [], "unmatched_D": []}

for p in all_procs:
    cat = p.category or ""
    name = p.name or ""
    
    if "/24:Manufacture of basic metals" in cat or cat.startswith("C:Manufacturing/24:"):
        metals += 1
        if len(samples["metals"]) < 3:
            samples["metals"].append(f"  CAT: {cat}\n  NAME: {name}")
    elif cat.startswith("D:Electricity"):
        electricity += 1
        if len(samples["electricity"]) < 3:
            samples["electricity"].append(f"  CAT: {cat}\n  NAME: {name}")
    
    # Check if "24:" appears anywhere but our filter misses it
    if "/24:" in cat and "basic metals" not in cat.lower():
        if len(samples["unmatched_24"]) < 5:
            samples["unmatched_24"].append(f"  CAT: {cat}")
    
    if not cat:
        no_cat += 1

print(f"TOTAL PROCESSES: {len(all_procs)}")
print(f"METALS (24:): {metals}")
print(f"ELECTRICITY (D:): {electricity}")
print(f"NO CATEGORY: {no_cat}")
print(f"\n--- METAL SAMPLES ---")
for s in samples["metals"]: print(s)
print(f"\n--- ELECTRICITY SAMPLES ---")
for s in samples["electricity"]: print(s)
print(f"\n--- CATEGORIES WITH /24: BUT NOT 'basic metals' ---")
for s in samples["unmatched_24"]: print(s)
print(f"\n--- FIRST 10 RAW CATEGORY STRINGS ---")
for p in all_procs[:10]:
    print(f"  [{repr(p.category)}]")