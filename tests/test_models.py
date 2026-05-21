"""Multi-model registry: pick/switch the active whisper model."""
from pathlib import Path

import pytest

from voice_app.models import list_models, resolve_active_model, switch_model


def _config(active="large", models=None):
    return {
        "active_model": active,
        "models": models or {
            "large": "C:/x/ggml-large-v3-turbo-q5_0.bin",
            "medium": "C:/x/ggml-medium-q5_0.bin",
        },
    }


def test_list_models_returns_names_sorted():
    cfg = _config(models={"medium": "a", "large": "b", "small": "c"})
    assert list_models(cfg) == ["large", "medium", "small"]


def test_list_models_on_empty_returns_empty():
    assert list_models({}) == []


def test_resolve_active_model_returns_path():
    cfg = _config(active="medium")
    assert resolve_active_model(cfg) == Path("C:/x/ggml-medium-q5_0.bin")


def test_resolve_active_model_raises_when_active_missing():
    cfg = _config(active="bogus")
    with pytest.raises(ValueError, match="bogus"):
        resolve_active_model(cfg)


def test_resolve_active_model_raises_when_active_key_missing():
    cfg = {"models": {"large": "p"}}
    with pytest.raises(ValueError):
        resolve_active_model(cfg)


def test_switch_model_returns_new_config_with_updated_active():
    cfg = _config(active="large")
    new = switch_model(cfg, "medium")
    assert new["active_model"] == "medium"
    # Original is unchanged
    assert cfg["active_model"] == "large"


def test_switch_model_preserves_other_keys():
    cfg = _config()
    cfg["language"] = "ru"
    cfg["hotkey"] = "alt+z"
    new = switch_model(cfg, "medium")
    assert new["language"] == "ru"
    assert new["hotkey"] == "alt+z"
    assert new["models"] == cfg["models"]


def test_switch_model_raises_on_unknown_name():
    cfg = _config()
    with pytest.raises(ValueError, match="bogus"):
        switch_model(cfg, "bogus")


def test_switch_to_currently_active_is_safe_noop():
    cfg = _config(active="large")
    new = switch_model(cfg, "large")
    assert new["active_model"] == "large"
