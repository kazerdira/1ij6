#!/usr/bin/env python3
"""
Test Fixtures: Audio Samples
============================

Provides sample audio data for testing transcription endpoints.
"""

import numpy as np
from typing import Tuple


def generate_silence(duration_seconds: float = 1.0, sample_rate: int = 16000) -> np.ndarray:
    """
    Generate silence audio data
    
    Args:
        duration_seconds: Duration in seconds
        sample_rate: Sample rate (default 16kHz for Whisper)
    
    Returns:
        Numpy array of zeros
    """
    num_samples = int(duration_seconds * sample_rate)
    return np.zeros(num_samples, dtype=np.float32)


def generate_sine_wave(
    frequency: float = 440.0,
    duration_seconds: float = 1.0,
    sample_rate: int = 16000,
    amplitude: float = 0.5
) -> np.ndarray:
    """
    Generate a sine wave tone
    
    Args:
        frequency: Frequency in Hz (default 440 = A4 note)
        duration_seconds: Duration in seconds
        sample_rate: Sample rate
        amplitude: Wave amplitude (0.0 to 1.0)
    
    Returns:
        Numpy array of audio samples
    """
    num_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, num_samples, dtype=np.float32)
    return (amplitude * np.sin(2 * np.pi * frequency * t)).astype(np.float32)


def generate_white_noise(
    duration_seconds: float = 1.0,
    sample_rate: int = 16000,
    amplitude: float = 0.1
) -> np.ndarray:
    """
    Generate white noise
    
    Args:
        duration_seconds: Duration in seconds
        sample_rate: Sample rate
        amplitude: Noise amplitude
    
    Returns:
        Numpy array of random noise
    """
    num_samples = int(duration_seconds * sample_rate)
    return (amplitude * np.random.randn(num_samples)).astype(np.float32)


def generate_speech_like_audio(
    duration_seconds: float = 2.0,
    sample_rate: int = 16000
) -> np.ndarray:
    """
    Generate audio that resembles speech patterns (for testing)
    
    This creates a mix of frequencies that roughly mimics human speech
    frequency range (100-4000 Hz) with varying amplitude.
    
    Args:
        duration_seconds: Duration in seconds
        sample_rate: Sample rate
    
    Returns:
        Numpy array mimicking speech patterns
    """
    num_samples = int(duration_seconds * sample_rate)
    t = np.linspace(0, duration_seconds, num_samples, dtype=np.float32)
    
    # Mix of fundamental frequencies typical in speech
    audio = np.zeros(num_samples, dtype=np.float32)
    
    # Fundamental (100-300 Hz)
    audio += 0.3 * np.sin(2 * np.pi * 150 * t)
    
    # First formant (500-1000 Hz)
    audio += 0.2 * np.sin(2 * np.pi * 700 * t)
    
    # Second formant (1000-2500 Hz)
    audio += 0.15 * np.sin(2 * np.pi * 1500 * t)
    
    # Add amplitude modulation to simulate speech rhythm
    envelope = 0.5 + 0.5 * np.sin(2 * np.pi * 4 * t)  # ~4 Hz modulation
    audio *= envelope
    
    # Normalize
    max_val = np.abs(audio).max()
    if max_val > 0:
        audio = audio / max_val * 0.8
    
    return audio


def audio_to_bytes(audio: np.ndarray, sample_rate: int = 16000) -> bytes:
    """
    Convert numpy audio array to WAV bytes
    
    Args:
        audio: Audio numpy array
        sample_rate: Sample rate
    
    Returns:
        WAV file as bytes
    """
    import io
    import wave
    
    # Convert to 16-bit PCM
    audio_int16 = (audio * 32767).astype(np.int16)
    
    buffer = io.BytesIO()
    with wave.open(buffer, 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(audio_int16.tobytes())
    
    return buffer.getvalue()


# Pre-generated samples for quick access
SILENCE_1S = generate_silence(1.0)
SILENCE_5S = generate_silence(5.0)
TONE_440HZ = generate_sine_wave(440.0, 1.0)
WHITE_NOISE = generate_white_noise(1.0)
SPEECH_LIKE = generate_speech_like_audio(2.0)
