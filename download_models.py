#!/usr/bin/env python3
"""Model download script for LocalVoice.

This script downloads Whisper models for offline use.
Run this once after installation to ensure models are available offline.
"""

import argparse
import sys
from pathlib import Path

MODEL_SIZES = ['tiny', 'tiny.en', 'base', 'base.en', 'small', 'small.en', 
               'medium', 'medium.en', 'large', 'large-v2', 'large-v3']

MODEL_INFO = {
    'tiny': ('39M', 'Fastest, least accurate'),
    'tiny.en': ('39M', 'Fastest, English only'),
    'base': ('74M', 'Fast, good accuracy'),
    'base.en': ('74M', 'Fast, English only'),
    'small': ('244M', 'Medium speed, better accuracy'),
    'small.en': ('244M', 'Medium speed, English only'),
    'medium': ('769M', 'Slower, high accuracy'),
    'medium.en': ('769M', 'Slower, English only'),
    'large': ('1550M', 'Slowest, highest accuracy'),
    'large-v2': ('1550M', 'Large v2, highest accuracy'),
    'large-v3': ('1550M', 'Large v3, latest model'),
}


def download_model(model_size: str, model_dir: Path) -> bool:
    """Download a specific model."""
    print(f"\nDownloading {model_size} model...")
    print(f"Model directory: {model_dir}")
    
    try:
        from faster_whisper import WhisperModel
        
        model_path = str(model_dir)
        
        _ = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=model_path
        )
        
        print(f"Successfully downloaded {model_size} model!")
        return True
        
    except Exception as e:
        print(f"Failed to download {model_size} model: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Download Whisper models for LocalVoice offline use"
    )
    parser.add_argument(
        'models',
        nargs='*',
        choices=['all'] + MODEL_SIZES,
        default=['base'],
        help="Models to download (default: base). Use 'all' for all models."
    )
    parser.add_argument(
        '--dir',
        type=str,
        default=None,
        help="Custom directory to store models (default: ~/.localvoice/models)"
    )
    parser.add_argument(
        '--list',
        action='store_true',
        help="List available models and exit"
    )
    
    args = parser.parse_args()
    
    if args.list:
        print("\nAvailable Whisper Models:")
        print("-" * 50)
        for model, (size, description) in MODEL_INFO.items():
            print(f"  {model:12} ({size:>6}) - {description}")
        print()
        return 0
    
    if args.dir:
        model_dir = Path(args.dir)
    else:
        model_dir = Path.home() / ".localvoice" / "models"
    
    model_dir.mkdir(parents=True, exist_ok=True)
    
    models_to_download = MODEL_SIZES if 'all' in args.models else args.models
    
    print("=" * 50)
    print("LocalVoice Model Downloader")
    print("=" * 50)
    print(f"\nModels to download: {', '.join(models_to_download)}")
    
    success_count = 0
    for model in models_to_download:
        if download_model(model, model_dir):
            success_count += 1
    
    print("\n" + "=" * 50)
    print(f"Download complete: {success_count}/{len(models_to_download)} models")
    print("=" * 50)
    
    return 0 if success_count == len(models_to_download) else 1


if __name__ == '__main__':
    sys.exit(main())