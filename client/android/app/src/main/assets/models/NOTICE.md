# Acoustic Wake-Word Models & Runtime License Notice

This application bundles on-device acoustic keyword spotting models and runtimes for local, offline wake-word activation.

---

## 1. Feature Extraction Models
- **`melspectrogram.onnx`**
  - **Source**: [openWakeWord](https://github.com/dscripka/openWakeWord)
  - **Author**: David Scripka
  - **License**: Apache 2.0

- **`embedding_model.onnx`**
  - **Source**: [openWakeWord](https://github.com/dscripka/openWakeWord) (based on Google Speech Embedding CNN backbone)
  - **Author**: David Scripka / Google Research
  - **License**: Apache 2.0

---

## 2. Wake-Word Classifier Model
- **`hey_jarvis.onnx`**
  - **Source**: [openWakeWord](https://github.com/dscripka/openWakeWord)
  - **Target Phrase**: "Hey Jarvis"
  - **Author**: David Scripka
  - **License**: [Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
  - **Usage**: Permitted for personal, open-source, and non-commercial projects.

---

## 3. ONNX Runtime Mobile
- **Package**: `com.microsoft.onnxruntime:onnxruntime-android:1.19.2`
  - **Author**: Microsoft Corporation
  - **License**: MIT License
