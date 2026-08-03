import numpy as np
import soundfile as sf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

R = r"C:\Users\highv\Documents\Default Project\ableton-auto-mix-mcp\renders"
data, sr = sf.read(R + r"\demo_before_after.wav", dtype="float32", always_2d=True)
mono = data.mean(axis=1)

# Layout: BEFORE(28.24s) + gap/beep(~2.3s) + AFTER(28.24s)
before_end = int(sr * 28.24)
after_start = before_end + int(sr * 2.3)

before = mono[:before_end]
after = mono[after_start:after_start + before_end]
N = min(len(before), len(after))
before, after = before[:N], after[:N]

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 5),
                               gridspec_kw={"hspace": 0.35})
fig.patch.set_facecolor("#0d1117")

t_b = np.linspace(0, N / sr, N)
t_a = np.linspace(0, N / sr, N)

ax1.fill_between(t_b, before, color="#8b949e", alpha=0.85)
ax1.set_title("BEFORE  — raw sum, no processing",
              color="#8b949e", loc="left", fontweight="bold", fontsize=13)
for s in ax1.spines.values():
    s.set_edgecolor("#30363d"); s.set_linewidth(1)
ax1.spines[["top", "right", "left"]].set_visible(False)
ax1.tick_params(colors="#888"); ax1.get_yaxis().set_visible(False)
ax1.set_facecolor("#0d1117")

ax2.fill_between(t_a, after, color="#2ea043", alpha=0.9)
ax2.set_title("AFTER — mastered (breaks style)", color="#2ea043",
              loc="left", fontweight="bold", fontsize=13)
for s in ax2.spines.values():
    s.set_edgecolor("#30363d"); s.set_linewidth(1)
ax2.spines[["top", "right", "left"]].set_visible(False)
ax2.tick_params(colors="#888"); ax2.get_yaxis().set_visible(False)
ax2.set_facecolor("#0d1117")

out = R + r"\demo_waveform.png"
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
print("wrote", out, "before_len", N, "samples =", round(N / sr, 2), "s")