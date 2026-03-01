# 🔬 LMD-W LCA Platform

Streamlit-based Life Cycle Assessment tool for Laser Metal Deposition — Wire (LMD-W), powered by openLCA + ecoinvent + Claude AI.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env        # Add your Anthropic API key
streamlit run app.py
```

## Setup openLCA

1. Open openLCA, import ecoinvent 3.10 (cutoff) + ReCiPe 2016
2. **Window → Developer Tools → IPC Server → Start** (port 8080)
3. Connect from the app's Connection page

## Project Structure

```
app.py              # Main Streamlit app (all pages)
config.py           # Credentials, constants, material data
olca_client.py      # openLCA IPC communication
ai_matcher.py       # Claude AI process matching
.env.example        # Template for API keys
requirements.txt
```

## Workflow

1. **Connect** to openLCA IPC server
2. **AI Match** — describe materials, AI finds ecoinvent processes
3. **Inventory** — enter wire/electricity/argon per 1 ml
4. **Calculate** — build product system + run ReCiPe LCIA
5. **Results** — midpoint, normalized, export

## Functional Unit

**1 ml of final LMD-W printed part**

| Flow | Type | Unit |
|------|------|------|
| Metal wire | Input | g/ml |
| Electricity | Input | kWh/ml |
| Argon gas | Input | L/ml |
| Scrap metal | Output | g/ml |
