# WAV -> STFT -> Frequency bands

import numpy as np
from scipy.io import wavfile
from scipy.signal import ShortTimeFFT, get_window
import time
import os
import meshtastic.serial_interface
from pubsub import pub
import time
from typing import Any
import json
import datetime
import subprocess
import threading


from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

MESH_DEVICE_ACTIVE = False
BANDS = [
    {"label": "110 Hz",  "centre": 110,  "low":  60,  "high": 160},
    {"label": "440 Hz",  "centre": 440,  "low": 390,  "high": 490},
    {"label": "1 kHz",   "centre": 1000, "low": 950,  "high": 1050},
    {"label": "4 kHz",   "centre": 4000, "low": 3950, "high": 4050},
]
 
BAND_WIDTH = 50  # ± Hz
 
TEST_CHANNEL_INDEX = 1
_TZ_NAME = time.tzname[time.localtime().tm_isdst > 0]
PRODUCER_DEVICE = '/dev/ttyACM0' #pico pi
CONSUMER_DEVICE = '/dev/ttyUSB1' #pico pi

# Recording for arecord
AUDIO_DEVICE = "plughw:1"
RECORD_DURATION = 60
SAMPLE_RATE = 16000
AUDIO_FORMAT = "S16_LE"
OUTPUT_DIR = "./temp_recordings"

# ----------------- Capture .wav files --------------------
_stop_event = threading.Event()

def record_loop(
    device: str = AUDIO_DEVICE,
    duration: int = RECORD_DURATION,
    sample_rate: int = SAMPLE_RATE,
    fmt: str = AUDIO_FORMAT,
    output_dir: str = OUTPUT_DIR,
) -> None:
    # Note! I think there could be gaps in the recording with this approach
    # need to investigate later
    print(f"[recorder] Starting continuous recording on {device} ...")
    while not _stop_event.is_set():
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(output_dir, f"recording_{timestamp}.wav")
        print(f"[recorder] Recording {filename} ...")
        try:
            subprocess.run(
                [
                    "arecord",
                    "-D", device,
                    "-c1",
                    "-r", str(sample_rate),
                    "-f", fmt,
                    "-d", str(duration),
                    filename,
                ],
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print(f"[recorder] arecord error (exit {exc.returncode}); retrying ...")
            time.sleep(1)
        except FileNotFoundError:
            _stop_event.wait(5)



# -------------- Processing for .wav files ----------------

def load_wav(path: str) -> tuple[int, np.ndarray]:
    """Load a WAV file and return (sample_rate, mono_float_samples)."""
    sample_rate, data = wavfile.read(path)

    # Convert to float32 in the range [-1, 1]
    if data.dtype == np.int16:
        data = data.astype(np.float32) / 32768.0
    elif data.dtype == np.int32:
        data = data.astype(np.float32) / 2147483648.0
    elif data.dtype == np.uint8:
        data = (data.astype(np.float32) - 128) / 128.0
    else:
        data = data.astype(np.float32)

    # Mix down to mono if stereo
    if data.ndim > 1:
        data = data.mean(axis=1)

    return sample_rate, data

def compute_stft(
    samples: np.ndarray,
    sample_rate: int,
    window: str = "hann",
    nperseg: int = 1024,
    noverlap: int | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    
    if noverlap is None:
        noverlap = nperseg // 2  # 50% overlap by default
    
    # window gets directly multiplied by the sample
    win = get_window(window, nperseg)
    hop = nperseg - noverlap

    SFT = ShortTimeFFT(
        win = win, 
        hop=hop, 
        fs= sample_rate,  
        scale_to='psd'
    )
    Zxx = SFT.stft(samples) # (n_freqs, n_frames)
    freqs = SFT.f # array of freq bins
    times = SFT.t(len(samples)) # n_frames
    return freqs, times, Zxx


def band_average_dbfs(freqs: np.ndarray, Zxx: np.ndarray, bands: list[dict]) -> list[dict]:
    """
    For each band, select STFT bins whose centre frequencies fall within
    [low, high], compute RMS magnitude across those bins and all time frames,
    then convert to dBFS.
 
    Returns the band dicts with an added 'dbfs' key.
    """
    results = []
    magnitude = np.abs(Zxx)  # shape: (n_freqs, n_frames)
 
    for band in bands:
        mask = (freqs >= band["low"]) & (freqs <= band["high"])
        n_bins = mask.sum()
 
        if n_bins == 0:
            raise ValueError(
                f"No STFT bins found in {band['low']}–{band['high']} Hz. "
                f"Try increasing nperseg for better frequency resolution."
            )
 
        # RMS across all selected frequency bins and all time frames
        band_mag = magnitude[mask, :]          # (n_bins, n_frames)
        rms = np.sqrt(np.mean(band_mag ** 2))
        dbfs = 20 * np.log10(rms + 1e-9)
 
        results.append({**band, "dbfs": dbfs, "n_bins": int(n_bins)})
        print(f"  {band['label']:>7}  ({band['low']}-{band['high']} Hz, "
              f"{n_bins} bins)  →  {dbfs:+.1f} dBFS")
 
    return results



def on_ack(packet: dict[str, Any], interface: Any) -> None:
    portnum = packet.get("decoded", {}).get("portnum")
    from_id = packet.get("fromId", "unknown")
    channel = packet.get("channel", 0)
    print(f"packet received: portnum={portnum} from={from_id} channel={channel}")

def send_message(device_name: str, message: str, channel_index: int = TEST_CHANNEL_INDEX) -> int:
    pub.subscribe(on_ack, "meshtastic.receive")
    iface = None
    try:
        iface = meshtastic.serial_interface.SerialInterface(device_name)
        iface.sendText(message, channelIndex=channel_index, wantAck=True)
        print(f"Queued on channel {channel_index}: {message}")
        time.sleep(10)  # stay open long enough to transmit and receive ACK
    except Exception as exc:
        print(f"Error: {exc}")
        return 1
    finally:
        if iface:
            iface.close()
    return 0
    

class AudioEventHandler(FileSystemEventHandler):
    def on_closed(self, event):
            if not event.is_directory and event.src_path.endswith(".wav"):
                print(f"Processing: {event.src_path}")
                
                # 1. Your processing logic here
                # process_audio(event.src_path)
                sample_rate, samples = load_wav(event.src_path)
                freqs, times, Zxx = compute_stft(
                    samples,
                    sample_rate,
                )
                band_results = band_average_dbfs(freqs, Zxx, BANDS)

                if MESH_DEVICE_ACTIVE:
                    time = [datetime.datetime.now().strftime("%Y-%m-%d %H:%M") for result in band_results]
                    hz = [result['centre'] for result in band_results]
                    dbfs = [result['dbfs'] for result in band_results]
                    message = [time, hz, dbfs]           
                    message_json = json.dumps(message, separators=(',', ':'))
                    # 2. Send summary logic (TODO)
                    send_message(
                        PRODUCER_DEVICE, 
                        message_json,
                    )
                    
                # 3. Clean up
                os.remove(event.src_path)
                print(f"Deleted: {event.src_path}")


if __name__ == "__main__":

    recorder_thread = threading.Thread(
        target=record_loop,
        kwargs={"output_dir": OUTPUT_DIR},
        daemon=True,
        name="audio-recorder",
    )
    recorder_thread.start()


    wav_files_path = OUTPUT_DIR
    event_handler = AudioEventHandler()
    observer = Observer()
    observer.schedule(event_handler, wav_files_path, recursive=True)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        _stop_event.set()
        observer.stop()
        observer.join()
        recorder_thread.join(timeout=5)