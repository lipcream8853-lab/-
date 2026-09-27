from PIL import Image, ImageOps, ImageEnhance, ImageFilter
# crops in display-fraction coords of oriented image: (left, top, width) ; height = width*1.25 in px
jobs = [
 ("white-monster-1","white-monster-1", (260/2000, 0/1500, 1200/2000)),
 ("white-monster-2","white-monster-2", (0, 40/2000, 1)),
 ("white-monster-3","white-monster-3", (0, 60/2000, 1)),
 ("anthurium-veitchii-1","anthurium-veitchii-1", (0, 60/2000, 1)),
 ("anthurium-veitchii-2","anthurium-veitchii-2", (444/1500, 0, 1056/1500)),
 ("monstera-mint-1","monstera-mint-1", (0, 60/2000, 1)),
 ("monstera-mint-2","monstera-mint-2", (420/1500, 700/2000, 1000/1500)),
 ("monstera-mint-1","monstera-mint-3", (560/1500, 700/2000, 640/1500)),
 ("monstera-bulbasaur-1","monstera-bulbasaur-1", (480/2000, 0, 1200/2000)),
 ("monstera-bulbasaur-2","monstera-bulbasaur-2", (140/1500, 350/2000, 1200/1500)),
 ("monstera-bulbasaur-1","monstera-bulbasaur-3", (1020/2000, 190/1500, 560/2000)),
]
for src,dst,(l,t,w) in jobs:
    im = ImageOps.exif_transpose(Image.open(f"images/{src}.jpg")).convert("RGB")
    W,H = im.size
    pw = w*W; ph = pw*1.25; pl = l*W; pt = t*H
    if pt+ph > H: pt = H-ph
    box = tuple(round(v) for v in (pl, pt, pl+pw, pt+ph))
    out = im.crop(box).resize((1080,1350), Image.LANCZOS)
    out = ImageOps.autocontrast(out, cutoff=0.5)
    out = ImageEnhance.Brightness(out).enhance(1.04)
    out = ImageEnhance.Color(out).enhance(1.08)
    out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    out.save(f"images/post/{dst}.jpg", quality=92)
    print(dst, box, (W,H))
# contact sheet
names=["white-monster-1","white-monster-2","white-monster-3","anthurium-veitchii-1","anthurium-veitchii-2",None,"monstera-mint-1","monstera-mint-2","monstera-mint-3","monstera-bulbasaur-1","monstera-bulbasaur-2","monstera-bulbasaur-3"]
sheet=Image.new("RGB",(3*360,4*450),"white")
for i,n in enumerate(names):
    if n: sheet.paste(Image.open(f"images/post/{n}.jpg").resize((360,450)),((i%3)*360,(i//3)*450))
sheet.save("/tmp/claude-0/-home-user--/fa015730-9753-5c5e-9626-715ba18375a3/scratchpad/sheet.jpg",quality=85)
