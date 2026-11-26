# calendar + kid drawing textures for kitchen_set.py (needs PIL; run with normal python)
import os
HERE = os.path.dirname(os.path.abspath(__file__))
from PIL import Image, ImageDraw, ImageFont
cal = Image.new("RGB", (400, 560), (250, 248, 240)); d = ImageDraw.Draw(cal)
d.rectangle([0, 0, 400, 230], fill=(90, 150, 210)); d.ellipse([260, 40, 360, 140], fill=(255, 215, 60))
d.polygon([(0, 230), (130, 110), (260, 230)], fill=(60, 130, 70)); d.polygon([(150, 230), (280, 130), (400, 230)], fill=(40, 110, 60))
fnt = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 34); d.text((120, 245), "MARCH", font=fnt, fill=(40, 40, 50))
for r_ in range(5):
    for c_ in range(7):
        x0_, y0_ = 20 + c_ * 52, 300 + r_ * 50; d.rectangle([x0_, y0_, x0_ + 48, y0_ + 46], outline=(180, 180, 180))
        d.text((x0_ + 4, y0_ + 2), str(r_ * 7 + c_ + 1), font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 16), fill=(70, 70, 70))
d.ellipse([20 + 3 * 52 - 2, 300 + 2 * 50 - 2, 20 + 4 * 52, 300 + 3 * 50], outline=(220, 30, 30), width=4)
cal.save(os.path.join(HERE, 'tex', 'calendar.png'))
dr = Image.new("RGB", (300, 220), (255, 255, 255)); d = ImageDraw.Draw(dr)
d.ellipse([40, 60, 110, 130], outline=(230, 60, 40), width=6); d.line([(75, 130), (75, 190)], fill=(230, 60, 40), width=6)
d.ellipse([170, 40, 250, 120], outline=(40, 90, 220), width=6); d.line([(210, 120), (210, 200)], fill=(40, 90, 220), width=6)
d.ellipse([230, 10, 290, 60], fill=(255, 200, 0)); d.text((60, 195), "MOM + ME", fill=(30, 30, 30), font=ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 22))
dr.save(os.path.join(HERE, 'tex', 'drawing.png'))
print('ok')
