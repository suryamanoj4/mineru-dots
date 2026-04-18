import json
import os
import sys
import click
import requests
from loguru import logger

from vparse.utils.compat import get_config_file_path, get_env_with_legacy
from vparse.utils.enum_class import ModelPath
from vparse.utils.models_download_utils import auto_download_and_get_model_root_path


PIPELINE_REQUIRED_MODEL_PATHS = [
    ModelPath.doclayout_yolo,
    ModelPath.yolo_v8_mfd,
    ModelPath.unimernet_small,
    ModelPath.pytorch_paddle,
    ModelPath.layout_reader,
    ModelPath.slanet_plus,
    ModelPath.unet_structure,
    ModelPath.paddle_table_cls,
    ModelPath.paddle_orientation_classification,
    ModelPath.pp_formulanet_plus_m,
]


def download_json(url):
    """Download JSON file"""
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def load_template_json(url):
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for template_name in ("vparse.template.json", "mineru.template.json"):
        local_template = os.path.join(repo_root, template_name)
        if os.path.exists(local_template):
            with open(local_template, "r", encoding="utf-8") as f:
                return json.load(f)
    return download_json(url)


def download_and_modify_json(url, local_filename, modifications):
    """Download JSON and modify content"""
    if os.path.exists(local_filename):
        with open(local_filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        config_version = data.get('config_version', '0.0.0')
        if config_version < '1.3.1':
            data = load_template_json(url)
    else:
        data = load_template_json(url)

    # Modify content
    for key, value in modifications.items():
        if key in data:
            if isinstance(data[key], dict):
                # If it's a dictionary, merge new values
                data[key].update(value)
            else:
                # Otherwise, replace directly
                data[key] = value

    # Save modified content
    with open(local_filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def has_pipeline_models(model_dir):
    if not model_dir or not os.path.isdir(model_dir):
        return False
    return all(
        os.path.exists(os.path.join(model_dir, relative_path))
        for relative_path in PIPELINE_REQUIRED_MODEL_PATHS
    )


def configure_model(model_dir, model_type):
    """配置模型"""
    json_url = 'https://gcore.jsdelivr.net/gh/opendatalab/VParse@master/vparse.template.json'
    config_file = get_config_file_path(prefer_existing=True)
    os.makedirs(os.path.dirname(config_file), exist_ok=True)

    json_mods = {
        'models-dir': {
            f'{model_type}': model_dir
        }
    }

    download_and_modify_json(json_url, config_file, json_mods)
    logger.info(f'The configuration file has been successfully configured, the path is: {config_file}')


def download_pipeline_models():
    """Download Pipeline models"""
    model_paths = [
        ModelPath.doclayout_yolo,
        ModelPath.yolo_v8_mfd,
        ModelPath.unimernet_small,
        ModelPath.pytorch_paddle,
        ModelPath.layout_reader,
        ModelPath.slanet_plus,
        ModelPath.unet_structure,
        ModelPath.paddle_table_cls,
        ModelPath.paddle_orientation_classification,
        ModelPath.pp_formulanet_plus_m,
    ]
    download_finish_path = ""
    for model_path in model_paths:
        logger.info(f"Downloading model: {model_path}")
        download_finish_path = auto_download_and_get_model_root_path(model_path, repo_mode='pipeline')
    logger.info(f"Pipeline models downloaded successfully to: {download_finish_path}")
    configure_model(download_finish_path, "pipeline")


def download_vlm_models():
    """Download VLM models"""
    download_finish_path = auto_download_and_get_model_root_path("/", repo_mode='vlm')
    logger.info(f"VLM models downloaded successfully to: {download_finish_path}")
    configure_model(download_finish_path, "vlm")


@click.command()
@click.option(
    '-s',
    '--source',
    'model_source',
    type=click.Choice(['huggingface', 'modelscope']),
    help="""
        The source of the model repository. 
        """,
    default=None,
)
@click.option(
    '-m',
    '--model_type',
    'model_type',
    type=click.Choice(['pipeline', 'vlm', 'all']),
    help="""
        The type of the model to download.
        """,
    default=None,
)
def download_models(model_source, model_type):
    """Download VParse model files.

    Supports downloading pipeline or VLM models from ModelScope or HuggingFace.
    """
    # Prompt for download source if not explicitly specified
    if model_source is None:
        model_source = click.prompt(
            "Please select the model download source: ",
            type=click.Choice(['huggingface', 'modelscope']),
            default='huggingface'
        )

    if os.getenv('VPARSE_MODEL_SOURCE', None) is None:
        os.environ['VPARSE_MODEL_SOURCE'] = get_env_with_legacy(
            'VPARSE_MODEL_SOURCE',
            'MINERU_MODEL_SOURCE',
            model_source,
        )

    # Prompt for model type if not explicitly specified
    if model_type is None:
        model_type = click.prompt(
            "Please select the model type to download: ",
            type=click.Choice(['pipeline', 'vlm', 'all']),
            default='all'
        )

    logger.info(f"Downloading {model_type} model from {os.getenv('VPARSE_MODEL_SOURCE', None)}...")

    try:
        if model_type == 'pipeline':
            download_pipeline_models()
        elif model_type == 'vlm':
            download_vlm_models()
        elif model_type == 'all':
            download_pipeline_models()
            download_vlm_models()
        else:
            click.echo(f"Unsupported model type: {model_type}", err=True)
            sys.exit(1)

    except Exception as e:
        logger.exception(f"An error occurred while downloading models: {str(e)}")
        sys.exit(1)

if __name__ == '__main__':
    download_models()
