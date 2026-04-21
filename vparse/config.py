# Copyright (c) Opendatalab. All rights reserved.
import json
import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict
from vparse.utils.compat import get_config_file_path, get_env_with_legacy
from vparse.utils.config_reader import get_device
from vparse.utils.enum_class import MakeMode
from vparse.exceptions import ConfigurationError


class VParseConfigModel(BaseModel):
    """Internal Pydantic model for VParse configuration validation."""
    model_config = ConfigDict(protected_namespaces=())

    backend: str = Field(default="pipeline", description="OCR backend to use")
    lang: str = Field(default="en", description="Default language for OCR")
    device: str = Field(default_factory=get_device, description="Device to use (cpu, cuda, etc.)")
    output_format: str = Field(default=MakeMode.MM_MD, description="Default output format")
    formula_enable: bool = Field(default=True, description="Enable formula recognition")
    table_enable: bool = Field(default=True, description="Enable table recognition")
    models_dir: Optional[str] = Field(default=None, description="Directory containing model weights")
    batch_size: int = Field(default=8, description="Batch size for processing")
    
    # Advanced configs from JSON
    bucket_info: Dict[str, Any] = Field(default_factory=dict, description="S3 bucket information")
    latex_delimiters: Dict[str, Any] = Field(
        default_factory=lambda: {
            'display': {'left': '$$', 'right': '$$'},
            'inline': {'left': '$', 'right': '$'}
        },
        description="LaTeX delimiters for formulas"
    )
    llm_aided_config: Dict[str, Any] = Field(default_factory=dict, description="Configuration for LLM-aided processing")


class Config:
    """
    Fluent configuration builder for VParse.
    
    Hierarchy (later overrides earlier):
    1. Defaults
    2. File (~/.vparse.json or ~/.mineru.json)
    3. Environment variables (VPARSE_* or MINERU_*)
    4. Programmatic .set_*() calls
    """

    def __init__(self):
        # Start with defaults
        self._model = VParseConfigModel()
        self._programmatic_overrides: Dict[str, Any] = {}

    def set_backend(self, backend: str) -> "Config":
        """Set the OCR backend (e.g., 'pipeline', 'vlm-auto-engine')."""
        self._programmatic_overrides["backend"] = backend
        return self

    def set_device(self, device: str) -> "Config":
        """Set the compute device (e.g., 'cpu', 'cuda', 'mps')."""
        self._programmatic_overrides["device"] = device
        return self

    def set_language(self, lang: str) -> "Config":
        """Set the primary language for OCR."""
        self._programmatic_overrides["lang"] = lang
        return self

    def set_output_format(self, fmt: str) -> "Config":
        """Set the output format (e.g., 'mm_markdown', 'nlp_markdown')."""
        self._programmatic_overrides["output_format"] = fmt
        return self

    def enable_formula(self, enable: bool = True) -> "Config":
        """Enable or disable formula recognition."""
        self._programmatic_overrides["formula_enable"] = enable
        return self

    def disable_formula(self) -> "Config":
        """Disable formula recognition."""
        return self.enable_formula(False)

    def enable_tables(self, enable: bool = True) -> "Config":
        """Enable or disable table recognition."""
        self._programmatic_overrides["table_enable"] = enable
        return self

    def disable_tables(self) -> "Config":
        """Disable table recognition."""
        return self.enable_tables(False)

    def set_batch_size(self, size: int) -> "Config":
        """Set the batch size for processing."""
        self._programmatic_overrides["batch_size"] = size
        return self

    def set_models_dir(self, path: str) -> "Config":
        """Set the directory where models are stored."""
        self._programmatic_overrides["models_dir"] = path
        return self

    def load_from_file(self, path: Optional[str] = None) -> "Config":
        """
        Load configuration from a JSON file.
        Priority level 2 in the hierarchy.
        """
        config_path = path or get_config_file_path(prefer_existing=True)
        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # Map JSON keys to model fields
                file_config = {}
                if "models-dir" in data:
                    file_config["models_dir"] = data["models-dir"]
                if "bucket_info" in data:
                    file_config["bucket_info"] = data["bucket_info"]
                if "latex-delimiter-config" in data:
                    file_config["latex_delimiters"] = data["latex-delimiter-config"]
                if "llm-aided-config" in data:
                    file_config["llm_aided_config"] = data["llm-aided-config"]
                
                # Update the base model with file values
                for k, v in file_config.items():
                    setattr(self._model, k, v)
            except Exception as e:
                raise ConfigurationError(f"Failed to load config from {config_path}: {e}")
        return self

    def load_from_env(self) -> "Config":
        """
        Load configuration from environment variables.
        Priority level 3 in the hierarchy.
        """
        env_mappings = {
            "backend": ("VPARSE_BACKEND", "MINERU_BACKEND"),
            "device": ("VPARSE_DEVICE_MODE", "MINERU_DEVICE_MODE"),
            "lang": ("VPARSE_LANG", "MINERU_LANG"),
            "formula_enable": ("VPARSE_FORMULA_ENABLE", "MINERU_FORMULA_ENABLE"),
            "table_enable": ("VPARSE_TABLE_ENABLE", "MINERU_TABLE_ENABLE"),
            "models_dir": ("VPARSE_MODELS_DIR", "MINERU_MODELS_DIR"),
            "batch_size": ("VPARSE_BATCH_SIZE", "MINERU_BATCH_SIZE"),
        }
        
        for field, (curr, legacy) in env_mappings.items():
            val = get_env_with_legacy(curr, legacy)
            if val is not None:
                # Type conversion for bools and ints
                if field in ("formula_enable", "table_enable"):
                    val = val.lower() == "true"
                elif field == "batch_size":
                    try:
                        val = int(val)
                    except ValueError:
                        continue
                setattr(self._model, field, val)
        return self

    def build(self) -> VParseConfigModel:
        """
        Finalize and validate the configuration.
        Returns the validated Pydantic model.
        """
        # Start with the model (Defaults + File + Env)
        data = self._model.model_dump()
        # Overlay programmatic overrides (Level 4)
        data.update(self._programmatic_overrides)
        
        try:
            return VParseConfigModel(**data)
        except Exception as e:
            # Pydantic validation errors caught here
            raise ConfigurationError(f"Invalid configuration: {e}")

    def to_dict(self) -> dict:
        """Return the finalized configuration as a dictionary."""
        return self.build().model_dump()
