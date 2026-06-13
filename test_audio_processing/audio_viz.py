"""
WAV → STFT → Spectrogram
Usage: python stft_spectrogram.py <path_to_wav> [options]

Dependencies: pip install numpy scipy matplotlib
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from scipy.io import wavfile
from scipy.signal import stft, ShortTimeFFT, get_window

BANDS = [
    {"label": "110 Hz",  "centre": 110,  "low":  60,  "high": 160},
    {"label": "440 Hz",  "centre": 440,  "low": 390,  "high": 490},
    {"label": "1 kHz",   "centre": 1000, "low": 950,  "high": 1050},
    {"label": "4 kHz",   "centre": 4000, "low": 3950, "high": 4050},
]
 
BAND_WIDTH = 50  # ± Hz
 

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


def plot_spectrogram(
    freqs: np.ndarray,
    times: np.ndarray,
    Zxx: np.ndarray,
    title: str = "Spectrogram",
    db_range: float = 80.0,
    cmap: str = "inferno",
    output_path: str | None = None,
) -> None:
    """
    Plot a magnitude spectrogram (dB scale) from STFT output.

    Parameters
    ----------
    freqs      : frequency axis (Hz)
    times      : time axis (s)
    Zxx        : complex STFT matrix, shape (n_freqs, n_frames)
    title      : figure title
    db_range   : dynamic range shown; values below (peak - db_range) are clipped
    cmap       : matplotlib colormap
    output_path: if given, saves the figure to this path instead of showing it
    """
    # Magnitude → dB
    magnitude = np.abs(Zxx)
    magnitude_db = 20 * np.log10(magnitude + 1e-9)  # avoid log(0)

    # Clip to the desired dynamic range
    peak_db = magnitude_db.max()
    magnitude_db = np.clip(magnitude_db, peak_db - db_range, peak_db)

    fig, ax = plt.subplots(figsize=(12, 5))

    img = ax.pcolormesh(
        times,
        freqs,
        magnitude_db,
        shading="gouraud",
        cmap=cmap,
        vmin=peak_db - db_range,
        vmax=peak_db,
    )

    cbar = fig.colorbar(img, ax=ax, pad=0.02)
    cbar.set_label("Magnitude (dBFS)", rotation=270, labelpad=15)

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Frequency (Hz)")
    ax.set_title(title)
    ax.set_ylim(freqs[0], freqs[-1])

    plt.tight_layout()

    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved spectrogram to: {output_path}")
    else:
        plt.show()


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
        print(f"  {band['label']:>7}  ({band['low']}–{band['high']} Hz, "
              f"{n_bins} bins)  →  {dbfs:+.1f} dBFS")
 
    return results
 


def plot_band_chart(band_results: list[dict], wav_path: str, output_path: str | None = None):
    labels = [b["label"] for b in band_results]
    values = [b["dbfs"] for b in band_results]
    ranges = [f"{b['low']}–{b['high']} Hz" for b in band_results]
 
    # Colour-map bars by dBFS level (louder = brighter)
    norm = plt.Normalize(vmin=min(values) - 5, vmax=max(values) + 5)
    cmap = plt.cm.plasma
    colours = [cmap(norm(v)) for v in values]
 
    fig, ax = plt.subplots(figsize=(8, 5))
 
    bars = ax.bar(labels, values, color=colours, width=0.55,
                  edgecolor="white", linewidth=0.8, zorder=3)
 
    # Value labels above / below each bar
    for bar, val in zip(bars, values):
        offset = 0.8 if val >= 0 else -1.5
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            val + offset,
            f"{val:+.1f} dBFS",
            ha="center", va="bottom" if val >= 0 else "top",
            fontsize=10, fontweight="bold", color="white"
        )
 
    # Frequency range sub-labels on x-axis
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(
        [f"{lbl}\n{rng}" for lbl, rng in zip(labels, ranges)],
        fontsize=10
    )
 
    ax.set_ylabel("Average Level (dBFS)", fontsize=11)
    ax.set_title(f"Average dBFS by Frequency Band\n{wav_path}", fontsize=12)
 
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%+.0f"))
    ax.yaxis.grid(True, linestyle="--", alpha=0.4, zorder=0)
    ax.set_axisbelow(True)
 
    # Add a 0 dBFS reference line if the range spans it
    if min(values) < 0 < max(values) + 10:
        ax.axhline(0, color="white", linewidth=0.8, linestyle="--", alpha=0.5)
        ax.text(len(labels) - 0.42, 0.5, "0 dBFS", color="white",
                fontsize=8, alpha=0.6)
 
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")
    ax.tick_params(colors="white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_edgecolor("#444466")
 
    plt.tight_layout()
 
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        print(f"\nSaved chart to: {output_path}")
    else:
        plt.show()


# ── main ──────────────────────────────────────────────────────────────────────

def main(
        wav:str, 
        nperseg:int = 1024, 
        overlap: int = None, 
        window: str = "hann",  
        db_range:float = 80, 
        cmap: str = "inferno", 
        output:str=None,
        output_base:str = "test_results"):

    print(f"Loading: {wav}")
    sample_rate, samples = load_wav(wav)
    duration = len(samples) / sample_rate
    bin_width = sample_rate / nperseg

    print(f"  Sample rate : {sample_rate} Hz")
    print(f"  Duration    : {duration:.2f} s")
    print(f"  Samples     : {len(samples):,}")
    print(f"  Bin Width   : {bin_width}")
    print(f"\nComputing STFT  (nperseg={nperseg}, window={window})")

    freqs, times, Zxx = compute_stft(
        samples,
        sample_rate,
        window=window,
        nperseg=nperseg,
        noverlap=overlap,
    )
    print(f"  Frequency bins : {len(freqs)}")
    print(f"  Time frames    : {len(times)}")
    print(f"  Zxx shape      : {Zxx.shape}  (complex)")

    band_results = band_average_dbfs(freqs, Zxx, BANDS)

    title = f"Spectrogram — {wav}"

    if output is not None: 
        spec_chart_output = f"{output_base}/spectrogram_{output}"
    else:
        spec_chart_output = None
    
    plot_spectrogram(freqs, times, Zxx,
                     title=title,
                     db_range=db_range,
                     cmap=cmap,
                     output_path=spec_chart_output)
    
    if output is not None:
        bar_chart_output = f"{output_base}/band_{output}"
    else:
        bar_chart_output = None

    plot_band_chart(
        band_results, 
        wav, 
        output_path = bar_chart_output
    )


if __name__ == "__main__":
    file = "test_signals/Bongo_sound.wav"
    output = "bongo_test.png"

    # file = "test_signals/30_sec_test.wav"
    # output = "rpi_test.png"
    main(file, output = output)