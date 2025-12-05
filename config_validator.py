#!/usr/bin/env python3
"""
Configuration Validator for Real-time Speech Translator
Validates configuration before runtime to prevent crashes
"""

import sys
from typing import Dict, Any, List, Optional


class ConfigValidator:
    """Validates translator configuration"""
    
    # Valid configuration options
    VALID_WHISPER_MODELS = ['tiny', 'base', 'small', 'medium', 'large']
    
    VALID_WHISPER_LANGUAGES = [
        'en', 'zh', 'de', 'es', 'ru', 'ko', 'fr', 'ja', 'pt', 'tr', 'pl', 'ca', 'nl',
        'ar', 'sv', 'it', 'id', 'hi', 'fi', 'vi', 'he', 'uk', 'el', 'ms', 'cs', 'ro',
        'da', 'hu', 'ta', 'no', 'th', 'ur', 'hr', 'bg', 'lt', 'la', 'mi', 'ml', 'cy',
        'sk', 'te', 'fa', 'lv', 'bn', 'sr', 'az', 'sl', 'kn', 'et', 'mk', 'br', 'eu',
        'is', 'hy', 'ne', 'mn', 'bs', 'kk', 'sq', 'sw', 'gl', 'mr', 'pa', 'si', 'km',
        'sn', 'yo', 'so', 'af', 'oc', 'ka', 'be', 'tg', 'sd', 'gu', 'am', 'yi', 'lo',
        'uz', 'fo', 'ht', 'ps', 'tk', 'nn', 'mt', 'sa', 'lb', 'my', 'bo', 'tl', 'mg',
        'as', 'tt', 'haw', 'ln', 'ha', 'ba', 'jw', 'su', 'auto'
    ]
    
    VALID_NLLB_LANGUAGES = [
        'eng_Latn', 'fra_Latn', 'spa_Latn', 'deu_Latn', 'ita_Latn', 'por_Latn',
        'rus_Cyrl', 'jpn_Jpan', 'kor_Hang', 'zho_Hans', 'zho_Hant', 'ara_Arab',
        'hin_Deva', 'ben_Beng', 'urd_Arab', 'pes_Arab', 'pol_Latn', 'ukr_Cyrl',
        'nld_Latn', 'tur_Latn', 'vie_Latn', 'tha_Thai', 'heb_Hebr', 'ell_Grek',
        'ces_Latn', 'ron_Latn', 'swe_Latn', 'dan_Latn', 'fin_Latn', 'nor_Latn',
        'ind_Latn', 'msa_Latn', 'cat_Latn', 'hun_Latn', 'slk_Latn', 'bul_Cyrl',
        'srp_Cyrl', 'hrv_Latn', 'lit_Latn', 'lav_Latn', 'est_Latn', 'slv_Latn'
    ]
    
    def __init__(self, strict: bool = False):
        """
        Initialize validator
        
        Args:
            strict: If True, treats warnings as errors
        """
        self.strict = strict
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate(self, config: Dict[str, Any]) -> bool:
        """
        Validate configuration
        
        Args:
            config: Configuration dictionary
        
        Returns:
            True if valid, False otherwise
        """
        self.errors = []
        self.warnings = []
        
        # Validate each section
        self._validate_audio(config)
        self._validate_whisper(config)
        self._validate_translation(config)
        self._validate_performance(config)
        self._validate_general(config)
        
        # Check for errors
        has_errors = len(self.errors) > 0
        has_warnings = len(self.warnings) > 0
        
        if has_errors or (self.strict and has_warnings):
            return False
        
        return True
    
    def _validate_audio(self, config: Dict[str, Any]):
        """Validate audio configuration"""
        sample_rate = config.get('sample_rate', 16000)
        chunk_duration = config.get('chunk_duration', 3)
        buffer_duration = config.get('buffer_duration', 1)
        
        # Sample rate
        if not isinstance(sample_rate, int):
            self.errors.append(f"sample_rate must be an integer, got {type(sample_rate).__name__}")
        elif sample_rate < 8000 or sample_rate > 48000:
            self.warnings.append(f"sample_rate {sample_rate} is unusual. Recommended: 16000 Hz")
        
        # Chunk duration
        if not isinstance(chunk_duration, (int, float)):
            self.errors.append(f"chunk_duration must be a number, got {type(chunk_duration).__name__}")
        elif chunk_duration < 0.5 or chunk_duration > 30:
            self.warnings.append(f"chunk_duration {chunk_duration}s is unusual. Recommended: 2-5 seconds")
        
        # Buffer duration
        if not isinstance(buffer_duration, (int, float)):
            self.errors.append(f"buffer_duration must be a number, got {type(buffer_duration).__name__}")
        elif buffer_duration >= chunk_duration:
            self.errors.append(f"buffer_duration ({buffer_duration}s) must be less than chunk_duration ({chunk_duration}s)")
        elif buffer_duration < 0:
            self.errors.append("buffer_duration cannot be negative")
    
    def _validate_whisper(self, config: Dict[str, Any]):
        """Validate Whisper configuration"""
        model = config.get('whisper_model', 'base')
        source_lang = config.get('source_language', 'en')
        
        # Model size
        if model not in self.VALID_WHISPER_MODELS:
            self.errors.append(
                f"Invalid whisper_model '{model}'. "
                f"Valid options: {', '.join(self.VALID_WHISPER_MODELS)}"
            )
        
        # Source language
        if source_lang not in self.VALID_WHISPER_LANGUAGES:
            self.warnings.append(
                f"Unknown source_language '{source_lang}'. "
                f"This may still work, but verify it's a valid Whisper language code."
            )
    
    def _validate_translation(self, config: Dict[str, Any]):
        """Validate translation configuration"""
        target_lang = config.get('target_language', 'eng_Latn')
        num_beams = config.get('num_beams', 5)
        nllb_model = config.get('nllb_model', 'facebook/nllb-200-distilled-600M')
        
        # Target language
        if target_lang not in self.VALID_NLLB_LANGUAGES:
            self.warnings.append(
                f"Unknown target_language '{target_lang}'. "
                f"This may still work, but verify it's a valid NLLB language code."
            )
        
        # Num beams
        if not isinstance(num_beams, int):
            self.errors.append(f"num_beams must be an integer, got {type(num_beams).__name__}")
        elif num_beams < 1 or num_beams > 20:
            self.warnings.append(f"num_beams {num_beams} is unusual. Recommended: 3-10")
        
        # NLLB model
        valid_nllb_models = [
            'facebook/nllb-200-distilled-600M',
            'facebook/nllb-200-distilled-1.3B',
            'facebook/nllb-200-1.3B',
            'facebook/nllb-200-3.3B'
        ]
        if nllb_model not in valid_nllb_models:
            self.warnings.append(
                f"Unknown NLLB model '{nllb_model}'. "
                f"Valid options: {', '.join(valid_nllb_models)}"
            )
    
    def _validate_performance(self, config: Dict[str, Any]):
        """Validate performance configuration"""
        use_gpu = config.get('use_gpu', True)
        fp16 = config.get('fp16', False)
        
        if not isinstance(use_gpu, bool):
            self.errors.append(f"use_gpu must be a boolean, got {type(use_gpu).__name__}")
        
        if not isinstance(fp16, bool):
            self.errors.append(f"fp16 must be a boolean, got {type(fp16).__name__}")
        
        # FP16 requires GPU
        if fp16 and not use_gpu:
            self.warnings.append("fp16 is enabled but use_gpu is disabled. FP16 requires CUDA.")
    
    def _validate_general(self, config: Dict[str, Any]):
        """Validate general configuration"""
        verbose = config.get('verbose', True)
        save_to_file = config.get('save_to_file', False)
        output_file = config.get('output_file', 'transcriptions.txt')
        
        if not isinstance(verbose, bool):
            self.errors.append(f"verbose must be a boolean, got {type(verbose).__name__}")
        
        if not isinstance(save_to_file, bool):
            self.errors.append(f"save_to_file must be a boolean, got {type(save_to_file).__name__}")
        
        if save_to_file and not isinstance(output_file, str):
            self.errors.append(f"output_file must be a string, got {type(output_file).__name__}")
    
    def get_report(self) -> str:
        """Get validation report"""
        report = []
        
        if self.errors:
            report.append("❌ ERRORS:")
            for error in self.errors:
                report.append(f"   - {error}")
            report.append("")
        
        if self.warnings:
            report.append("⚠️  WARNINGS:")
            for warning in self.warnings:
                report.append(f"   - {warning}")
            report.append("")
        
        if not self.errors and not self.warnings:
            report.append("✅ Configuration is valid!")
        
        return "\n".join(report)
    
    def print_report(self):
        """Print validation report"""
        print(self.get_report())


def validate_config_file(config_file: str, strict: bool = False) -> bool:
    """
    Validate a configuration file
    
    Args:
        config_file: Path to configuration file
        strict: If True, treats warnings as errors
    
    Returns:
        True if valid, False otherwise
    """
    import configparser
    
    if not os.path.exists(config_file):
        print(f"❌ Configuration file not found: {config_file}")
        return False
    
    # Parse config file
    parser = configparser.ConfigParser()
    try:
        parser.read(config_file)
    except Exception as e:
        print(f"❌ Error parsing configuration file: {e}")
        return False
    
    # Convert to dict
    config = {}
    
    if "Audio" in parser:
        config["sample_rate"] = parser.getint("Audio", "sample_rate", fallback=16000)
        config["chunk_duration"] = parser.getfloat("Audio", "chunk_duration", fallback=3)
        config["buffer_duration"] = parser.getfloat("Audio", "buffer_duration", fallback=1)
    
    if "Whisper" in parser:
        config["whisper_model"] = parser.get("Whisper", "model_size", fallback="base")
        config["source_language"] = parser.get("Whisper", "source_language", fallback="en")
    
    if "Translation" in parser:
        config["target_language"] = parser.get("Translation", "target_language", fallback="eng_Latn")
        config["nllb_model"] = parser.get("Translation", "nllb_model", fallback="facebook/nllb-200-distilled-600M")
        config["num_beams"] = parser.getint("Translation", "num_beams", fallback=5)
    
    if "General" in parser:
        config["verbose"] = parser.getboolean("General", "verbose", fallback=True)
        config["save_to_file"] = parser.getboolean("General", "save_to_file", fallback=False)
        config["output_file"] = parser.get("General", "output_file", fallback="transcriptions.txt")
    
    if "Performance" in parser:
        config["use_gpu"] = parser.getboolean("Performance", "use_gpu", fallback=True)
        config["fp16"] = parser.getboolean("Performance", "fp16", fallback=False)
    
    # Validate
    validator = ConfigValidator(strict=strict)
    is_valid = validator.validate(config)
    
    validator.print_report()
    
    return is_valid


def main():
    """Command-line interface for config validation"""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(
        description="Validate Real-time Translator configuration"
    )
    parser.add_argument("config_file", help="Path to configuration file")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("  Configuration Validator")
    print("=" * 80)
    print()
    
    is_valid = validate_config_file(args.config_file, args.strict)
    
    print()
    print("=" * 80)
    
    if is_valid:
        print("✅ Configuration is valid and ready to use!")
        sys.exit(0)
    else:
        print("❌ Configuration has issues. Please fix them before running.")
        sys.exit(1)


if __name__ == "__main__":
    import os
    main()
