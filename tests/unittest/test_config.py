# Copyright (c) Opendatalab. All rights reserved.
from vparse import Config
from vparse.exceptions import ConfigurationError

def test_config_builder_fluent_api():
    """Test that the Config builder correctly handles fluent API calls."""
    config = Config().set_device("cpu").set_language("en").set_batch_size(16)
    final_config = config.build()
    
    assert final_config.device == "cpu"
    assert final_config.lang == "en"
    assert final_config.batch_size == 16

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
    test_config_validation_error()
    test_config_to_dict()
    print("test_config.py passed!")
