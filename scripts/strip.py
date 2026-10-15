# 审图逐帧条：把机构各状态的特写拼成一张带中文标注的图（G3 起每个机构样板交一张 SEQ-*.png）。
#   python3 scripts/strip.py spec.json
# spec.json：[{"src": "帧所在目录/", "out": "review/.../SEQ-x.png", "cols": 2, "width": 520, "items": [["帧文件名", "标注"], ...]}]
# 帧用 node src/figure/shots.mjs <临时目录> --pre "__arcseq.set(...)" 逐个截；字体用系统的文泉驿正黑。
import sys, json
from PIL import Image, ImageDraw, ImageFont
FONT = ImageFont.truetype('/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc', 15)
def strip(src, out_path, items, cols, width=520):
    ims=[]
    for f,label in items:
        im=Image.open(src+f).convert('RGB'); im=im.resize((width, round(im.height*width/im.width)), Image.LANCZOS); ims.append((im,label))
    h=ims[0][0].height; rows=(len(ims)+cols-1)//cols
    out=Image.new('RGB',(cols*width+(cols+1)*12, rows*(h+32)+12),(16,21,24)); d=ImageDraw.Draw(out)
    for i,(im,label) in enumerate(ims):
        x=12+(i%cols)*(width+12); y=12+(i//cols)*(h+32)
        d.text((x,y),label,fill=(160,176,182),font=FONT); out.paste(im,(x,y+22))
    out.save(out_path); print(out_path,out.size)
if __name__ == '__main__':
    spec = json.load(open(sys.argv[1]))
    for s in spec: strip(s['src'], s['out'], s['items'], s['cols'], s.get('width', 520))
