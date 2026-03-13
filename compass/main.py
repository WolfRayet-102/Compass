# main.py

import threading
import time
from listener import Listener
from brain import Brain
from speaker import Speaker

speaker  = Speaker()
brain    = Brain()
listener = Listener()

def on_voice_input(text: str):
    if not text or not text.strip():
        return
    print(f"[User said]: {text}")
    speaker.speak("Got it.", blocking=False)
    response = brain.process(text)
    print(f"[Compass]: {response}")
    speaker.speak(response)

def start():
    speaker.speak("Compass is ready. Say 'Hey Compass' followed by your request.")
    stop_listening = listener.start(callback=on_voice_input)
    return stop_listening

if __name__ == "__main__":
    stop_listening = start()
    print("Compass is running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down Compass...")
        speaker.speak("Goodbye! Compass is shutting down.")
        stop_listening()
        print("Done.")