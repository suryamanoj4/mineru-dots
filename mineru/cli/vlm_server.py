import click
import sys
try:
    import torch
except ImportError:
    torch = None

from loguru import logger
from mineru.utils.vparse_config import config


def _has_cli_arg(args: list[str], flag: str) -> bool:
    return any(arg == flag or arg.startswith(f"{flag}=") for arg in args)


def _append_arg_if_missing(args: list[str], flag: str, value: str) -> None:
    if not _has_cli_arg(args, flag):
        args.extend([flag, value])


def _append_flag_if_missing(args: list[str], flag: str) -> None:
    if not _has_cli_arg(args, flag):
        args.append(flag)


def _auto_max_model_len_from_vram() -> int:
    if torch is None or not torch.cuda.is_available():
        return 4096

    total_memory = torch.cuda.get_device_properties(0).total_memory
    total_memory_gb = total_memory / (1024 ** 3)

    if total_memory_gb <= 16.5:
        return 4096
    if total_memory_gb <= 24.5:
        return 16384
    if total_memory_gb <= 48.5:
        return 32768
    return 131072


def _build_vllm_args(base_args: list[str]) -> list[str]:
    args = list(base_args)

    _append_flag_if_missing(args, "--trust-remote-code")

    _append_arg_if_missing(args, "--port", str(config.engine.port))

    if not _has_cli_arg(args, "--max-model-len"):
        if config.engine.max_model_len == "auto":
            tuned_len = _auto_max_model_len_from_vram()
            args.extend(["--max-model-len", str(tuned_len)])
        else:
            args.extend(["--max-model-len", str(config.engine.max_model_len)])

    return args


def vllm_server():
    from mineru.model.vlm.vllm_server import main
    main()


def lmdeploy_server():
    from mineru.model.vlm.lmdeploy_server import main
    main()


@click.command(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.option(
    '-e',
    '--engine',
    'inference_engine',
    type=click.Choice(['auto', 'vllm', 'lmdeploy']),
    default='auto',
    help='Select the inference engine used to accelerate VLM inference, default is "auto".',
)
@click.pass_context
def openai_server(ctx, inference_engine):
    base_args = list(ctx.args)
    if inference_engine == 'auto':
        try:
            import vllm
            inference_engine = 'vllm'
            logger.info("Using vLLM as the inference engine for VLM server.")
        except ImportError:
            logger.info("vLLM not found, attempting to use LMDeploy as the inference engine for VLM server.")
            try:
                import lmdeploy
                inference_engine = 'lmdeploy'
            # Success message moved after successful import
                logger.info("Using LMDeploy as the inference engine for VLM server.")
            except ImportError:
                logger.error("Neither vLLM nor LMDeploy is installed. Please install at least one of them.")
                sys.exit(1)

    if inference_engine == 'vllm':
        try:
            import vllm
        except ImportError:
            logger.error("vLLM is not installed. Please install vLLM or choose LMDeploy as the inference engine.")
            sys.exit(1)

        sys.argv = [sys.argv[0]] + _build_vllm_args(base_args)
        vllm_server()
    elif inference_engine == 'lmdeploy':
        try:
            import lmdeploy
        except ImportError:
            logger.error("LMDeploy is not installed. Please install LMDeploy or choose vLLM as the inference engine.")
            sys.exit(1)

        sys.argv = [sys.argv[0]] + base_args
        lmdeploy_server()

if __name__ == "__main__":
    openai_server()