import os
from huggingface_hub import snapshot_download as hf_snapshot_download
from modelscope import snapshot_download as ms_snapshot_download

from vparse.utils.config_reader import get_local_models_dir
from vparse.utils.enum_class import ModelPath

def auto_download_and_get_model_root_path(relative_path: str, repo_mode='pipeline') -> str:
    """
    Supports reliable download of files or directories.
    - If input is a file: returns the absolute local file path
    - If input is a directory: returns a relative path string with the same structure as relative_path in local cache
    :param repo_mode: Specify repository mode, 'pipeline' or 'vlm'
    :param relative_path: Relative path of file or directory
    :return: Absolute local path or relative path
    """
    model_source = os.getenv('VPARSE_MODEL_SOURCE', "huggingface")

    if model_source == 'local':
        local_models_config = get_local_models_dir()
        root_path = local_models_config.get(repo_mode, None)
        if not root_path:
            raise ValueError(f"Local path for repo_mode '{repo_mode}' is not configured.")
        return root_path

    # Establish mapping from repository mode to path
    repo_mapping = {
        'pipeline': {
            'huggingface': ModelPath.pipeline_root_hf,
            'modelscope': ModelPath.pipeline_root_modelscope,
            'default': ModelPath.pipeline_root_hf
        },
        'vlm': {
            'huggingface': ModelPath.vlm_root_hf,
            'modelscope': ModelPath.vlm_root_modelscope,
            'default': ModelPath.vlm_root_hf
        }
    }

    if repo_mode not in repo_mapping:
        raise ValueError(f"Unsupported repo_mode: {repo_mode}, must be 'pipeline' or 'vlm'")

    # Use default if model_source is not specified or not 'modelscope'
    repo = repo_mapping[repo_mode].get(model_source, repo_mapping[repo_mode]['default'])


    if model_source == "huggingface":
        snapshot_download = hf_snapshot_download
    elif model_source == "modelscope":
        snapshot_download = ms_snapshot_download
    else:
        raise ValueError(f"Unknown repository type: {model_source}")

    cache_dir = None

    if repo_mode == 'pipeline':
        relative_path = relative_path.strip('/')
        cache_dir = snapshot_download(repo, allow_patterns=[relative_path, relative_path+"/*"])
    elif repo_mode == 'vlm':
        # Handle different relative_path in VLM mode
        if relative_path == "/":
            cache_dir = snapshot_download(repo)
        else:
            relative_path = relative_path.strip('/')
            cache_dir = snapshot_download(repo, allow_patterns=[relative_path, relative_path+"/*"])

    if not cache_dir:
        raise FileNotFoundError(f"Failed to download model: {relative_path} from {repo}")
    return cache_dir


if __name__ == '__main__':
    path1 = "models/README.md"
    root = auto_download_and_get_model_root_path(path1)
    print("Absolute local file path:", os.path.join(root, path1))