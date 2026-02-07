"""Load prompts from a single prompts.json."""
from pathlib import Path
import json

_PROMPTS_PATH = Path(__file__).resolve().parent / "prompts.json"
_cache = None


def get_prompt(name: str) -> str:
    """Return prompt text for key (e.g. alert_explanation_system, report_writer_system)."""
    global _cache
    if _cache is None:
        with open(_PROMPTS_PATH) as f:
            _cache = json.load(f)
    return _cache.get(name, "")
