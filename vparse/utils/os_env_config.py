import os

from vparse.utils.compat import get_env_with_legacy


def get_op_num_threads(env_name: str) -> int:
    env_value = os.getenv(env_name, None)
    return get_value_from_string(env_value, -1)


def get_load_images_timeout() -> int:
    env_value = get_env_with_legacy('VPARSE_PDF_RENDER_TIMEOUT', 'MINERU_PDF_RENDER_TIMEOUT', None)
    return get_value_from_string(env_value, 300)


def get_load_images_threads() -> int:
    env_value = get_env_with_legacy('VPARSE_PDF_RENDER_THREADS', 'MINERU_PDF_RENDER_THREADS', None)
    return get_value_from_string(env_value, 4)


def get_value_from_string(env_value: str, default_value: int) -> int:
    if env_value is not None:
        try:
            num_threads = int(env_value)
            if num_threads > 0:
                return num_threads
        except ValueError:
            return default_value
    return default_value


if __name__ == '__main__':
    print(get_value_from_string('1', -1))
    print(get_value_from_string('0', -1))
    print(get_value_from_string('-1', -1))
    print(get_value_from_string('abc', -1))
    print(get_load_images_timeout())
