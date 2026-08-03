import os, glob
import numpy as np
import soundfile as sf

RENDERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "renders")
track_names = ["KICK.wav", "SUB.wav", "BASS.wav", "growl.wav", "SNARE.wav",
               "snt2.wav", "HatsPercussion.wav", "Main LEAD.wav", "VOCALS.wav"]

sums = None
sr = None
for name in track_names:
    path = os.path.join(RENDERS, name)
    data, sr = sf.read(path, dtype="float32", always_2d=True)
    if sums is None:
        sums = np.zeros_like(data)
    n = min(len(data), len(sums))
    sums[:n] += data[:n]
    print(f"added {name}: {len(data)/sr:.2f}s")

# normalize to a sane peak (~-1 dBFS) so it is listenable, but do NOT master
peak = np.max(np.abs(sums)) if sums.size else 1.0
if peak > 0:
    sums = sums / peak * 0.89

out = os.path.join(RENDERS, "before_raw_mix.wav")
sf.write(out, sums, sr, subtype="PCM_24")
print(f"wrote {out}: {len(sums)/sr:.2f}s, peak_norm={peak:.3f}")
