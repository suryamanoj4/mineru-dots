import os
import sys


CURRENT_ENV_PREFIX = "VPARSE_"
LEGACY_ENV_PREFIX = "MINERU_"

DEFAULT_CONFIG_FILE_NAME = ".vparse.json"
LEGACY_CONFIG_FILE_NAMES = (
    ".mineru.json",
    "vparse.json",
    "mineru.json",
)


def alias_legacy_env_vars() -> None:
    """Populate VPARSE_* env vars from legacy MINERU_* values when unset."""
    for env_key, env_value in list(os.environ.items()):
        if env_key.startswith(LEGACY_ENV_PREFIX):
            current_key = f"{CURRENT_ENV_PREFIX}{env_key[len(LEGACY_ENV_PREFIX):]}"
            os.environ.setdefault(current_key, env_value)


def get_legacy_env_key(current_key: str) -> str | None:
    if current_key.startswith(CURRENT_ENV_PREFIX):
        return f"{LEGACY_ENV_PREFIX}{current_key[len(CURRENT_ENV_PREFIX):]}"
    return None


def get_env_with_legacy(current_key: str, legacy_key: str | None = None, default=None):
    if legacy_key is None:
        legacy_key = get_legacy_env_key(current_key)

    value = os.getenv(current_key)
    if value is not None:
        return value

    if legacy_key is not None:
        return os.getenv(legacy_key, default)

    return default


def iter_default_config_paths(home_dir: str | None = None) -> list[str]:
    if home_dir is None:
        home_dir = os.path.expanduser("~")

    return [
        os.path.join(home_dir, DEFAULT_CONFIG_FILE_NAME),
        *[os.path.join(home_dir, file_name) for file_name in LEGACY_CONFIG_FILE_NAMES],
    ]


def get_config_file_path(
    config_file_name: str | None = None,
    *,
    home_dir: str | None = None,
    prefer_existing: bool = True,
) -> str:
    if home_dir is None:
        home_dir = os.path.expanduser("~")

    explicit_name = config_file_name
    if explicit_name is None:
        explicit_name = get_env_with_legacy("VPARSE_TOOLS_CONFIG_JSON", "MINERU_TOOLS_CONFIG_JSON")

    if explicit_name is not None:
        if os.path.isabs(explicit_name):
            return explicit_name
        return os.path.join(home_dir, explicit_name)

    default_path = os.path.join(home_dir, DEFAULT_CONFIG_FILE_NAME)
    if not prefer_existing:
        return default_path

    for candidate in iter_default_config_paths(home_dir):
        if os.path.exists(candidate):
            return candidate

    return default_path


alias_legacy_env_vars()

_module = sys.modules[__name__]
sys.modules.setdefault("vparse.utils.compat", _module)
sys.modules.setdefault("mineru.utils.compat", _module)
