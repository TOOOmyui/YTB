"""Génère 3 identités de chaîne : logo (800×800, lisible en cercle), bannière (2560×1440, zone sûre 1546×423) et planche de présentation."""
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ICI = os.path.dirname(os.path.abspath(__file__))
PO = os.path.join(ICI, 'polices')
INTER = '/usr/share/fonts/opentype/inter'


def F(nom, taille):
    chemins = {
        'bask': f'{PO}/libre-baskerville/files/libre-baskerville-latin-400-normal.woff',
        'bask-b': f'{PO}/libre-baskerville/files/libre-baskerville-latin-700-normal.woff',
        'frau': f'{PO}/fraunces/files/fraunces-latin-400-normal.woff',
        'frau-sb': f'{PO}/fraunces/files/fraunces-latin-600-normal.woff',
        'corm': f'{PO}/cormorant-garamond/files/cormorant-garamond-latin-600-normal.woff',
        'corm-b': f'{PO}/cormorant-garamond/files/cormorant-garamond-latin-700-normal.woff',
        'inter': f'{INTER}/Inter-Medium.otf', 'inter-sb': f'{INTER}/Inter-SemiBold.otf',
    }
    return ImageFont.truetype(chemins[nom], taille)


def centre_txt(d, cx, y, txt, pol, fill, espacement=0):
    if espacement:
        larg = sum(d.textlength(c, font=pol) for c in txt) + espacement * (len(txt) - 1)
        x = cx - larg / 2
        for c in txt:
            d.text((x, y), c, font=pol, fill=fill)
            x += d.textlength(c, font=pol) + espacement
        return
    bb = d.textbbox((0, 0), txt, font=pol)
    d.text((cx - (bb[2] - bb[0]) / 2 - bb[0], y), txt, font=pol, fill=fill)


IDENTITES = [
    dict(id='patrimoine-clair', nom='Patrimoine Clair', mono='PC', police='bask', police_b='bask-b',
         fond=(250, 247, 240), papier=(240, 232, 216), encre=(27, 36, 51), accent=(176, 132, 60),
         devise='La finance personnelle, textes et chiffres à l\'appui',
         esprit='Sobre et institutionnel, façon cabinet ou revue juridique. Le monogramme « PC » est encadré d\'un double filet, comme un sceau.'),
    dict(id='capital-lucide', nom='Capital Lucide', mono='CL', police='frau', police_b='frau-sb',
         fond=(252, 251, 248), papier=(236, 233, 226), encre=(22, 33, 30), accent=(36, 104, 84),
         devise='Comprendre avant d\'investir',
         esprit='Plus moderne et éditorial, façon magazine économique. Accent vert sapin, « l\'argent qui pousse » sans cliché.'),
    dict(id='epargne-decodee', nom='Épargne Décodée', mono='ÉD', police='corm', police_b='corm-b',
         fond=(247, 242, 233), papier=(232, 222, 204), encre=(40, 30, 24), accent=(150, 64, 44),
         devise='Ce que les textes disent vraiment de ton argent',
         esprit='Le plus chaleureux : beige papier, accent terre cuite, typographie Garamond de livre de droit. Met en avant l\'angle juriste.'),
]


def logo(idt, taille=800):
    img = Image.new('RGB', (taille, taille), idt['fond'])
    d = ImageDraw.Draw(img)
    c = taille / 2
    # disque papier (lisible une fois recadré en cercle par YouTube)
    r = taille * 0.46
    d.ellipse([c - r, c - r, c + r, c + r], fill=idt['papier'])
    # double filet
    for rr, w in ((r * 0.86, 6), (r * 0.80, 2)):
        d.ellipse([c - rr, c - rr, c + rr, c + rr], outline=idt['encre'], width=w)
    pol = F(idt['police_b'], int(taille * 0.30))
    bb = d.textbbox((0, 0), idt['mono'], font=pol)
    h = bb[3] - bb[1]
    centre_txt(d, c, c - h / 2 - bb[1] - taille * 0.025, idt['mono'], pol, idt['encre'])
    # petit filet d'accent sous le monogramme
    lw = taille * 0.09
    y = c + h / 2 + taille * 0.025
    d.rectangle([c - lw, y, c + lw, y + taille * 0.012], fill=idt['accent'])
    return img


def banniere(idt):
    W, H = 2560, 1440
    img = Image.new('RGB', (W, H), idt['fond'])
    d = ImageDraw.Draw(img)
    # bandes papier discrètes hors zone sûre
    d.rectangle([0, H * 0.5 + 300, W, H], fill=idt['papier'])
    d.rectangle([0, 0, W, H * 0.5 - 300], fill=idt['papier'])
    # zone sûre 1546×423 centrée
    lg = logo(idt, 300)
    masque = Image.new('L', (300, 300), 0)
    ImageDraw.Draw(masque).ellipse([0, 0, 299, 299], fill=255)
    x0 = W / 2 - 700
    img.paste(lg, (int(x0), int(H / 2 - 150)), masque)
    pol = F(idt['police_b'], 132)
    d.text((x0 + 360, H / 2 - 120), idt['nom'], font=pol, fill=idt['encre'])
    d.rectangle([x0 + 364, H / 2 + 52, x0 + 364 + 90, H / 2 + 58], fill=idt['accent'])
    d.text((x0 + 364, H / 2 + 80), idt['devise'], font=F('inter', 44), fill=tuple(int(v * 0.85 + 40) for v in idt['encre']))
    return img


def planche(idts, sortie):
    W, H = 2400, 1500
    img = Image.new('RGB', (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    col = W / 3
    for i, idt in enumerate(idts):
        x = i * col
        d.rectangle([x, 0, x + col, H], fill=idt['fond'])
        lg = logo(idt, 420)
        m = Image.new('L', (420, 420), 0)
        ImageDraw.Draw(m).ellipse([0, 0, 419, 419], fill=255)
        img.paste(lg, (int(x + col / 2 - 210), 120), m)
        centre_txt(d, x + col / 2, 600, idt['nom'], F(idt['police_b'], 76), idt['encre'])
        d.rectangle([x + col / 2 - 40, 712, x + col / 2 + 40, 717], fill=idt['accent'])
        pd = F('inter', 34)
        lignes, cur = [], ''
        for mot in idt['devise'].split():
            t = (cur + ' ' + mot).strip()
            if d.textlength(t, font=pd) > col - 140:
                lignes.append(cur); cur = mot
            else:
                cur = t
        lignes.append(cur)
        for k, l in enumerate(lignes):
            centre_txt(d, x + col / 2, 750 + k * 48, l, pd, idt['encre'])
        # aperçu de petite taille (comme dans les commentaires)
        for j, s in enumerate((96, 48)):
            p = logo(idt, s)
            mm = Image.new('L', (s, s), 0)
            ImageDraw.Draw(mm).ellipse([0, 0, s - 1, s - 1], fill=255)
            img.paste(p, (int(x + col / 2 - 90 + j * 130), 1000), mm)
        centre_txt(d, x + col / 2, 1120, 'Taille réelle dans YouTube', F('inter', 26), tuple(v // 2 + 90 for v in idt['encre']))
        centre_txt(d, x + col / 2, 1300, str(i + 1), F(idt['police_b'], 90), idt['accent'])
    img.save(sortie, quality=92)


if __name__ == '__main__':
    out = os.path.join(ICI, 'sorties')
    os.makedirs(out, exist_ok=True)
    for idt in IDENTITES:
        logo(idt).save(f"{out}/{idt['id']}-logo.png")
        banniere(idt).save(f"{out}/{idt['id']}-banniere.jpg", quality=92)
    planche(IDENTITES, f'{out}/planche-identites.jpg')
    print('ok')
