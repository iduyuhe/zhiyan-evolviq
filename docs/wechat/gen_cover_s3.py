import math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 900, 500
ACCENT = (37, 99, 235)      # #2563eb
ACCENT_L = (96, 165, 250)   # #60a5fa
WHITE = (248, 250, 252)
MUTE = (148, 163, 184)
DARK1 = (15, 23, 42)        # #0f172a
DARK2 = (30, 41, 59)        # #1e293b

def font(path, size):
    return ImageFont.truetype(path, size)

FB = r"C:/Windows/Fonts/Noto Sans SC Bold (TrueType).otf"
FR = r"C:/Windows/Fonts/Noto Sans SC (TrueType).otf"

img = Image.new("RGB", (W, H), DARK1)
px = img.load()
# vertical gradient
for y in range(H):
    t = y / (H - 1)
    r = int(DARK1[0] + (DARK2[0] - DARK1[0]) * t)
    g = int(DARK1[1] + (DARK2[1] - DARK1[1]) * t)
    b = int(DARK1[2] + (DARK2[2] - DARK1[2]) * t)
    for x in range(W):
        px[x, y] = (r, g, b)

# radial blue glow top-right
glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
gd = ImageDraw.Draw(glow)
cx, cy = 720, 90
for radius in range(360, 0, -8):
    alpha = int(26 * (1 - radius / 360))
    gd.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(37, 99, 235, alpha))
glow = glow.filter(ImageFilter.GaussianBlur(40))
img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")

# faint grid
gd = ImageDraw.Draw(img, "RGBA")
grid = (37, 99, 235, 18)
for x in range(0, W, 45):
    gd.line([(x, 0), (x, H)], fill=grid, width=1)
for y in range(0, H, 45):
    gd.line([(0, y), (W, y)], fill=grid, width=1)

d = ImageDraw.Draw(img)

# kicker top-left
d.rectangle([60, 56, 78, 80], fill=ACCENT)
d.text((92, 54), "智衍 EvolvIQ · 工业智能体互联平台", font=font(FR, 20), fill=MUTE)

# main title
d.text((60, 120), "48小时双阶段收口", font=font(FB, 58), fill=WHITE)
d.text((62, 196), "越用越懂你的工业智能体", font=font(FB, 38), fill=ACCENT_L)

# subtitle line
d.text((62, 250), "S2 信任爬梯收口 · S3 智能推荐六层全交付", font=font(FR, 19), fill=MUTE)

# six-layer chain (S3-1..S3-6)
labels = ["行为基座", "相关性降噪", "源推荐", "采纳反哺", "行为导航", "共生环"]
n = len(labels)
x0, x1 = 60, 840
y = 330
chain_gap = (x1 - x0) / (n - 1)
# connecting line
d.line([(x0, y), (x1, y)], fill=(37, 99, 235, 120), width=2)
for i in range(n):
    cx = int(x0 + i * chain_gap)
    # node circle
    d.ellipse([cx - 13, y - 13, cx + 13, y + 13], fill=ACCENT)
    d.text((cx - 7, y - 11), str(i + 1), font=font(FB, 16), fill=WHITE)
    # label below
    d.text((cx - 44, y + 22), labels[i], font=font(FR, 16), fill=WHITE)

# bottom source line + tag
d.line([(60, 430), (840, 430)], fill=(37, 99, 235, 90), width=1)
d.text((60, 446), "工业5.0产业生态联盟", font=font(FR, 18), fill=MUTE)
# tag right
tag = "共生进化飞轮 · 已破 N=0"
tb = d.textbbox((0, 0), tag, font=font(FB, 17))
tw = tb[2] - tb[0]
d.rounded_rectangle([840 - tw - 28, 442, 840, 474], radius=14, fill=ACCENT)
d.text((840 - tw - 14, 446), tag, font=font(FB, 17), fill=WHITE)

img.save(r"E:/agent_industry/zhiyan/docs/wechat/cover_s3_dual_stage.jpg", "JPEG", quality=88)
print("saved cover, size:", img.size)
