#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成智衍 EvolvIQ 体验二维码卡片（真实可扫二维码 + 品牌信息）。"""
import os
from PIL import Image, ImageDraw, ImageFont
import qrcode

OUT = r"E:\agent_industry\zhiyan\docs\智衍EvolvIQ_体验二维码卡.png"
FONT_DIR = r"C:\Windows\Fonts"
F_REG = os.path.join(FONT_DIR, "msyh.ttc")      # 微软雅黑
F_BOLD = os.path.join(FONT_DIR, "msyhbd.ttc")   # 微软雅黑粗体

# ---- 配色（与 PPT / 平台一致）----
DARK = (11, 37, 69)        # #0B2545 深蓝
NAVY = (19, 49, 92)        # #13315C
STEEL = (28, 78, 128)      # #1C4E80
TEAL = (46, 196, 182)      # #2EC4B6 青
ICE = (207, 227, 242)      # #CFE3F2 浅蓝灰
MUTED = (159, 179, 200)    # #9FB3C8 灰蓝
WHITE = (255, 255, 255)

W, H = 1080, 1440


def font(path, size, bold=False):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


f_brand = font(F_BOLD, 34)
f_title = font(F_BOLD, 56)
f_sub = font(F_REG, 30)
f_qr_cap = font(F_REG, 30)
f_url_lbl = font(F_BOLD, 26)
f_url = font(F_REG, 28)
f_acc_lbl = font(F_BOLD, 30)
f_acc = font(F_BOLD, 34)
f_note = font(F_REG, 24)
f_sign = font(F_REG, 26)

img = Image.new("RGB", (W, H), DARK)
d = ImageDraw.Draw(img)

# 顶部细青条装饰
d.rectangle([0, 0, W, 8], fill=TEAL)

# 品牌角标
d.text((W / 2, 78), "智衍 · 决策孪生  v1.0", font=f_brand, fill=TEAL, anchor="mm")

# 主标题
d.text((W / 2, 150), "扫码体验工业智能体平台", font=f_title, fill=WHITE, anchor="mm")

# 副标题
d.text((W / 2, 226), "全球首个开源 AI-Native 工业 Agent 平台", font=f_sub, fill=ICE, anchor="mm")

# ---- 白色卡片 ----
CARD_X, CARD_Y, CARD_W, CARD_H = 140, 300, 800, 720
d.rounded_rectangle([CARD_X, CARD_Y, CARD_X + CARD_W, CARD_Y + CARD_H], radius=40, fill=WHITE)

# ---- 二维码（真实可扫，品牌深蓝码）----
qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H,
                   box_size=10, border=4)
qr.add_data("http://43.153.172.52:3006")
qr.make(fit=True)
qr_img = qr.make_image(fill_color="#0B2545", back_color="white").convert("RGB")
# 缩放到 520x520
qr_img = qr_img.resize((520, 520), Image.LANCZOS)
qx = (W - 520) // 2
qy = CARD_Y + 60
img.paste(qr_img, (qx, qy))

# 二维码底部说明
d.text((W / 2, CARD_Y + CARD_H - 70), "微信 / 相机扫码 · 即开即用", font=f_qr_cap, fill=NAVY, anchor="mm")

# ---- 底部信息区 ----
y = 1075
# 体验网址
d.text((W / 2, y), "体验网址", font=f_url_lbl, fill=TEAL, anchor="mm")
d.text((W / 2, y + 38), "http://43.153.172.52:3006", font=f_url, fill=WHITE, anchor="mm")

y = 1180
# 体验账号
d.text((W / 2, y), "体验账号  demo      密码  EvolvIQ2026", font=f_acc, fill=WHITE, anchor="mm")

y = 1245
d.text((W / 2, y), "登录页已预填演示账号，进入即可体验 25 个工业智能分身", font=f_note, fill=MUTED, anchor="mm")

# 署名
d.text((W / 2, 1358), "杜玉河 · 工业5点0产业生态联盟", font=f_sign, fill=TEAL, anchor="mm")

# 底部青条（与顶部呼应）
d.rectangle([0, H - 8, W, H], fill=TEAL)

img.save(OUT, "PNG")
print("SAVED", OUT, img.size)
# 自检：确认二维码含非白像素（说明码真的画进去了）
px = list(qr_img.getdata())
dark = sum(1 for r, g, b in px if r < 128 and g < 128 and b < 128)
print("QR dark pixels:", dark, "(>0 means scannable pattern present)")
