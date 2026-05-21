"""Multi-model registry — config holds multiple model paths and an active key."""
from pathlib import Path


def list_models(config: dict) -> list[str]:
    return sorted(config.get("models", {}).keys())


def resolve_active_model(config: dict) -> Path:
    active = config.get("active_model")
    models = config.get("models", {})
    if active not in models:
        raise ValueError(
            f"active_model {active!r} not found in models {list(models)}"
        )
    return Path(models[active])


def switch_model(config: dict, name: str) -> dict:
    if name not in config.get("models", {}):
        raise ValueError(
            f"unknown model {name!r}; known: {list(config.get('models', {}))}"
        )
    new = dict(config)
    new["active_model"] = name
    return new
