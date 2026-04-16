# Model Source Documentation

VParse uses `HuggingFace` and `ModelScope` as model repositories. Users can switch model sources or use local models as needed.

- `HuggingFace` is the default model source, providing excellent loading speed and high stability globally.
- `ModelScope` is the best choice for users in mainland China, providing seamlessly compatible `hf` SDK modules, suitable for users who cannot access HuggingFace.

## Default VLM Model: dots.ocr

VParse uses **dots.ocr** (`rednote-hilab/dots.mocr`) as the default VLM model for the `vlm-auto-engine` and `hybrid-auto-engine` backends. This is a 3B parameter multilingual document parsing VLM that supports:

- Layout detection (title, text, table, image, formula, list, etc.)
- OCR in 109+ languages
- Formula detection and recognition

### dots.ocr Model Sources

| Source | Model Path |
|--------|------------|
| HuggingFace | `rednote-hilab/dots.mocr` |
| ModelScope | `rednote-hilab/dots.ocr` |

The model source is controlled by the same `VPARSE_MODEL_SOURCE` environment variable as other models.

## Methods to Switch Model Sources

### Switch via Command Line Parameters
Currently, only the `vparse` command line tool supports switching model sources through command line parameters. Other command line tools such as `vparse-api`, `vparse-gradio`, etc., do not support this yet.
```bash
vparse -p <input_path> -o <output_path> --source modelscope
```

### Switch via Environment Variables
You can switch model sources by setting environment variables in any situation. This applies to all command line tools and API calls.
```bash
export VPARSE_MODEL_SOURCE=modelscope
```
or
```python
import os
os.environ["VPARSE_MODEL_SOURCE"] = "modelscope"
```
>[!TIP]
> Model sources set through environment variables will take effect in the current terminal session until the terminal is closed or the environment variable is modified. They have higher priority than command line parameters - if both command line parameters and environment variables are set, the command line parameters will be ignored.

## Using Local Models

### 1. Download Models to Local Storage
```bash
vparse-models-download --help
```
or use the interactive command line tool to select model downloads:
```bash
vparse-models-download
```
> [!NOTE]
>- After download completion, the model path will be output in the current terminal window and automatically written to `~/.vparse.json`.
>- You can also create it by copying the [configuration template file](https://github.com/opendatalab/VParse/blob/master/vparse.template.json) to your user directory and renaming it to `.vparse.json`.
>- After downloading models locally, you can freely move the model folder to other locations while updating the model path in `~/.vparse.json`.
>- If you deploy the model folder to another server, please ensure you move the `~/.vparse.json` file to the user directory of the new device and configure the model path correctly.
>- If you need to update model files, you can run the `vparse-models-download` command again. Model updates do not support custom paths currently. If you have not moved the local model folder, model files will be incrementally updated; if you have moved the model folder, model files will be re-downloaded to the default location and `~/.vparse.json` will be updated.
>- Legacy config files such as `~/.mineru.json`, `~/vparse.json`, and `~/mineru.json` are still read if `~/.vparse.json` is absent.

### 2. Use Local Models for Parsing

```bash
vparse -p <input_path> -o <output_path> --source local
```
or enable through environment variables:
```bash
export VPARSE_MODEL_SOURCE=local
vparse -p <input_path> -o <output_path>
```
