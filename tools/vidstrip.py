"""Полоска из N кадров видео для быстрой проверки: python vidstrip.py in.mp4 out.jpg [N]"""
import sys, av
from PIL import Image
src, dst = sys.argv[1], sys.argv[2]
n = int(sys.argv[3]) if len(sys.argv) > 3 else 5
c = av.open(src)
frames = [f.to_image() for f in c.decode(video=0)]
st = c.streams.video[0]
has_audio = any(s.type == "audio" for s in c.streams)
picks = [frames[round(i * (len(frames) - 1) / (n - 1))] for i in range(n)]
h = 260
picks = [p.resize((int(p.width * h / p.height), h)) for p in picks]
out = Image.new("RGB", (sum(p.width for p in picks), h))
x = 0
for p in picks:
    out.paste(p, (x, 0)); x += p.width
out.save(dst, quality=80)
print(f"кадров {len(frames)}, {frames[0].size}, fps {float(st.average_rate):.0f}, звук: {has_audio}")
