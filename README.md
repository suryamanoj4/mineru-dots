<div align="center" xmlns="http://www.w3.org/1999/html">
<!-- logo -->
<p align="center">
  <img src="https://gcore.jsdelivr.net/gh/opendatalab/VParse@master/docs/images/VParse-logo.png" width="300px" style="vertical-align:middle;">
</p>

<!-- status badge -->

[![Status](https://img.shields.io/badge/status-active--development-orange)](ROADMAP.md)
[![Version](https://img.shields.io/badge/version-2.7.6--vparse--dev-blue)](vparse/version.py)
[![Python](https://img.shields.io/badge/python-3.10--3.13-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE.md)
[![Roadmap](https://img.shields.io/badge/📋-view%20roadmap-purple)](ROADMAP.md)

<!-- language -->

[English](README.md) | [简体中文](README_zh-CN.md)

<!-- disclaimer banner -->

<p align="center">
⚠️ <strong>ACTIVE REBRANDING NOTICE:</strong> This project has completed the internal rebranding from <strong>MinerU</strong> to <strong>VParse</strong>. Core functionality remains stable, and legacy commands/imports remain available through compatibility aliases.
</p>

<!-- join us -->

<p align="center">
    👋 join us on <a href="https://discord.gg/Tdedn9GTXq" target="_blank">Discord</a> and <a href="https://vparse.net/community-portal/?aliasId=3c430f94" target="_blank">WeChat</a>
</p>

</div>

---

## ⚠️ Rebranding Status

> **This project has been rebranded from MinerU → VParse**
>
> - ✅ **Core OCR functionality**: Stable and production-ready
> - ✅ **Rebranding completed**: Package name, CLI commands, and documentation now use VParse branding
> - ✅ **Backward compatibility retained**: Legacy `mineru*` commands/imports remain available as aliases
> - 📋 **Roadmap**: Comprehensive development plan available at [ROADMAP.md](ROADMAP.md)
>
> **What this means for users**:
> - Current functionality works as documented
> - Use `vparse` as the primary package name
> - Use `vparse` CLI commands as primary commands
> - Legacy `mineru` imports and CLI commands continue to work during migration
>
> **See [ROADMAP.md](ROADMAP.md) for complete development plan and contribution guide.**

---

# VParse (formerly MinerU)

> **VParse is built on top of [VParse](https://github.com/opendatalab/VParse) by customizing and extending the original tool to meet specific OCR and document parsing needs.** We extend VParse's powerful document understanding capabilities with additional backend support, Docker deployment, multi-model VLM integration, and production-grade optimizations.

## Project Introduction

**VParse** (previously known as MinerU) is a comprehensive document parsing and OCR toolkit that converts PDFs and images into machine-readable formats (e.g., markdown, JSON, HTML, DOCX). It supports multiple OCR backends, VLM models, and deployment methods.

VParse originated from [VParse](https://github.com/opendatalab/VParse), which was born during the pre-training process of [InternLM](https://github.com/InternLM/InternLM). We are extending it into a one-stop OCR toolkit with enhanced backend support, Docker deployment capabilities, and optimized performance for bulk processing.

If you encounter any issues or if the results are not as expected, please submit an issue on [GitHub Issues](https://github.com/opendatalab/VParse/issues) and **attach the relevant PDF**.

https://github.com/user-attachments/assets/4bea02c9-6d54-4cd6-97ed-dff14340982c

---

## Current Project Status

### ✅ What Works Now (Stable)

| Feature | Status | Description |
|---------|--------|-------------|
| **Pipeline Backend** | ✅ Stable | Traditional OCR pipeline with layout detection, formula recognition, table extraction |
| **VLM Backend** | ✅ Stable | Vision Language Model backend using `rednote-hilab/dots.mocr` (3B params) |
| **Hybrid Backend** | ✅ Stable | Combines VLM layout detection with pipeline OCR for accuracy |
| **dots.ocr Integration** | ✅ Stable | Default VLM model, supports 109+ languages |
| **Multi-language OCR** | ✅ Stable | 109 languages via pipeline backend |
| **Formula Recognition** | ✅ Stable | LaTeX conversion via Unimernet |
| **Table Recognition** | ✅ Stable | HTML conversion via SlanetPlus/UnetTableModel |
| **CPU Support** | ✅ Stable | Pure CPU inference with pipeline backend |
| **GPU Acceleration** | ✅ Stable | CUDA, NPU (CANN), MPS (Apple Silicon) support |
| **CLI Interface** | ✅ Stable | `vparse` command-line tool |
| **FastAPI Server** | ✅ Stable | `vparse-api` with `/file_parse` endpoint |
| **Gradio Web UI** | ✅ Stable | `vparse-gradio` for browser-based usage |
| **Docker Support** | ✅ Stable | Docker Compose with vLLM, API, Gradio services |
| **Output Formats** | ✅ Stable | Markdown, JSON (middle, model, content_list), images |
| **Domestic Hardware** | ✅ Stable | Ascend, Hygon, Enflame, MooreThreads, IluvatarCorex, Cambricon, METAX, Kunlunxin, Tecorigin, Biren |

### 📋 Planned Enhancements

| Feature | Status | Expected Completion |
|---------|--------|---------------------|
| **Tesseract Integration** | ✅ Done | Lightweight `lite` backend for fast OCR |
| **Multi-Model VLM Support** | 📋 Planned | Qwen2-VL, InternVL2, Got-OCR2.0, Nougat |
| **KV Cache Optimization** | 📋 Planned | Memory optimization for bulk VLM processing |
| **Bulk Processing API** | 📋 Planned | Job queue, progress tracking, checkpoint/resume |
| **Enhanced Docker** | 📋 Planned | Multi-stage builds, Kubernetes manifests, Helm charts |
| **Python Library API** | 📋 Planned | `from vparse import OCR` unified interface |
| **Additional Output Formats** | 📋 Planned | DOCX, searchable PDF, HTML, LaTeX, EPUB |

### 📋 See Complete Roadmap

For detailed development plan with 15 modules and 148 tasks, see **[ROADMAP.md](ROADMAP.md)**.

---

## Supported Modes & Backends

### Backend Comparison

VParse currently supports **three main backends** with different trade-offs:

<table>
  <thead>
    <tr>
      <th rowspan="2">Backend</th>
      <th rowspan="2">Pipeline</th>
      <th colspan="2">Auto-Engine (Local GPU)</th>
      <th colspan="2">HTTP Client (Remote/OpenAI-Compatible)</th>
    </tr>
    <tr>
      <th>Hybrid</th>
      <th>VLM</th>
      <th>Hybrid</th>
      <th>VLM</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>Best For</th>
      <td>CPU-only, general docs</td>
      <td colspan="2">High accuracy, GPU available</td>
      <td colspan="2">Remote inference, low local resources</td>
    </tr>
    <tr>
      <th>Accuracy¹</th>
      <td style="text-align:center;">82+</td>
      <td colspan="4" style="text-align:center;">90+</td>
    </tr>
    <tr>
      <th>CPU Support</th>
      <td style="text-align:center;">✅ Yes</td>
      <td colspan="2" style="text-align:center;">❌ No</td>
      <td colspan="2" style="text-align:center;">✅ Yes</td>
    </tr>
    <tr>
      <th>Min VRAM</th>
      <td style="text-align:center;">6GB</td>
      <td style="text-align:center;">10GB</td>
      <td style="text-align:center;">8GB</td>
      <td style="text-align:center;">3GB (server-side)</td>
      <td style="text-align:center;">3GB (server-side)</td>
    </tr>
    <tr>
      <th>Multi-language</th>
      <td style="text-align:center;">109 languages</td>
      <td style="text-align:center;">Chinese + English</td>
      <td style="text-align:center;">Chinese + English</td>
      <td style="text-align:center;">109 languages</td>
      <td style="text-align:center;">Chinese + English</td>
    </tr>
    <tr>
      <th>Inference Engines</th>
      <td colspan="5" style="text-align:center;">transformers, vLLM, LMDeploy, MLX (macOS), OpenAI-compatible HTTP</td>
    </tr>
    <tr>
      <th>VLM Models</th>
      <td>N/A</td>
      <td colspan="4" style="text-align:center;">dots.mocr (default)</td>
    </tr>
  </tbody>
</table>

<sup>¹</sup> Accuracy metrics are End-to-End Evaluation Overall scores from OmniDocBench (v1.5), based on latest version.

### Backend Selection Guide

| Scenario | Recommended Backend | Command |
|----------|---------------------|---------|
| **CPU-only device** | `pipeline` | `vparse -p input.pdf -b pipeline` |
| **GPU available, fast processing** | `pipeline` | `vparse -p input.pdf -b pipeline` |
| **GPU available, highest accuracy** | `vlm-auto-engine` | `vparse -p input.pdf -b vlm-auto-engine` |
| **GPU available, balanced accuracy** | `hybrid-auto-engine` | `vparse -p input.pdf -b hybrid-auto-engine` |
| **Remote VLM server** | `vlm-http-client` | `vparse -p input.pdf -b vlm-http-client -u http://server:30000` |
| **Remote VLM + local OCR** | `hybrid-http-client` | `vparse -p input.pdf -b hybrid-http-client -u http://server:30000` |

### Supported VLM Models

| Model | Status | Description |
|-------|--------|-------------|
| **dots.mocr** (rednote-hilab/dots.mocr) | ✅ Default | 3B params, 109+ languages, multilingual document parsing |
| Qwen2-VL | 📋 Planned | Strong multilingual support, 2B/7B/72B variants |
| InternVL2/2.5 | 📋 Planned | Excellent table and formula understanding |
| Got-OCR2.0 | 📋 Planned | Specialized for OCR tasks |
| Nougat | 📋 Planned | Scientific papers, LaTeX output |

### Supported Inference Engines

| Engine | Status | Description |
|--------|--------|-------------|
| **transformers** | ✅ Supported | HuggingFace transformers, universal compatibility |
| **vLLM** | ✅ Supported | High-throughput serving, continuous batching |
| **LMDeploy** | ✅ Supported | TurboMind engine, efficient deployment |
| **MLX** | ✅ Supported | Apple Silicon optimization (macOS only) |
| **Ollama** | 📋 Planned | Easy local model serving |
| **TGI** | 📋 Planned | HuggingFace Text Generation Inference |
| **OpenAI-compatible HTTP** | ✅ Supported | Remote inference via API |

### Supported Output Formats

| Format | Status | Description |
|--------|--------|-------------|
| **Markdown (MM_MD)** | ✅ Supported | Multimodal markdown with images |
| **Markdown (NLP_MD)** | ✅ Supported | NLP-focused markdown |
| **JSON (middle)** | ✅ Supported | Intermediate structured format |
| **JSON (model)** | ✅ Supported | Raw model output |
| **JSON (content_list)** | ✅ Supported | Simplified content list |
| **Images** | ✅ Supported | Extracted images |
| DOCX | 📋 Planned | Microsoft Word export |
| HTML | 📋 Planned | Semantic HTML with accessibility |
| Searchable PDF | 📋 Planned | OCR layer over original PDF |
| LaTeX | 📋 Planned | Academic paper format |
| CSV/TSV | 📋 Planned | Tabular data extraction |
| EPUB | 📋 Planned | E-book format |

---

## Key Features

- **Multiple Backend Support**: Pipeline (traditional OCR), VLM (vision language models), and Hybrid (combined approach)
- **dots.ocr VLM Integration**: Uses `rednote-hilab/dots.mocr` (3B params) for multilingual document parsing. Supports 109+ languages.
- **Intelligent Layout Analysis**: Remove headers, footers, footnotes, page numbers, etc., to ensure semantic coherence.
- **Reading Order Preservation**: Output text in human-readable order, suitable for single-column, multi-column, and complex layouts.
- **Structure Preservation**: Preserve the structure of the original document, including headings, paragraphs, lists, etc.
- **Multimedia Extraction**: Extract images, image descriptions, tables, table titles, and footnotes.
- **Formula Recognition**: Automatically recognize and convert formulas in the document to LaTeX format.
- **Table Recognition**: Automatically recognize and convert tables in the document to HTML format.
- **Auto OCR Detection**: Automatically detect scanned PDFs and garbled PDFs and enable OCR functionality.
- **109-Language OCR**: OCR supports detection and recognition of 109 languages.
- **Multiple Output Formats**: Supports multimodal and NLP Markdown, JSON sorted by reading order, and rich intermediate formats.
- **Visualization**: Supports various visualization results, including layout visualization and span visualization.
- **Cross-Platform**: Supports running in pure CPU environment, and also supports GPU(CUDA)/NPU(CANN)/MPS acceleration. Compatible with Windows, Linux, and Mac platforms.
- **Extensive Hardware Support**: Supports domestic computing platforms (Ascend, Hygon, Enflame, MooreThreads, IluvatarCorex, Cambricon, METAX, Kunlunxin, Tecorigin, Biren)

---

### Installation

#### 1. Full Installation (All Features)
```bash
pip install "vparse[all]"
```

#### 2. CPU/Lite Installation (Fast & Lightweight)
If you only need the high-performance `lite` backend (Tesseract-based) and want to avoid heavy dependencies like PyTorch and PaddleOCR:
```bash
pip install "vparse[lite]"
```

> ⚠️ **IMPORTANT: System Requirement**  
> The `lite` backend requires the Tesseract-OCR engine to be installed on your system:  
> - **Ubuntu/Linux**: `sudo apt install tesseract-ocr`  
> - **macOS**: `brew install tesseract`  
> - **Windows**: [Download Tesseract Binary](https://github.com/UB-Mannheim/tesseract/wiki)

### Quick Start


> ⚠️ **Note**: `vparse` is the primary CLI prefix. Legacy `mineru*` commands remain available as backward-compatible aliases.

If you encounter any installation issues, please first consult the <a href="#faq">FAQ</a>. </br>
If the parsing results are not as expected, refer to the <a href="#known-issues">Known Issues</a>. </br>
For detailed development roadmap, see <a href="ROADMAP.md">ROADMAP.md</a>.

### Local Deployment

#### Install Using pip or uv

```bash
pip install --upgrade pip
pip install uv
uv pip install -U "vparse[all]"
```

#### Install From Source

```bash
git clone https://github.com/opendatalab/VParse.git
cd VParse
uv pip install -e .[all]
```

> [!TIP]
> `vparse[all]` includes all core features, compatible with Windows / Linux / macOS systems.
> For VLM inference engine selection or lightweight installation, see [Extension Modules Installation Guide](https://opendatalab.github.io/VParse/quick_start/extension_modules/).

#### Deploy Using Docker

VParse provides Docker deployment with Docker Compose:

```bash
cd docker
# CPU deployment: FastAPI backend on :8000 and Gradio frontend on :7860
docker compose --profile cpu up -d

# GPU deployment: FastAPI backend on :8000 and Gradio frontend on :7860
docker compose --profile gpu up -d

# Hybrid deployment: FastAPI backend on :8000 and Gradio frontend on :7860
docker compose --profile hybrid up -d
```

On the first `docker compose up`, the API container downloads only the models needed for that profile into persistent Docker volumes. The image stays lean, and later restarts reuse the mounted cache.

See [Docker Deployment Documentation](https://opendatalab.github.io/VParse/quick_start/docker_deployment/) for detailed instructions.

---

### Using VParse

#### CLI Usage

For GPU-accelerated parsing (recommended):
```bash
vparse -p <input_path> -o <output_path>
```

For CPU-only environment:
```bash
vparse -p <input_path> -o <output_path> -b pipeline
```

For VLM backend with highest accuracy:
```bash
vparse -p <input_path> -o <output_path> -b vlm-auto-engine
```

For remote VLM server:
```bash
vparse -p <input_path> -o <output_path> -b vlm-http-client -u http://127.0.0.1:30000
```

#### API Usage

Start the FastAPI server:
```bash
vparse-api --host 0.0.0.0 --port 8000
```

Then send requests:
```bash
curl -X POST "http://localhost:8000/file_parse" \
  -F "files=@document.pdf" \
  -F "backend=hybrid-auto-engine" \
  -F "return_md=true"
```

#### Web UI

Start the Gradio interface:
```bash
vparse-gradio --server-name 0.0.0.0 --server-port 7860
```

Then open `http://localhost:7860` in your browser.

For detailed usage instructions, see the [Usage Guide](https://opendatalab.github.io/VParse/usage/).

---

## Development Roadmap

VParse is undergoing active development with a comprehensive roadmap to become a one-stop OCR toolkit.

### Planned Modules (15 Total)

| Module | Focus Area | Status | Tasks |
|--------|-----------|--------|-------|
| **M1** | Core Library & API Foundation | 🚧 37.5% | 8 tasks |
| **M2** | Backend Engine Abstraction | 📋 6.25% | 8 tasks |
| **M3** | Pipeline Backend Enhancements | 🚧 43.75% | 8 tasks |
| **M4** | Multi-Model VLM Backend | 📋 18.2% | 11 tasks |
| **M5** | Inference Engine Integration | 🚧 44.4% | 9 tasks |
| **M6** | Memory & Performance Optimization | 📋 27.3% | 11 tasks |
| **M7** | KV Cache Optimization | 📋 0% | 11 tasks |
| **M8** | Bulk Processing & Job Management | 📋 13.6% | 11 tasks |
| **M9** | Docker & Deployment Services | 🚧 45.5% | 11 tasks |
| **M10** | API Server Features | 📋 30% | 10 tasks |
| **M11** | Document Processing Pipeline | 📋 31.8% | 11 tasks |
| **M12** | Output Formats & Export | 📋 31.8% | 11 tasks |
| **M13** | Testing & Quality Assurance | 📋 25% | 10 tasks |
| **M14** | Monitoring & Observability | 📋 5.6% | 9 tasks |
| **M15** | Developer Experience & Docs | 📋 35% | 10 tasks |

### Implementation Waves

| Wave | Focus | Timeline | Key Deliverables |
|------|-------|----------|------------------|
| **Wave 1** | Foundation | Weeks 1-4 | Unified API, Tesseract `lite` backend, PyPI package |
| **Wave 2** | Multi-Model VLM | Weeks 5-8 | Qwen2-VL, InternVL2, model auto-selection |
| **Wave 3** | Memory & Performance | Weeks 9-12 | KV cache optimization, streaming, OOM prevention |
| **Wave 4** | Bulk Processing & Docker | Weeks 13-16 | Job queue, Redis/Celery, production Docker |
| **Wave 5** | Output & Processing | Weeks 17-20 | DOCX, searchable PDF, RAG chunks |
| **Wave 6** | Quality & Docs | Weeks 21-24 | 85%+ tests, monitoring, documentation |
| **Wave 7** | Polish & Advanced | Weeks 25+ | K8s, Helm, advanced optimizations |

📋 **For complete details with task descriptions, file references, and contribution guides, see [ROADMAP.md](ROADMAP.md).**

---

## Known Issues

- Reading order is determined by the model based on the spatial distribution of readable content, and may be out of order in some areas under extremely complex layouts.
- Limited support for vertical text.
- Tables of contents and lists are recognized through rules, and some uncommon list formats may not be recognized.
- Code blocks are not yet supported in the layout model.
- Comic books, art albums, primary school textbooks, and exercises cannot be parsed well.
- Table recognition may result in row/column recognition errors in complex tables.
- OCR recognition may produce inaccurate characters in PDFs of lesser-known languages (e.g., diacritical marks in Latin script, easily confused characters in Arabic script).
- Some formulas may not render correctly in Markdown.

---

## FAQ

- If you encounter any issues during usage, you can first check the [FAQ](https://opendatalab.github.io/VParse/faq/) for solutions.
- If your issue remains unresolved, you may also use [DeepWiki](https://deepwiki.com/opendatalab/VParse) to interact with an AI assistant, which can address most common problems.
- If you still cannot resolve the issue, you are welcome to join our community via [Discord](https://discord.gg/Tdedn9GTXq) or [WeChat](https://vparse.net/community-portal/?aliasId=3c430f94) to discuss with other users and developers.

---

## Contributing

We welcome contributions. Please note:

1. **Primary namespace**: The codebase now uses the `vparse` namespace by default
2. **Compatibility namespace**: The legacy `mineru` namespace remains available for backward compatibility
3. **Contributing to roadmap**: See [ROADMAP.md](ROADMAP.md) for detailed task breakdown
4. **Pick a task**: Each module has specific files to create/modify and implementation details

### For Contributors

```bash
# Fork and clone
git clone https://github.com/your-username/VParse-dots.git
cd VParse-dots

# Set up dev environment
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,test]"

# Run tests
pytest tests/
```

See [ROADMAP.md](ROADMAP.md) for detailed contribution guidelines and task assignments.

---

## License Information

[LICENSE.md](LICENSE.md)

Some models in this project are trained based on YOLO. Since YOLO follows the AGPL license, it may impose restrictions on certain use cases. In future iterations, we plan to explore and replace these with models under more permissive licenses.

---

## Acknowledgments

- [VParse (Original Project)](https://github.com/opendatalab/VParse)
- [PDF-Extract-Kit](https://github.com/opendatalab/PDF-Extract-Kit)
- [DocLayout-YOLO](https://github.com/opendatalab/DocLayout-YOLO)
- [dots.ocr](https://huggingface.co/rednote-hilab/dots.mocr) - Multilingual document parsing VLM
- [UniMERNet](https://github.com/opendatalab/UniMERNet)
- [RapidTable](https://github.com/RapidAI/RapidTable)
- [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [vLLM](https://github.com/vllm-project/vllm)
- [LMDeploy](https://github.com/InternLM/lmdeploy)

---

## Citation

```bibtex
@article{dong2026minerudiffusion,
  title={VParse-Diffusion: Rethinking Document OCR as Inverse Rendering via Diffusion Decoding},
  author={Dong, Hejun and Niu, Junbo and Wang, Bin and Zeng, Weijun and Zhang, Wentao and He, Conghui},
  journal={arXiv preprint arXiv:2603.22458},
  year={2026}
}

@article{niu2025mineru2,
  title={Mineru2. 5: A decoupled vision-language model for efficient high-resolution document parsing},
  author={Niu, Junbo and Liu, Zheng and Gu, Zhuangcheng and Wang, Bin and Ouyang, Linke and Zhao, Zhiyuan and Chu, Tao and He, Tianyao and Wu, Fan and Zhang, Qintong and others},
  journal={arXiv preprint arXiv:2509.22186},
  year={2025}
}

@article{wang2024mineru,
  title={Mineru: An open-source solution for precise document content extraction},
  author={Wang, Bin and Xu, Chao and Zhao, Xiaomeng and Ouyang, Linke and Wu, Fan and Zhao, Zhiyuan and Xu, Rui and Liu, Kaiwen and Qu, Yuan and Shang, Fukai and others},
  journal={arXiv preprint arXiv:2409.18839},
  year={2024}
}
```

---

**Last Updated**: April 8, 2026  
**Project Status**: Active Development & Rebranding  
**Version**: 2.7.6 (VParse development branch)
