"""Agent Packaging — miniature 1280×720 lisible en petit, aux couleurs de la chaîne.

Usage : python3 miniature.py sortie.jpg "GROS CHIFFRE" "Ligne 1" "Ligne 2" [ton] [marque] [pastille]
ton : negatif | positif | accent
"""
import os, sys
from PIL import Image, ImageDraw, ImageFont

ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
from rendu2 import P

# Charte Clear Assets (beige papier, encre bleu nuit, or)
CHARTE = dict(fond=(250, 247, 240), papier=(240, 232, 216), encre=(27, 36, 51), or_=(176, 132, 60),
              negatif=(196, 40, 52), positif=(18, 128, 86), accent=(176, 112, 20))


def serif(taille):
    for f in (os.path.join(ICI, '..', 'marque', 'polices', 'libre-baskerville-latin-700-normal.woff'),):
        if os.path.exists(f):
            return ImageFont.truetype(f, taille)
    return P('black', taille)


def miniature(sortie, chiffre, l1, l2='', ton='accent', theme=None, marque=None, pastille=None):
    W, H = 1280, 720
    c = CHARTE
    img = Image.new('RGBA', (W, H), c['fond'])
    d = ImageDraw.Draw(img)
    # bandeau papier à droite + filet or
    d.rectangle([0, 0, 28, H], fill=c[ton] if ton in c else c['accent'])
    # gros chiffre
    coul = c.get(ton, c['accent'])
    pol = P('black', 290)
    while d.textlength(chiffre, font=pol) > W - 150 and pol.size > 80:
        pol = P('black', pol.size - 10)
    d.text((76, 34), chiffre, font=pol, fill=coul)
    y = 60 + pol.size + 16
    for i, l in enumerate([l1, l2]):
        if not l:
            continue
        p2 = P('black', 84)
        while d.textlength(l, font=p2) > W - 160 and p2.size > 40:
            p2 = P('black', p2.size - 4)
        if i == 1:
            w = d.textlength(l, font=p2)
            d.rectangle([62, y - 8, 92 + w, y + p2.size + 16], fill=c['encre'])
            d.text((77, y), l, font=p2, fill=c['fond'])
        else:
            d.text((76, y), l, font=p2, fill=c['encre'])
        y += p2.size + 34
    if marque:
        pm = P('bold', 32)
        tw = d.textlength(marque.upper(), font=pm)
        x = W - 64
        if pastille and os.path.exists(pastille):
            p = Image.open(pastille).convert('RGBA').resize((72, 72))
            img.alpha_composite(p, (int(x - tw - 90), H - 112))
        d.text((x - tw, H - 96), marque.upper(), font=pm, fill=c['encre'])
        d.rectangle([x - tw, H - 50, x - tw + 60, H - 46], fill=c['or_'])
    img.convert('RGB').save(sortie, quality=92)
    return sortie


if __name__ == '__main__':
    a = sys.argv[1:]
    miniature(a[0], a[1], a[2], a[3] if len(a) > 3 else '', a[4] if len(a) > 4 else 'accent',
              marque=a[5] if len(a) > 5 else None, pastille=a[6] if len(a) > 6 else None)
