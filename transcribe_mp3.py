#!/usr/bin/env python3
"""
Standalone MP3 transcription tool using OpenAI Whisper
Reuses the existing whisper integration from the Discord bot
"""

import argparse
import os
import sys
import tempfile
import wave
from pathlib import Path

import openai
import speech_recognition as sr
from dotenv import load_dotenv
from pydub import AudioSegment

# Load environment variables
load_dotenv()

# Configuration from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TRANSCRIPTION_METHOD = os.getenv("TRANSCRIPTION_METHOD", "openai")
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
WHISPER_LANGUAGE = "en"

# Try importing local whisper components
try:
    import torch
    from faster_whisper import WhisperModel
    LOCAL_WHISPER_AVAILABLE = True
    WHISPER__PRECISION = "float32"
    DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    LOCAL_MODEL = "large-v3"
except ImportError:
    LOCAL_WHISPER_AVAILABLE = False


class MP3Transcriber:
    def __init__(self, transcription_method=None):
        self.transcription_method = transcription_method or TRANSCRIPTION_METHOD
        
        if self.transcription_method == "openai":
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not found in environment variables")
            self.client = openai.OpenAI(api_key=OPENAI_API_KEY)
        elif self.transcription_method == "local":
            if not LOCAL_WHISPER_AVAILABLE:
                raise ValueError("Local whisper dependencies not available. Install: faster-whisper torch")
            self.audio_model = WhisperModel(LOCAL_MODEL, device=DEVICE, compute_type=WHISPER__PRECISION)
        else:
            raise ValueError("Invalid transcription method. Use 'openai' or 'local'")

    def convert_mp4_to_mp3(self, mp4_path):
        """Convert MP4 file to MP3 format"""
        try:
            # Load MP4 file (extract audio)
            audio = AudioSegment.from_file(mp4_path, format="mp4")
            
            # Create temporary MP3 file
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_mp3:
                audio.export(temp_mp3.name, format="mp3")
                return temp_mp3.name
                
        except Exception as e:
            raise RuntimeError(f"Failed to convert MP4 to MP3: {e}")

    def convert_audio_to_wav(self, audio_path):
        """Convert audio file (MP3/MP4) to WAV format for transcription"""
        try:
            # Determine file format
            file_ext = Path(audio_path).suffix.lower()
            
            if file_ext == ".mp4":
                # Load MP4 file (extract audio)
                audio = AudioSegment.from_file(audio_path, format="mp4")
            elif file_ext == ".mp3":
                # Load MP3 file
                audio = AudioSegment.from_mp3(audio_path)
            else:
                # Try generic audio loading
                audio = AudioSegment.from_file(audio_path)
            
            # Convert to mono and set sample rate
            audio = audio.set_channels(1)
            audio = audio.set_frame_rate(16000)
            
            # Create temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                audio.export(temp_wav.name, format="wav")
                return temp_wav.name
                
        except Exception as e:
            raise RuntimeError(f"Failed to convert {audio_path} to WAV: {e}")

    def check_audio_length(self, wav_path):
        """Check audio file length"""
        try:
            with wave.open(wav_path, 'rb') as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                duration = frames / float(sample_rate)
                return duration
        except Exception:
            return 0

    def split_audio_file(self, wav_path, chunk_duration_ms=600000):  # 10 minutes
        """Split audio file into chunks for OpenAI API (25MB limit)"""
        audio = AudioSegment.from_wav(wav_path)
        chunks = []
        
        # Split into chunks with small overlap to avoid cutting words
        overlap_ms = 5000  # 5 seconds overlap
        start = 0
        
        while start < len(audio):
            end = min(start + chunk_duration_ms, len(audio))
            chunk = audio[start:end]
            
            # Create temporary file for chunk
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_chunk:
                chunk.export(temp_chunk.name, format="wav")
                chunks.append(temp_chunk.name)
            
            # Move start position (with overlap for continuity)
            start = end - overlap_ms
            if start >= len(audio) - overlap_ms:
                break
        
        return chunks

    def transcribe_openai(self, wav_path):
        """Transcribe using OpenAI API with chunking for large files"""
        # Check file size first
        file_size = os.path.getsize(wav_path)
        max_size = 24 * 1024 * 1024  # 24MB to be safe
        
        if file_size <= max_size:
            # File is small enough, transcribe directly
            with open(wav_path, "rb") as audio_file:
                transcription = self.client.audio.transcriptions.create(
                    file=audio_file,
                    model=WHISPER_MODEL,
                    language=WHISPER_LANGUAGE,
                )
                return transcription.text
        else:
            # File is too large, split into chunks
            print(f"File size ({file_size / (1024*1024):.1f}MB) exceeds OpenAI limit. Splitting into chunks...")
            chunks = self.split_audio_file(wav_path)
            transcripts = []
            
            try:
                for i, chunk_path in enumerate(chunks):
                    print(f"Transcribing chunk {i+1}/{len(chunks)}...")
                    with open(chunk_path, "rb") as audio_file:
                        transcription = self.client.audio.transcriptions.create(
                            file=audio_file,
                            model=WHISPER_MODEL,
                            language=WHISPER_LANGUAGE,
                        )
                        transcripts.append(transcription.text.strip())
                
                # Combine all transcripts
                return " ".join(transcripts)
            
            finally:
                # Clean up chunk files
                for chunk_path in chunks:
                    try:
                        os.unlink(chunk_path)
                    except OSError:
                        pass

    def transcribe_local(self, wav_path):
        """Transcribe using local faster-whisper"""
        segments, info = self.audio_model.transcribe(
            wav_path,
            language=WHISPER_LANGUAGE,
            beam_size=10,
            best_of=3,
            vad_filter=True,
            vad_parameters=dict(
                min_silence_duration_ms=150,
                threshold=0.8
            ),
            no_speech_threshold=0.6,
            initial_prompt="You are transcribing an audio file.",
        )
        
        # Combine all segments
        transcript_parts = []
        for segment in segments:
            transcript_parts.append(segment.text.strip())
        
        return " ".join(transcript_parts)

    def transcribe_audio(self, audio_path):
        """Main transcription method for MP3/MP4 files"""
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        file_ext = Path(audio_path).suffix.lower()
        print(f"Converting {file_ext.upper()} to WAV...")
        wav_path = self.convert_audio_to_wav(audio_path)
        
        try:
            # Check audio length
            duration = self.check_audio_length(wav_path)
            if duration <= 0.1:
                return "Audio file is too short or empty"
            
            print(f"Audio duration: {duration:.2f} seconds")
            print(f"Transcribing using {self.transcription_method} method...")
            
            # Transcribe based on method
            if self.transcription_method == "openai":
                transcript = self.transcribe_openai(wav_path)
            else:
                transcript = self.transcribe_local(wav_path)
            
            return transcript.strip()
            
        finally:
            # Clean up temporary WAV file
            try:
                os.unlink(wav_path)
            except OSError:
                pass


def main():
    parser = argparse.ArgumentParser(description="Transcribe MP3/MP4 files using OpenAI Whisper")
    parser.add_argument("audio_file", help="Path to the audio file to transcribe (MP3 or MP4)")
    parser.add_argument("-o", "--output", help="Output file path (optional, prints to console if not specified)")
    parser.add_argument("-m", "--method", choices=["openai", "local"], 
                       help="Transcription method (overrides environment variable)")
    parser.add_argument("--convert-only", action="store_true", 
                       help="Only convert MP4 to MP3 without transcribing")
    
    args = parser.parse_args()
    
    try:
        # Handle MP4 to MP3 conversion only
        if args.convert_only:
            if not args.audio_file.lower().endswith('.mp4'):
                print("Error: --convert-only requires an MP4 file", file=sys.stderr)
                sys.exit(1)
            
            transcriber = MP3Transcriber()
            mp3_path = transcriber.convert_mp4_to_mp3(args.audio_file)
            
            # Move to desired output location
            if args.output:
                import shutil
                shutil.move(mp3_path, args.output)
                print(f"MP4 converted to MP3: {args.output}")
            else:
                output_path = args.audio_file.replace('.mp4', '.mp3')
                import shutil
                shutil.move(mp3_path, output_path)
                print(f"MP4 converted to MP3: {output_path}")
            return
        
        # Initialize transcriber
        transcriber = MP3Transcriber(transcription_method=args.method)
        
        # Transcribe the file
        print(f"Transcribing: {args.audio_file}")
        transcript = transcriber.transcribe_audio(args.audio_file)
        
        # Output the transcript
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(transcript)
            print(f"Transcript saved to: {args.output}")
        else:
            print("\n" + "="*50)
            print("TRANSCRIPT:")
            print("="*50)
            print(transcript)
            print("="*50)
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()