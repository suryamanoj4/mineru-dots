# Copyright (c) Opendatalab. All rights reserved.
import json
import os
import sys
import tempfile
import types
from pathlib import Path
from unittest import mock


def install_import_stubs() -> None:
    if "loguru" not in sys.modules:
        loguru = types.ModuleType("loguru")
        loguru.logger = types.SimpleNamespace(
            debug=lambda *a, **k: None,
            info=lambda *a, **k: None,
            warning=lambda *a, **k: None,
            error=lambda *a, **k: None,
            exception=lambda *a, **k: None,
        )
        sys.modules["loguru"] = loguru


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))
install_import_stubs()

from vparse.config import Config
from vparse.exceptions import ConfigurationError

def test_config_builder_fluent_api():
    """Test that the Config builder correctly handles fluent API calls."""
    config = Config().set_device("cpu").set_language("en").set_batch_size(16)
    final_config = config.build()
    
    assert final_config.device == "cpu"
    assert final_config.lang == "en"
    assert final_config.batch_size == 16

def test_config_load_from_file_supports_phase_three_fields():
    """Test that load_from_file applies core config fields, not only legacy extras."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "vparse.json"
        config_path.write_text(
            json.dumps(
                {
                    "backend": "vlm-auto-engine",
                    "lang": "japan",
                    "batch_size": 16,
                    "models-dir": "/models",
                }
            ),
            encoding="utf-8",
        )

        final_config = Config().load_from_file(str(config_path)).build()

    assert final_config.backend == "vlm-auto-engine"
    assert final_config.lang == "japan"
    assert final_config.batch_size == 16
    assert final_config.models_dir == "/models"

def test_config_hierarchy_file_env_programmatic():
    """Test defaults < file < env < programmatic precedence."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_path = Path(temp_dir) / "vparse.json"
        config_path.write_text(
            json.dumps(
                {
                    "backend": "pipeline",
                    "lang": "en",
                    "batch_size": 8,
                }
            ),
            encoding="utf-8",
        )

        with mock.patch.dict(
            os.environ,
            {
                "VPARSE_BACKEND": "vlm-auto-engine",
                "VPARSE_BATCH_SIZE": "12",
            },
            clear=False,
        ):
            final_config = (
                Config()
                .load_from_file(str(config_path))
                .load_from_env()
                .set_backend("hybrid-auto-engine")
                .set_batch_size(24)
                .build()
            )

    assert final_config.backend == "hybrid-auto-engine"
    assert final_config.lang == "en"
    assert final_config.batch_size == 24

def test_config_validation_error():
    """Test that the Config builder raises ConfigurationError for invalid types."""
    try:
        Config().set_batch_size("heavy").build()
        assert False, "Should have raised ConfigurationError"
    except ConfigurationError:
        pass

def test_config_to_dict():
    """Test that Config can be converted to a dictionary for internal engine use."""
    config_dict = Config().set_backend("vlm-auto-engine").to_dict()
    assert config_dict["backend"] == "vlm-auto-engine"
    assert "device" in config_dict

if __name__ == "__main__":
    test_config_builder_fluent_api()
    test_config_load_from_file_supports_phase_three_fields()
    test_config_hierarchy_file_env_programmatic()
    test_config_validation_error()
    test_config_to_dict()
    print("test_config.py passed!")
