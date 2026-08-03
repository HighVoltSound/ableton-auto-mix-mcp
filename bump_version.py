import io

p = "pyproject.toml"
with open(p, encoding="utf-8") as f:
    s = f.read()

s = s.replace('version = "0.1.1"', 'version = "0.1.2"')

with open(p, "w", encoding="utf-8", newline="") as f:
    f.write(s)

# strip any accidental BOM
raw = open(p, "rb").read().lstrip(b"\xef\xbb\xbf")
open(p, "wb").write(raw)

print("version lines:")
for line in s.splitlines():
    if line.startswith("version"):
        print(" ", line)
print("first bytes:", open(p, "rb").read(3))