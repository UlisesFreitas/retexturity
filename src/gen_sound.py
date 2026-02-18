import wave
import math
import struct

def generate_beep(filename, duration=0.5, frequency=880, sample_rate=44100):
    n_samples = int(sample_rate * duration)
    with wave.open(filename, 'w') as obj:
        obj.setnchannels(1) # mono
        obj.setsampwidth(2) # 2 bytes
        obj.setframerate(sample_rate)
        
        for i in range(n_samples):
            value = int(32767.0 * math.sin(2.0 * math.pi * frequency * i / sample_rate))
            data = struct.pack('<h', value)
            obj.writeframesraw(data)

if __name__ == "__main__":
    generate_beep("c:/Users/ulise/OneDrive/Escritorio/retexturity/sounds/sound.wav")
