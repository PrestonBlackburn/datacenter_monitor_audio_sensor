import numpy as np
from scipy.io import wavfile
import os

def generate_test_suite(fs=44100):
    if not os.path.exists('test_signals'):
        os.makedirs('test_signals')
    
    t_len = 2 # seconds
    t = np.linspace(0, t_len, int(fs * t_len), endpoint=False)
    
    # 1. Pure Tones (Frequency Accuracy)
    # 440Hz and 880Hz sine waves
    tone_data = 0.5 * (np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 880 * t))
    save_wav('test_signals/pure_tones.wav', fs, tone_data)
    
    # 2. Linear Chirp (Time-Frequency Linearity)
    # Sweeps from 100Hz to 5000Hz
    chirp_data = np.sin(2 * np.pi * (100 + (5000 - 100) * t / (2 * t_len)) * t)
    save_wav('test_signals/linear_chirp.wav', fs, chirp_data)
    
    # 3. Impulse (Temporal Resolution)
    # A single spike at 1 second
    impulse_data = np.zeros(len(t))
    impulse_data[int(len(t)/2)] = 1.0
    save_wav('test_signals/impulse.wav', fs, impulse_data)
    
    # 4. Tone Bursts (Windowing/Smoothing)
    # 1000Hz tone that turns on and off abruptly
    burst_data = np.sin(2 * np.pi * 1000 * t)
    burst_data[:int(0.5*fs)] = 0 # Silent first 0.5s
    burst_data[int(1.5*fs):] = 0 # Silent last 0.5s
    save_wav('test_signals/tone_burst.wav', fs, burst_data)

    print("Test suite generated in 'test_signals/' directory.")

def save_wav(filename, fs, data):
    # Normalize to 16-bit range
    scaled = np.int16(data / np.max(np.abs(data)) * 32767)
    wavfile.write(filename, fs, scaled)

if __name__ == "__main__":
    generate_test_suite()