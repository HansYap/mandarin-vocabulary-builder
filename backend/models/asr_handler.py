from faster_whisper import WhisperModel
import subprocess
import tempfile
import os
import torch

class ASRHandler:
    def __init__(self):
        # Using large-v3-turbo for better mixed Mandarin/English recognition
        self.model = None
        self.last_use_time = None
        self.session_chunks = {}
        
        print("✅ ASR Handler initialized (lazy loading)")
    
    def _ensure_model_loaded(self):
        """Load model on first use"""
        if self.model is None:
            from faster_whisper import WhisperModel
            self.model = WhisperModel(
                "large-v3-turbo", 
                device="cuda",
                compute_type="float16", 
                num_workers=1
            )
            print("✅ Whisper loaded into VRAM")
        
        import time
        self.last_use_time = time.time()
      
    def add_chunk(self, session_id, webm_bytes):
        """Restored: Adds incoming audio chunks to the session buffer"""
        if session_id not in self.session_chunks:
            self.session_chunks[session_id] = []
        self.session_chunks[session_id].append(webm_bytes)
        
    def clear_session(self, session_id):
        """Restored: Cleans up memory for a specific session"""
        if session_id in self.session_chunks:
            del self.session_chunks[session_id]

    def _convert_webm_to_wav(self, webm_bytes):
        """Optimized: Removed lowpass/highpass filters to preserve English clarity"""
        try:
            process = subprocess.Popen(
                [
                    'ffmpeg', '-hide_banner', '-loglevel', 'error',
                    '-i', 'pipe:0', '-f', 'wav',
                    '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000',
                    'pipe:1'
                ],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            wav_bytes, stderr = process.communicate(input=webm_bytes)
            return wav_bytes if process.returncode == 0 else None
        except Exception as e:
            print(f"❌ FFmpeg conversion error: {e}")
            return None

    def transcribe_accumulated(self, session_id):
        self._ensure_model_loaded()
        
        if session_id not in self.session_chunks or not self.session_chunks[session_id]:
            return ""

        temp_path = None
        try:
            combined_webm = b''.join(self.session_chunks[session_id])
            wav_bytes = self._convert_webm_to_wav(combined_webm)
            
            if not wav_bytes:
                return ""

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(wav_bytes)
                temp_path = temp_file.name

            # Improved parameters for Code-Switching (Mandarin + English)
            segments, info = self.model.transcribe(
                temp_path,
                language="zh",  # Force Mandarin as base to prevent wrong language detection
                beam_size=5,
                initial_prompt="这是一段中文和English的混合语音。", # Helps model expect English nouns
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500)
            )

            all_text = [segment.text for segment in segments]
            transcription = "".join(all_text).strip()
            
            print(f"✅ Final Transcription: '{transcription}'")
            
            # Clear buffer after successful transcription
            self.session_chunks[session_id] = []
            return transcription

        except Exception as e:
            print(f"❌ Transcription error: {e}")
            return ""
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except:
                    pass

    def unload_model(self):
        """Call this when user ends session"""
        if self.model is not None:
            del self.model
            self.model = None
            torch.cuda.empty_cache()
            print("✅ Whisper unloaded from VRAM")