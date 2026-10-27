"""Agent Packaging — miniature 1280x720 lisible en petit.

Usage : python3 miniature.py sortie.jpg "GROS CHIFFRE" "Ligne 1" "Ligne 2" [ton]
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from PIL import Image, ImageDraw
from rendu import Toile, THEMES, P


def miniature(sortie, chiffre, l1, l2='', ton='accent', theme='finance'):
    W, H = 1280, 720
    t = Toile(W, H, THEMES[theme])
    img = t.nouvelle()
    d = ImageDraw.Draw(img)
    th = t.th
    c = th.get(ton, th['accent'])
    # bandeau d'accent à gauche
    d.rectangle([0, 0, 22, H], fill=c)
    # gros chiffre
    pol = P('bold', 300)
    while d.textlength(chiffre, font=pol) > W - 140 and pol.size > 80:
        pol = P('bold', pol.size - 10)
    d.text((70, 40), chiffre, font=pol, fill=c)
    y = 60 + pol.size + 20
    for i, l in enumerate([l1, l2]):
        if not l:
            continue
        p2 = P('bold', 86)
        while d.textlength(l, font=p2) > W - 140 and p2.size > 40:
            p2 = P('bold', p2.size - 4)
        # surlignage de la 2e ligne
        if i == 1:
            w = d.textlength(l, font=p2)
            d.rectangle([60, y - 6, 80 + w, y + p2.size + 14], fill=th['texte'])
            d.text((70, y), l, font=p2, fill=th['fond'])
        else:
            d.text((70, y), l, font=p2, fill=th['texte'])
        y += p2.size + 34
    img.convert('RGB').save(sortie, quality=92)
    return sortie


if __name__ == '__main__':
    a = sys.argv[1:]
    miniature(a[0], a[1], a[2], a[3] if len(a) > 3 else '', a[4] if len(a) > 4 else 'accent')
