import os
import sys

from mineru.backend.vlm.utils import set_default_gpu_memory_utilization, enable_custom_logits_processors, \
    mod_kwargs_by_device_type
from mineru.utils.models_download_utils import auto_download_and_get_model_root_path

from vllm.entrypoints.cli.main import main as vllm_main


def main():
    """Start vLLM server configured for dots.ocr model inference.

    This function sets up vLLM with the correct configuration for dots.ocr,
    including chat-template-content-format=string which is required by dots.ocr.
    """
    args = sys.argv[1:]

    has_port_arg = False
    has_gpu_memory_utilization_arg = False
    has_logits_processors_arg = False
    has_chat_template_content_format_arg = False
    has_max_model_len_arg = False
    model_path = None
    model_arg_indices = []

    # Check existing arguments
    for i, arg in enumerate(args):
        if arg == "--port" or arg.startswith("--port="):
            has_port_arg = True
        if arg == "--gpu-memory-utilization" or arg.startswith("--gpu-memory-utilization="):
            has_gpu_memory_utilization_arg = True
        if arg == "--logits-processors" or arg.startswith("--logits-processors="):
            has_logits_processors_arg = True
        if arg == "--chat-template-content-format" or arg.startswith("--chat-template-content-format="):
            has_chat_template_content_format_arg = True
        if arg == "--max-model-len" or arg.startswith("--max-model-len="):
            has_max_model_len_arg = True
        if arg == "--model":
            if i + 1 < len(args):
                model_path = args[i + 1]
                model_arg_indices.extend([i, i + 1])
        elif arg.startswith("--model="):
            model_path = arg.split("=", 1)[1]
            model_arg_indices.append(i)

    # Remove --model argument from argument list
    if model_arg_indices:
        for index in sorted(model_arg_indices, reverse=True):
            args.pop(index)

    custom_logits_processors = enable_custom_logits_processors()

    # Add default parameters for dots.ocr
    if not has_port_arg:
        args.extend(["--port", "30000"])
    if not has_gpu_memory_utilization_arg:
        gpu_memory_utilization = str(set_default_gpu_memory_utilization())
        args.extend(["--gpu-memory-utilization", gpu_memory_utilization])
    if not has_chat_template_content_format_arg:
        # Required for dots.ocr which expects string content format in chat template
        args.extend(["--chat-template-content-format", "string"])
    if not has_max_model_len_arg:
        # dots.ocr supports long context for complex PDF layouts
        args.extend(["--max-model-len", "32768"])
    if not model_path:
        model_path = auto_download_and_get_model_root_path("/", "vlm")
    if (not has_logits_processors_arg) and custom_logits_processors:
        args.extend(["--logits-processors", "mineru_vl_utils:MinerULogitsProcessor"])

    args = mod_kwargs_by_device_type(args, vllm_mode="server")

    # Reconstruct arguments with model path as positional argument
    sys.argv = [sys.argv[0]] + ["serve", model_path] + args

    if os.getenv('OMP_NUM_THREADS') is None:
        os.environ["OMP_NUM_THREADS"] = "1"

    # Start vLLM server
    print(f"start vllm server for dots.ocr: {sys.argv}")
    vllm_main()


if __name__ == "__main__":
    main()
