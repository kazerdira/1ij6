#!/usr/bin/env python3
"""
RunPod Serverless Handler
Real-time Speech Translator API
"""

import runpod
import torch
import whisper
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import numpy as np
import base64
import io
import os
import time

# Global models (loaded once, reused across requests)
whisper_model = None
nllb_model = None
nllb_tokenizer = None
device = None

def load_models():
    """Load models once at startup"""
    global whisper_model, nllb_model, nllb_tokenizer, device
    
    if whisper_model is not None:
        return  # Already loaded
    
    print("🔄 Loading models...")
    start = time.time()
    
    # Detect device
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"📱 Device: {device}")
    
    # Load Whisper
    whisper_size = os.getenv("WHISPER_MODEL", "base")
    print(f"🎤 Loading Whisper ({whisper_size})...")
    whisper_model = whisper.load_model(whisper_size, device=device)
    
    # Load NLLB-200
    print("🌍 Loading NLLB-200...")
    model_name = "facebook/nllb-200-distilled-600M"
    nllb_tokenizer = AutoTokenizer.from_pretrained(model_name)
    nllb_model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
    
    if device == "cuda":
        nllb_model = nllb_model.to(device)
    
    print(f"✅ Models loaded in {time.time() - start:.1f}s")


def transcribe_audio(audio_data: np.ndarray, source_language: str = None) -> str:
    """Transcribe audio using Whisper"""
    result = whisper_model.transcribe(
        audio_data,
        language=source_language[:2] if source_language else None,  # "en" from "eng_Latn"
        fp16=(device == "cuda")
    )
    return result["text"]


def translate_text(text: str, source_language: str, target_language: str) -> str:
    """Translate text using NLLB-200"""
    if not text.strip():
        return ""
    
    inputs = nllb_tokenizer(
        text,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=512
    )
    
    if device == "cuda":
        inputs = {k: v.to(device) for k, v in inputs.items()}
    
    target_lang_id = nllb_tokenizer.convert_tokens_to_ids(target_language)
    
    with torch.no_grad():
        translated_tokens = nllb_model.generate(
            **inputs,
            forced_bos_token_id=target_lang_id,
            max_length=512,
            num_beams=5,
            early_stopping=True
        )
    
    translated_text = nllb_tokenizer.batch_decode(
        translated_tokens,
        skip_special_tokens=True
    )[0]
    
    return translated_text


def handler(job):
    """
    RunPod Serverless Handler
    
    Input formats:
    1. Text translation:
       {"action": "translate", "text": "Hello", "source_language": "eng_Latn", "target_language": "fra_Latn"}
    
    2. Audio transcription + translation:
       {"action": "transcribe", "audio_base64": "...", "source_language": "eng_Latn", "target_language": "fra_Latn"}
    
    3. Audio transcription only:
       {"action": "transcribe_only", "audio_base64": "...", "source_language": "en"}
    
    4. Health check:
       {"action": "health"}
    """
    try:
        # Load models (cached after first call)
        load_models()
        
        job_input = job["input"]
        action = job_input.get("action", "translate")
        
        # Health check
        if action == "health":
            return {
                "status": "healthy",
                "device": device,
                "cuda_available": torch.cuda.is_available(),
                "models_loaded": whisper_model is not None
            }
        
        # Text translation
        if action == "translate":
            text = job_input.get("text", "")
            source_lang = job_input.get("source_language", "eng_Latn")
            target_lang = job_input.get("target_language", "fra_Latn")
            
            if not text:
                return {"error": "No text provided"}
            
            start = time.time()
            translated = translate_text(text, source_lang, target_lang)
            duration = time.time() - start
            
            return {
                "original": text,
                "translated": translated,
                "source_language": source_lang,
                "target_language": target_lang,
                "duration_ms": round(duration * 1000, 2)
            }
        
        # Audio transcription + translation
        if action == "transcribe":
            audio_base64 = job_input.get("audio_base64")
            source_lang = job_input.get("source_language", "eng_Latn")
            target_lang = job_input.get("target_language", "fra_Latn")
            
            if not audio_base64:
                return {"error": "No audio_base64 provided"}
            
            # Decode audio
            audio_bytes = base64.b64decode(audio_base64)
            audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
            
            start = time.time()
            
            # Transcribe
            transcribed = transcribe_audio(audio_array, source_lang)
            
            # Translate
            translated = translate_text(transcribed, source_lang, target_lang)
            
            duration = time.time() - start
            
            return {
                "transcribed": transcribed,
                "translated": translated,
                "source_language": source_lang,
                "target_language": target_lang,
                "duration_ms": round(duration * 1000, 2)
            }
        
        # Transcription only
        if action == "transcribe_only":
            audio_base64 = job_input.get("audio_base64")
            source_lang = job_input.get("source_language", "en")
            
            if not audio_base64:
                return {"error": "No audio_base64 provided"}
            
            audio_bytes = base64.b64decode(audio_base64)
            audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
            
            start = time.time()
            transcribed = transcribe_audio(audio_array, source_lang)
            duration = time.time() - start
            
            return {
                "transcribed": transcribed,
                "source_language": source_lang,
                "duration_ms": round(duration * 1000, 2)
            }
        
        return {"error": f"Unknown action: {action}"}
    
    except Exception as e:
        return {"error": str(e)}


# Start the serverless handler
runpod.serverless.start({"handler": handler})
