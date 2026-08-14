"""CladBench v1 — open evaluation benchmark for AI on the UK and EU built environment.

Package entry-points:
- cladbench.cli        : ``python -m cladbench --help``
- cladbench.loaders    : JSONL loading + schema validation
- cladbench.scorers    : exact-match / LLM-judge / spearman scorers
- cladbench.adapters   : model adapters for HF Transformers + frontier APIs
"""

__version__ = "0.1.0"
