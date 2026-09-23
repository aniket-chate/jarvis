"""
Wake Word Model Validator for JARVIS
Validates that jarvis.onnx, friday.onnx, ultron.onnx, and omi.onnx exist and are loadable by openWakeWord.
"""

import os
import sys

REQUIRED_MODELS = [
    "jarvis.onnx",
    "friday.onnx",
    "ultron.onnx",
    "omi.onnx",
]

def validate_models():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Scanning directory: {base_dir}")
    
    missing = []
    present = []
    
    for model_name in REQUIRED_MODELS:
        full_path = os.path.join(base_dir, model_name)
        if not os.path.exists(full_path):
            missing.append(model_name)
        else:
            file_size = os.path.getsize(full_path)
            if file_size < 1000:
                print(f"[ERROR] {model_name} exists but appears corrupt/too small ({file_size} bytes).")
                missing.append(model_name)
            else:
                present.append((model_name, full_path, file_size))
                
    if missing:
        print(f"[STATUS] Missing {len(missing)} of {len(REQUIRED_MODELS)} model(s): {', '.join(missing)}")
        print("Please complete the Google Colab training workflow to generate these ONNX models.")
        return False
        
    # Attempt to load with openWakeWord
    try:
        import openwakeword
        from openwakeword.model import Model
        model_paths = [p[1] for p in present]
        oww_model = Model(wakeword_models=model_paths)
        print("[SUCCESS] All 4 models loaded successfully into openWakeWord!")
        for name, path, size in present:
            print(f"  - {name}: {size:,} bytes [VALID]")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to load models with openWakeWord: {e}")
        return False

if __name__ == "__main__":
    success = validate_models()
    sys.exit(0 if success else 1)
