# dots.ocr Integration Documentation

## Overview

VParse integrates **dots.ocr** (`rednote-hilab/dots.mocr`) as the default VLM model for high-accuracy document parsing. This is a 3B parameter multilingual document parsing VLM developed by the rednote-hilab team.

## Supported Capabilities

- **Layout Detection**: Title, Text, Table, Image, Formula, List, Header, Footer, Footnote, Code blocks
- **OCR**: 109+ languages including Chinese, English, Japanese, Korean, Arabic, Cyrillic, etc.
- **Formula Detection**: Inline and interline formulas

## Backends

### vlm-auto-engine (Default)

The `vlm-auto-engine` backend uses dots.ocr for:
- Full layout detection
- Text extraction (OCR)
- Table detection
- Formula detection

This provides end-to-end document parsing with high accuracy.

**Prompt Mode**: `prompt_layout_all_en`

### hybrid-auto-engine

The `hybrid-auto-engine` backend uses dots.ocr for:
- Layout detection only

The pipeline backend handles:
- OCR (using PaddleOCR)
- Formula recognition (using UniMERNet)
- Table structure recognition (using RapidTable)

This provides flexibility with language-specific OCR support.

**Prompt Mode**: `prompt_layout_only_en`

## Hardware Requirements

| Backend | Min VRAM | Recommended VRAM |
|---------|----------|------------------|
| vlm-auto-engine | 8GB | 16GB+ |
| hybrid-auto-engine | 10GB | 16GB+ |

## Inference Engines

Both backends support auto-engine selection. The available inference engines are:

- **vLLM** (default): High throughput, recommended for production
- **Transformers**: HuggingFace transformers, for debugging
- **HTTP Client**: Connect to external OpenAI-compatible servers

## Usage Examples

### Basic Usage (vlm-auto-engine)

```bash
vparse -p <input_path> -o <output_path>
```

### Using hybrid-auto-engine

```bash
vparse -p <input_path> -o <output_path> -b hybrid-auto-engine
```

### Using with custom server

```bash
# Start vLLM server
vparse-openai-server --port 30000

# Connect via HTTP client
vparse -p <input_path> -o <output_path> -b vlm-http-client -u http://localhost:30000
```

## Environment Variables

- `VPARSE_MODEL_SOURCE`: Model source (huggingface/modelscope/local)
- `VPARSE_VL_MODEL_NAME`: Model name for remote servers
- `VPARSE_VL_API_KEY`: API key for remote servers

## Troubleshooting

### Out of Memory

If you encounter OOM errors:
1. Try using `hybrid-auto-engine` backend instead of `vlm-auto-engine`
2. Reduce batch size with `VPARSE_HYBRID_BATCH_RATIO=1`
3. Use HTTP client mode with a server that has more VRAM

### Model Download Issues

If model download fails:
1. Try switching model source: `export VPARSE_MODEL_SOURCE=modelscope`
2. Download manually from HuggingFace or ModelScope and use local mode

## Model Information

- **Model**: `rednote-hilab/dots.mocr`
- **Parameters**: ~3B
- **Framework**: Qwen2.5-VL
- **License**: Please check HuggingFace model card for license information
