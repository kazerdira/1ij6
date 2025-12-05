#!/usr/bin/env python3
"""
REST API for Real-time Speech Translator
Production-ready FastAPI service with OpenAPI documentation
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict
import uvicorn
import numpy as np
import soundfile as sf
import tempfile
import os
import time
from datetime import datetime
import logging
from io import BytesIO

# Import translator
from vad_translator import VADRealtimeTranslator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/api.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Real-time Speech Translator API",
    description="Production-grade API for speech transcription and translation",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global translator instance (lazy loaded)
translator_instance = None
translator_lock = False


class TranslationRequest(BaseModel):
    """Request model for text translation"""
    text: str = Field(..., description="Text to translate")
    source_language: str = Field("ko", description="Source language code")
    target_language: str = Field("eng_Latn", description="Target language code")


class TranscriptionConfig(BaseModel):
    """Configuration for transcription"""
    source_language: str = Field("ko", description="Source language code")
    target_language: str = Field("eng_Latn", description="Target language code")
    whisper_model: str = Field("base", description="Whisper model size")
    use_vad: bool = Field(True, description="Enable voice activity detection")


class TranslationResponse(BaseModel):
    """Response model for translations"""
    original: str
    translated: str
    source_language: str
    target_language: str
    processing_time: float
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    models_loaded: bool
    version: str


def get_translator(config: Optional[TranscriptionConfig] = None) -> VADRealtimeTranslator:
    """Get or create translator instance"""
    global translator_instance, translator_lock
    
    if translator_lock:
        raise HTTPException(status_code=503, detail="Translator is initializing")
    
    if translator_instance is None:
        translator_lock = True
        try:
            logger.info("Initializing translator...")
            
            # Use config or defaults
            if config:
                source_lang = config.source_language
                target_lang = config.target_language
                model = config.whisper_model
                use_vad = config.use_vad
            else:
                source_lang = os.getenv("SOURCE_LANGUAGE", "ko")
                target_lang = os.getenv("TARGET_LANGUAGE", "eng_Latn")
                model = os.getenv("WHISPER_MODEL", "base")
                use_vad = True
            
            translator_instance = VADRealtimeTranslator(
                source_language=source_lang,
                target_language=target_lang,
                whisper_model=model,
                vad_aggressiveness=3 if use_vad else 0,
                log_file="logs/translator.log",
                verbose=False
            )
            
            logger.info("Translator initialized successfully")
        finally:
            translator_lock = False
    
    return translator_instance


@app.get("/", tags=["General"])
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Real-time Speech Translator API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        models_loaded=translator_instance is not None,
        version="1.0.0"
    )


@app.post("/translate/text", response_model=TranslationResponse, tags=["Translation"])
async def translate_text(request: TranslationRequest):
    """
    Translate text from one language to another
    
    - **text**: Text to translate
    - **source_language**: Source language code (e.g., 'ko', 'ja', 'zh')
    - **target_language**: Target language code (e.g., 'eng_Latn', 'fra_Latn')
    """
    try:
        start_time = time.time()
        
        # Get translator
        translator = get_translator()
        
        # Translate
        translated = translator.translate_text(request.text)
        
        processing_time = time.time() - start_time
        
        return TranslationResponse(
            original=request.text,
            translated=translated,
            source_language=request.source_language,
            target_language=request.target_language,
            processing_time=processing_time,
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe/audio", response_model=TranslationResponse, tags=["Transcription"])
async def transcribe_audio(
    file: UploadFile = File(...),
    source_language: str = "ko",
    target_language: str = "eng_Latn",
    translate: bool = True
):
    """
    Transcribe and translate audio file
    
    - **file**: Audio file (WAV, MP3, FLAC, etc.)
    - **source_language**: Source language code
    - **target_language**: Target language code
    - **translate**: Whether to translate (if False, only transcribe)
    """
    try:
        start_time = time.time()
        
        # Get translator
        translator = get_translator()
        
        # Read audio file
        audio_bytes = await file.read()
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        
        try:
            # Load audio
            audio_data, sample_rate = sf.read(tmp_path)
            
            # Convert to mono if stereo
            if len(audio_data.shape) > 1:
                audio_data = audio_data[:, 0]
            
            # Resample to 16kHz if needed
            if sample_rate != 16000:
                from scipy import signal
                num_samples = int(len(audio_data) * 16000 / sample_rate)
                audio_data = signal.resample(audio_data, num_samples)
            
            # Process audio
            original, translated = translator.process_audio_chunk(audio_data)
            
            if not original:
                raise HTTPException(status_code=400, detail="No speech detected in audio")
            
            processing_time = time.time() - start_time
            
            return TranslationResponse(
                original=original,
                translated=translated if translate else original,
                source_language=source_language,
                target_language=target_language if translate else source_language,
                processing_time=processing_time,
                timestamp=datetime.now().isoformat()
            )
        
        finally:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe/batch", tags=["Transcription"])
async def transcribe_batch(
    files: List[UploadFile] = File(...),
    source_language: str = "ko",
    target_language: str = "eng_Latn",
    background_tasks: BackgroundTasks = None
):
    """
    Transcribe and translate multiple audio files
    
    - **files**: List of audio files
    - **source_language**: Source language code
    - **target_language**: Target language code
    """
    try:
        results = []
        
        for file in files:
            try:
                # Process each file
                audio_bytes = await file.read()
                
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                    tmp.write(audio_bytes)
                    tmp_path = tmp.name
                
                translator = get_translator()
                
                audio_data, sample_rate = sf.read(tmp_path)
                
                if len(audio_data.shape) > 1:
                    audio_data = audio_data[:, 0]
                
                original, translated = translator.process_audio_chunk(audio_data)
                
                results.append({
                    "filename": file.filename,
                    "success": True,
                    "original": original,
                    "translated": translated
                })
                
                os.unlink(tmp_path)
            
            except Exception as e:
                results.append({
                    "filename": file.filename,
                    "success": False,
                    "error": str(e)
                })
        
        return {"results": results}
    
    except Exception as e:
        logger.error(f"Batch transcription error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/languages", tags=["Configuration"])
async def get_supported_languages():
    """Get list of supported languages"""
    return {
        "whisper_languages": [
            "en", "zh", "de", "es", "ru", "ko", "fr", "ja", "pt", "tr", "pl",
            "ca", "nl", "ar", "sv", "it", "id", "hi", "fi", "vi", "he", "uk"
        ],
        "nllb_languages": [
            "eng_Latn", "fra_Latn", "spa_Latn", "deu_Latn", "ita_Latn",
            "por_Latn", "rus_Cyrl", "jpn_Jpan", "kor_Hang", "zho_Hans",
            "ara_Arab", "hin_Deva"
        ]
    }


@app.get("/models", tags=["Configuration"])
async def get_available_models():
    """Get list of available Whisper models"""
    return {
        "models": [
            {"name": "tiny", "size": "39M", "speed": "fastest", "quality": "good"},
            {"name": "base", "size": "74M", "speed": "fast", "quality": "good"},
            {"name": "small", "size": "244M", "speed": "medium", "quality": "better"},
            {"name": "medium", "size": "769M", "speed": "slow", "quality": "great"},
            {"name": "large", "size": "1550M", "speed": "slowest", "quality": "best"}
        ],
        "recommended": "base"
    }


@app.get("/stats", tags=["Statistics"])
async def get_statistics():
    """Get translator statistics"""
    if translator_instance is None:
        return {"message": "Translator not initialized"}
    
    return {
        "transcriptions": translator_instance.transcription_count,
        "translations": translator_instance.translation_count,
        "errors": translator_instance.error_count,
        "chunks_processed": translator_instance.chunks_processed,
        "chunks_skipped": translator_instance.chunks_skipped
    }


@app.post("/config/reload", tags=["Configuration"])
async def reload_config():
    """Reload translator configuration"""
    global translator_instance
    
    if translator_instance:
        translator_instance.stop()
        translator_instance = None
    
    return {"message": "Configuration reloaded. Translator will reinitialize on next request."}


if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs("logs", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)
    
    # Run server
    uvicorn.run(
        "rest_api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
