# OpenWakeWord Custom Model Training & Setup Guide

## Required Models
Four custom ONNX wake-word models are required in this directory:
- `jarvis.onnx`
- `friday.onnx`
- `ultron.onnx`
- `omi.onnx`

## Training Workflow via Google Colab

The official openWakeWord automated synthetic training pipeline runs in Google Colab (free GPU tier):

1. **Open the Training Notebook**:
   - Official openWakeWord Notebook: [Google Colab Link](https://colab.research.google.com/github/dscripka/openWakeWord/blob/main/notebooks/automatic_model_training.ipynb)
   - Alternative updated 2026 repository: [alfiedennen/openwakeword-colab-2026](https://github.com/alfiedennen/openwakeword-colab-2026)

2. **Configure Runtime**:
   - In Colab, click **Runtime** > **Change runtime type**.
   - Select **T4 GPU** (Hardware accelerator).

3. **Train Each Wake Word**:
   - Set `target_phrase` for each run:
     - Run 1: `"Jarvis"` or `"Hey Jarvis"` -> output exported to `jarvis.onnx`
     - Run 2: `"Friday"` or `"Hey Friday"` -> output exported to `friday.onnx`
     - Run 3: `"Ultron"` or `"Hey Ultron"` -> output exported to `ultron.onnx`
     - Run 4: `"Omi"` or `"Hey Omi"` -> output exported to `omi.onnx`
   - Run the cells to generate synthetic TTS data (using Piper TTS) and train the openWakeWord binary classifier.

4. **Download and Place Models**:
   - Download the generated `.onnx` files.
   - Place them directly in `JARVIS/models/wakewords/` with the exact filenames:
     - `jarvis.onnx`
     - `friday.onnx`
     - `ultron.onnx`
     - `omi.onnx`

5. **Validation**:
   - Run `python validate_wakewords.py` to verify ONNX structure and openWakeWord compatibility.
