"""Model artifacts and config (single config.json for feature names, threshold, bounds)."""
from pathlib import Path
import json

MODEL_DIR = Path(__file__).resolve().parent
CONFIG_PATH = MODEL_DIR / "config.json"
_cache = None


def _load_config() -> dict:
    global _cache
    if _cache is None and CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            _cache = json.load(f)
    return _cache or {}


def get_config() -> dict:
    return _load_config().copy()


def get_feature_names() -> list:
    return _load_config().get("feature_names", [])


def get_decision_threshold() -> float:
    return _load_config().get("decision_threshold", {}).get("threshold", 0.5)


def get_anomaly_feature_names() -> list:
    return _load_config().get("anomaly_feature_names", [])


def get_anomaly_score_bounds() -> tuple[float, float]:
    b = _load_config().get("anomaly_score_bounds", {})
    return (b.get("min", 0.0), b.get("max", 1.0))


def update_config(updates: dict) -> None:
    """Merge updates into config.json and write back."""
    config = _load_config()
    config.update(updates)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    global _cache
    _cache = config
