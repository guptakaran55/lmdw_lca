"""
config.py — Single source of truth for credentials, constants, material data.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── LLM Provider ──────────────────────────────────────────────────────────
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" or "perplexity"

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

# Perplexity
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-pro")

# openLCA
OLCA_PORT = int(os.getenv("OLCA_PORT", 8080))
DEFAULT_COUNTRY = os.getenv("DEFAULT_COUNTRY", "DE")

# ── Material Densities (g/ml) ─────────────────────────────────────────────
MATERIALS = {
    "Ti-6Al-4V":             {"density": 4.43, "family": "titanium"},
    "Inconel 625":           {"density": 8.44, "family": "nickel"},
    "Inconel 718":           {"density": 8.19, "family": "nickel"},
    "Stainless Steel 316L":  {"density": 7.99, "family": "steel"},
    "Stainless Steel 304":   {"density": 7.93, "family": "steel"},
    "Aluminum 4043":         {"density": 2.68, "family": "aluminium"},
    "Aluminum 5356":         {"density": 2.64, "family": "aluminium"},
    "Copper (pure)":         {"density": 8.96, "family": "copper"},
    "CoWaloy (Ni-Cr-W-Co)": {"density": 9.10, "family": "nickel"},
}

# ── Electricity grids ─────────────────────────────────────────────────────
ELECTRICITY_GRIDS = {
    "DE": "Germany",  "FR": "France",   "IT": "Italy",    "ES": "Spain",
    "GB": "United Kingdom", "US": "United States", "CN": "China",
    "JP": "Japan",    "IN": "India",    "AU": "Australia",
}

# ── Unit conversions ──────────────────────────────────────────────────────
ARGON_KG_PER_LITER = 0.001784

# ── ReCiPe 2016 Midpoint normalization factors (World 2010 H, per person/yr) ──
RECIPE_MIDPOINT_NF = {
    "Fine particulate matter formation": 28.29,
    "Fossil resource scarcity": 158,
    "Freshwater ecotoxicity": 5.86,
    "Freshwater eutrophication": 0.343,
    "Global warming": 8100,
    "Human carcinogenic toxicity": 14.94,
    "Human non-carcinogenic toxicity": 257,
    "Ionizing radiation": 1220,
    "Land use": 7470,
    "Marine ecotoxicity": 8.17,
    "Marine eutrophication": 5.80,
    "Mineral resource scarcity": 34.7,
    "Ozone formation, Human health": 30.84,
    "Ozone formation, Terrestrial ecosystems": 31.41,
    "Stratospheric ozone depletion": 0.0536,
    "Terrestrial acidification": 36.91,
    "Terrestrial ecotoxicity": 10800,
    "Water consumption": 101,
}

# ── ReCiPe 2016 Endpoint normalization & weighting ────────────────────────
RECIPE_ENDPOINT_NF = {
    "Human Health": 2.22e-2,
    "Ecosystems":   5.30e-4,
    "Resources":    21.6,
}

RECIPE_ENDPOINT_WEIGHTS = {
    "Human Health": 400,
    "Ecosystems":   400,
    "Resources":    200,
}