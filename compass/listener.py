# listener.py

import pvporcupine
import pyaudio
import struct
import wave
import os
import tempfile
import threading
import speech_recognition as sr
from config import (
    WAKE_WORD,
    PORCUPINE_ACCESS_KEY,
    STT_ENGINE,
    AUDIO_DEVICE_INDEX
)


class Listener:

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.is_running = False
        self.thread     = None
        self.porcupine  = None
        self.audio      = None
        self.stream     = None

    def _setup_porcupine(self):
        self.porcupine = pvporcupine.create(
            access_key=PORCUPINE_ACCESS_KEY,
            keywords=[WAKE_WORD]
        )
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            rate=self.porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            input_device_index=AUDIO_DEVICE_INDEX,
            frames_per_buffer=self.porcupine.frame_length
        )

    def _wait_for_wake_word(self):
        print("[Compass]: Waiting for wake word...")
        while True:
            raw_audio = self.stream.read(
                self.porcupine.frame_length,
                exception_on_overflow=False
            )
            pcm_frame = struct.unpack_from(
                "h" * self.porcupine.frame_length,
                raw_audio
            )
            result = self.porcupine.process(pcm_frame)
            if result >= 0:
                print("[Compass]: Wake word detected!")
                return

    def _record_command(self, duration: int = 5) -> str:
        print("[Compass]: Recording command...")
        temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        temp_path = temp_file.name
        temp_file.close()

        frames_to_record = int(
            self.porcupine.sample_rate / self.porcupine.frame_length * duration
        )
        recorded_frames = []

        for _ in range(frames_to_record):
            raw_audio = self.stream.read(
                self.porcupine.frame_length,
                exception_on_overflow=False
            )
            recorded_frames.append(raw_audio)

        with wave.open(temp_path, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.audio.get_sample_size(pyaudio.paInt16))
            wf.setframerate(self.porcupine.sample_rate)
            wf.writeframes(b''.join(recorded_frames))

        return temp_path

    def _transcribe(self, audio_path: str) -> str:
        try:
            with sr.AudioFile(audio_path) as source:
                audio_data = self.recognizer.record(source)

            if STT_ENGINE == "whisper":
                text = self.recognizer.recognize_whisper(
                    audio_data,
                    model="base",
                    language="english"
                )
            elif STT_ENGINE == "google":
                text = self.recognizer.recognize_google(audio_data)
            else:
                raise ValueError(f"Unknown STT engine: {STT_ENGINE}")

            return text.strip()

        except sr.UnknownValueError:
            print("[Compass]: Could not understand audio.")
            return ""
        except sr.RequestError as e:
            print(f"[Compass]: STT service error: {e}")
            return ""
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def _listen_loop(self, callback):
        self._setup_porcupine()
        while self.is_running:
            self._wait_for_wake_word()
            if not self.is_running:
                break
            audio_path = self._record_command(duration=5)
            text = self._transcribe(audio_path)
            if text:
                callback(text)
        self._cleanup()

    def _cleanup(self):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.audio:
            self.audio.terminate()
        if self.porcupine:
            self.porcupine.delete()

    def start(self, callback) -> callable:
        self.is_running = True
        self.thread = threading.Thread(
            target=self._listen_loop,
            args=(callback,),
            daemon=True
        )
        self.thread.start()
        return self.stop

    def stop(self):
        self.is_running = False