#!/usr/bin/env python3
"""
Input Validation and Sanitization
Prevents injection attacks, path traversal, and malformed data
"""

from fastapi import HTTPException, status, UploadFile
from typing import Optional, List
from pathlib import Path
import magic  # python-magic for file type detection
import hashlib
import re
from pydantic import BaseModel, validator, Field

# Configuration
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
MAX_TEXT_LENGTH = 100000  # 100k characters
MAX_FILENAME_LENGTH = 255

ALLOWED_AUDIO_FORMATS = {
    'audio/wav', 'audio/x-wav', 'audio/wave',
    'audio/mpeg', 'audio/mp3',
    'audio/flac',
    'audio/ogg', 'audio/opus',
    'audio/mp4', 'audio/m4a',
    'audio/aac'
}

ALLOWED_AUDIO_EXTENSIONS = {
    '.wav', '.mp3', '.flac', '.ogg', '.opus', '.m4a', '.aac'
}

# Dangerous file extensions (never allow)
DANGEROUS_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.sh', '.bash',
    '.py', '.pyc', '.pyo', '.pyw',
    '.php', '.jsp', '.asp', '.aspx',
    '.js', '.vbs', '.jar'
}


class InputValidator:
    """Comprehensive input validation"""
    
    @staticmethod
    def validate_text(text: str, field_name: str = "text") -> str:
        """Validate and sanitize text input"""
        if not text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} cannot be empty"
            )
        
        if not isinstance(text, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be a string"
            )
        
        if len(text) > MAX_TEXT_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"{field_name} exceeds maximum length of {MAX_TEXT_LENGTH} characters"
            )
        
        # Check for null bytes (attack vector)
        if '\x00' in text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} contains invalid null bytes"
            )
        
        # Remove control characters (except newline, tab, carriage return)
        text = ''.join(char for char in text if char in '\n\t\r' or not char.isspace() or char == ' ')
        
        return text.strip()
    
    @staticmethod
    def validate_language_code(code: str, field_name: str = "language") -> str:
        """Validate language code format"""
        if not code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} code cannot be empty"
            )
        
        # Whisper codes: 2-3 letters
        # NLLB codes: format like "eng_Latn"
        if not re.match(r'^[a-z]{2,3}(_[A-Za-z]{4})?$', code):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid {field_name} code format: {code}"
            )
        
        return code
    
    @staticmethod
    def validate_model_name(model: str) -> str:
        """Validate Whisper model name"""
        valid_models = {'tiny', 'base', 'small', 'medium', 'large', 'large-v2', 'large-v3'}
        
        if model not in valid_models:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid model '{model}'. Valid options: {', '.join(valid_models)}"
            )
        
        return model
    
    @staticmethod
    async def validate_audio_file(file: UploadFile) -> bytes:
        """
        Validate uploaded audio file
        Returns file bytes if valid
        """
        if not file:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file uploaded"
            )
        
        # 1. Validate filename
        filename = file.filename
        if not filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required"
            )
        
        if len(filename) > MAX_FILENAME_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Filename too long (max {MAX_FILENAME_LENGTH} characters)"
            )
        
        # 2. Check for path traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid filename: path traversal detected"
            )
        
        # 3. Check extension
        file_ext = Path(filename).suffix.lower()
        
        if file_ext in DANGEROUS_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Dangerous file extension: {file_ext}"
            )
        
        if file_ext not in ALLOWED_AUDIO_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid audio format. Allowed: {', '.join(ALLOWED_AUDIO_EXTENSIONS)}"
            )
        
        # 4. Read file content with size limit
        file_bytes = b""
        total_size = 0
        
        while chunk := await file.read(8192):  # Read in chunks
            total_size += len(chunk)
            
            if total_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB"
                )
            
            file_bytes += chunk
        
        if total_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )
        
        # 5. Validate MIME type using magic bytes
        try:
            mime = magic.from_buffer(file_bytes[:2048], mime=True)
            
            if mime not in ALLOWED_AUDIO_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type: {mime}. Expected audio file."
                )
        except Exception as e:
            # python-magic might not be installed
            # Fall back to extension-only validation
            pass
        
        return file_bytes
    
    @staticmethod
    def validate_file_path(path: str) -> Path:
        """
        Validate file path to prevent path traversal attacks
        """
        if not path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path cannot be empty"
            )
        
        try:
            path_obj = Path(path).resolve()
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid path format"
            )
        
        # Check for path traversal
        if '..' in path:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Path traversal detected"
            )
        
        # Ensure path exists
        if not path_obj.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Path not found: {path}"
            )
        
        return path_obj
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove path components
        filename = Path(filename).name
        
        # Remove dangerous characters
        filename = re.sub(r'[^\w\s.-]', '', filename)
        
        # Limit length
        if len(filename) > MAX_FILENAME_LENGTH:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            name = name[:MAX_FILENAME_LENGTH - len(ext) - 1]
            filename = f"{name}.{ext}" if ext else name
        
        return filename
    
    @staticmethod
    def validate_integer(value: int, min_val: int = None, max_val: int = None, field_name: str = "value") -> int:
        """Validate integer within range"""
        if not isinstance(value, int):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be an integer"
            )
        
        if min_val is not None and value < min_val:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be >= {min_val}"
            )
        
        if max_val is not None and value > max_val:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name} must be <= {max_val}"
            )
        
        return value


# Pydantic models with validation
class TranslationRequest(BaseModel):
    """Validated translation request"""
    text: str = Field(..., min_length=1, max_length=MAX_TEXT_LENGTH)
    source_language: str = Field(..., regex=r'^[a-z]{2,3}(_[A-Za-z]{4})?$')
    target_language: str = Field(..., regex=r'^[a-z]{2,3}(_[A-Za-z]{4})?$')
    
    @validator('text')
    def validate_text(cls, v):
        return InputValidator.validate_text(v, "text")
    
    @validator('source_language', 'target_language')
    def validate_language(cls, v, field):
        return InputValidator.validate_language_code(v, field.name)


class TranscriptionConfig(BaseModel):
    """Validated transcription configuration"""
    source_language: str = Field("ko", regex=r'^[a-z]{2,3}(_[A-Za-z]{4})?$')
    target_language: str = Field("eng_Latn", regex=r'^[a-z]{2,3}(_[A-Za-z]{4})?$')
    whisper_model: str = Field("base", regex=r'^(tiny|base|small|medium|large|large-v2|large-v3)$')
    use_vad: bool = Field(True)
    vad_aggressiveness: int = Field(3, ge=0, le=3)
    
    @validator('whisper_model')
    def validate_model(cls, v):
        return InputValidator.validate_model_name(v)


# Security headers middleware
class SecurityHeadersMiddleware:
    """Add security headers to responses"""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        async def send_with_security_headers(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                
                # Add security headers
                security_headers = [
                    (b"X-Content-Type-Options", b"nosniff"),
                    (b"X-Frame-Options", b"DENY"),
                    (b"X-XSS-Protection", b"1; mode=block"),
                    (b"Strict-Transport-Security", b"max-age=31536000; includeSubDomains"),
                    (b"Content-Security-Policy", b"default-src 'self'"),
                    (b"Referrer-Policy", b"strict-origin-when-cross-origin"),
                    (b"Permissions-Policy", b"geolocation=(), microphone=(), camera=()"),
                ]
                
                headers.extend(security_headers)
                message["headers"] = headers
            
            await send(message)
        
        await self.app(scope, receive, send_with_security_headers)


# Usage example:
"""
from security.input_validator import InputValidator, TranslationRequest

@app.post("/translate")
async def translate(request: TranslationRequest):
    # Request is already validated by Pydantic
    text = request.text
    # Process...
"""
