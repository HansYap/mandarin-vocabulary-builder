from faster_whisper import WhisperModel
import subprocess
import tempfile
import os

class ASRHandler:
    def __init__(self):
        # Use "base" for better mixed-language handling
        self.model = WhisperModel(
            "small",  # Sweet spot for speed + accuracy
            device="cuda",
            compute_type="int8",
            num_workers=4,
            cpu_threads=4
        )
        
        self.session_chunks = {}
        print("✅ faster-whisper initialized (base model, multilingual)")
        
    def add_chunk(self, session_id, webm_bytes):
        if session_id not in self.session_chunks:
            self.session_chunks[session_id] = []
        self.session_chunks[session_id].append(webm_bytes)
        
    def _convert_webm_to_wav(self, webm_bytes):
        """Convert WebM to high-quality WAV for Whisper"""
        try:
            process = subprocess.Popen(
                [
                    'ffmpeg',
                    '-hide_banner',
                    '-loglevel', 'error',
                    '-i', 'pipe:0',
                    '-f', 'wav',
                    '-acodec', 'pcm_s16le',  # ← Explicit codec
                    '-ac', '1',               # Mono
                    '-ar', '16000',           # 16kHz
                    '-af', 'highpass=f=200,lowpass=f=3000',  # ← Filter noise
                    'pipe:1'
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            wav_bytes, stderr = process.communicate(input=webm_bytes)
            
            if process.returncode != 0:
                print(f"❌ FFmpeg error: {stderr.decode()}")
                return None
            
            print(f"✅ FFmpeg conversion successful ({len(wav_bytes)} bytes)")
            return wav_bytes
            
        except Exception as e:
            print(f"❌ Conversion error: {e}")
            return None
    
    def transcribe_accumulated(self, session_id):
        """Transcribe with better error handling"""
        if session_id not in self.session_chunks or not self.session_chunks[session_id]:
            return ""
        
        temp_file = None
        try:
            # Combine chunks
            combined_webm = b''.join(self.session_chunks[session_id])
            print(f"📦 Combined {len(self.session_chunks[session_id])} chunks → {len(combined_webm)} bytes")
            
            # VALIDATION: Check if WebM is valid
            if len(combined_webm) < 1000:  # Too small
                print("⚠️ Audio too short, likely invalid")
                return ""
            
            # Save WebM for debugging
            # with open(f"debug_{session_id}.webm", "wb") as f:
            #     f.write(combined_webm)
            # print(f"💾 Saved debug audio: debug_{session_id}.webm")
            
            # Convert to WAV
            wav_bytes = self._convert_webm_to_wav(combined_webm)
            if wav_bytes is None or len(wav_bytes) < 100:
                print("❌ WAV conversion failed")
                return ""
            
            print(f"🎵 WAV size: {len(wav_bytes)} bytes")
            
            # Save WAV temporarily
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(wav_bytes)
                temp_path = temp_file.name
            
            print(f"⏳ Transcribing: {temp_path}")
            
            # Transcribe with detailed logging
            segments, info = self.model.transcribe(
                temp_path,
                language=None,
                beam_size=5,
                temperature=[0.0, 0.2, 0.4],  # Try multiple temperatures
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=300,  # More sensitive
                    speech_pad_ms=400
                ),
                condition_on_previous_text=False,
                initial_prompt="这是中文和English的混合语音。",
                word_timestamps=True  # ← Enable for debugging
            )
            
            # Collect segments with word-level detail
            all_text = []
            print("\n--- Transcription Segments ---")
            for segment in segments:
                print(f"[{segment.start:.2f}s - {segment.end:.2f}s] {segment.text}")
                all_text.append(segment.text)
            
            transcription = " ".join(all_text).strip()
            
            print(f"\n✅ Final: '{transcription}'")
            print(f"📊 Detected: {info.language} (confidence: {info.language_probability:.2f})")
            print(f"📊 Duration: {info.duration:.2f}s")
            
            # Clear chunks
            self.session_chunks[session_id] = []
            
            return transcription
            
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return ""
            
        finally:
            if temp_file and os.path.exists(temp_file.name):
                try:
                    os.unlink(temp_file.name)
                except:
                    pass
    
    def clear_session(self, session_id):
        if session_id in self.session_chunks:
            del self.session_chunks[session_id]