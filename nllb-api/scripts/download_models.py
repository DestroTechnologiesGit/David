#!/usr/bin/env python3
"""Download models to local cache and copy to models/ directory for Docker builds.
Only downloads if models don't already exist locally."""

import os
import shutil
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download, snapshot_download


def check_model_exists(model_id: str, cache_dir: str) -> bool:
    """Check if model already exists in cache."""
    # Check both hub/ format and legacy format
    model_cache_hub = os.path.join(cache_dir, "hub", f"models--{model_id.replace('/', '--')}")
    model_cache_legacy = os.path.join(cache_dir, f"models--{model_id.replace('/', '--')}")
    
    if os.path.exists(model_cache_hub) or os.path.exists(model_cache_legacy):
        print(f"✅ Model {model_id} already exists in cache")
        return True
    return False


def main() -> None:
    """Download models and copy to models/ directory."""
    cache_dir = os.path.expanduser("~/.cache/huggingface")

    print("Checking for existing models in cache...")
    try:
        # Check and download translation model
        translation_model_id = "OpenNMT/nllb-200-3.3B-ct2-int8"
        if check_model_exists(translation_model_id, cache_dir):
            print(f"⏭️  Translation model already exists, skipping download")
        else:
            print("Downloading translation model...")
            translation_path = snapshot_download(translation_model_id, cache_dir=cache_dir)
            print(f"✅ Translation model downloaded to: {translation_path}")

        # Check and download language detection model
        lang_model_id = "facebook/fasttext-language-identification"
        if check_model_exists(lang_model_id, cache_dir):
            print(f"⏭️  Language detection model already exists, skipping download")
        else:
            print("Downloading language detection model...")
            lang_path = hf_hub_download(lang_model_id, "model.bin", cache_dir=cache_dir)
            print(f"✅ Language detection model downloaded to: {lang_path}")

        print(f"Models ready in cache: {cache_dir}")

        # Copy only the specific models we need to models/ directory
        print("Copying to models/ directory...")
        
        # Create models directory structure
        models_dir = "models"
        if os.path.exists(models_dir):
            shutil.rmtree(models_dir)
        os.makedirs(models_dir)
        
        # Copy only the specific model directories we need
        # Translation model: OpenNMT/nllb-200-3.3B-ct2-int8
        # Check both hub/ format and legacy format
        translation_model_cache_hub = os.path.join(cache_dir, "hub", "models--OpenNMT--nllb-200-3.3B-ct2-int8")
        translation_model_cache_legacy = os.path.join(cache_dir, "models--OpenNMT--nllb-200-3.3B-ct2-int8")
        
        if os.path.exists(translation_model_cache_hub):
            print(f"Copying translation model from {translation_model_cache_hub}...")
            os.makedirs(os.path.join(models_dir, "hub"), exist_ok=True)
            shutil.copytree(translation_model_cache_hub, os.path.join(models_dir, "hub", "models--OpenNMT--nllb-200-3.3B-ct2-int8"))
            print("Translation model copied successfully")
        elif os.path.exists(translation_model_cache_legacy):
            print(f"Copying translation model from {translation_model_cache_legacy}...")
            shutil.copytree(translation_model_cache_legacy, os.path.join(models_dir, "models--OpenNMT--nllb-200-3.3B-ct2-int8"))
            print("Translation model copied successfully")
        else:
            print(f"ERROR: Translation model not found at {translation_model_cache_hub} or {translation_model_cache_legacy}", file=sys.stderr)
            sys.exit(1)
        
        # Language detection model: facebook/fasttext-language-identification
        # Check both hub/ format and legacy format
        lang_model_cache_hub = os.path.join(cache_dir, "hub", "models--facebook--fasttext-language-identification")
        lang_model_cache_legacy = os.path.join(cache_dir, "models--facebook--fasttext-language-identification")
        
        if os.path.exists(lang_model_cache_hub):
            print(f"Copying language detection model from {lang_model_cache_hub}...")
            os.makedirs(os.path.join(models_dir, "hub"), exist_ok=True)
            shutil.copytree(lang_model_cache_hub, os.path.join(models_dir, "hub", "models--facebook--fasttext-language-identification"))
            print("Language detection model copied successfully")
        elif os.path.exists(lang_model_cache_legacy):
            print(f"Copying language detection model from {lang_model_cache_legacy}...")
            shutil.copytree(lang_model_cache_legacy, os.path.join(models_dir, "models--facebook--fasttext-language-identification"))
            print("Language detection model copied successfully")
        else:
            print(f"ERROR: Language detection model not found at {lang_model_cache_hub} or {lang_model_cache_legacy}", file=sys.stderr)
            sys.exit(1)
        
        print("All models copied to models/ directory")

    except Exception as e:
        print(f"Error downloading models: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

