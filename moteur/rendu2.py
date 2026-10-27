"""Agent Monteur — moteur visuel v2 (dynamique).

Principes : un plan par phrase, caméra toujours en mouvement, fond animé, transitions rapides,
sous-titres mot à mot, effets d'entrée appuyés sur les chiffres.

Chronologie (liste de « plans ») produite par produire2.py :
  {"debut": s, "duree": s, "visuel": {...}, "groupe": id, "t_groupe": s (début du groupe de plans
   partageant le même visuel), "d_groupe": s, "mots": [(t0, t1, "mot"), ...], "chapitre": str,
   "nouveau": bool (le visuel change à ce plan)}
"""
import math, os, re, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FPS = 30
W, H = 1920, 1080

THEMES = {
    # sombre (d'origine)
    'nuit': dict(clair=False, fond=(9, 12, 18), fond2=(18, 26, 40), texte=(244, 246, 249), muet=(140, 152, 172),
                 accent=(255, 190, 60), positif=(52, 226, 150), negatif=(255, 84, 96), info=(110, 160, 255),
                 grille=(255, 255, 255), ombre=(0, 0, 0), ombre_a=0.45, carte=(255, 255, 255), vignette=120,
                 nappes=((255, 190, 60, 34), (110, 160, 255, 40), (52, 226, 150, 22)),
                 st_texte=(255, 255, 255), st_contour=(0, 0, 0), pastille=(0, 0, 0, 120)),
    # blanc épuré
    'blanc': dict(clair=True, fond=(251, 251, 249), fond2=(240, 243, 247), texte=(16, 20, 28), muet=(104, 112, 126),
                  accent=(218, 134, 0), positif=(10, 150, 96), negatif=(214, 46, 60), info=(38, 98, 220),
                  grille=(16, 20, 28), ombre=(30, 40, 60), ombre_a=0.10, carte=(16, 20, 28), vignette=18,
                  nappes=((255, 196, 90, 46), (120, 170, 255, 40), (90, 220, 170, 26)),
                  st_texte=(16, 20, 28), st_contour=(255, 255, 255), pastille=(255, 255, 255, 210)),
    # beige papier
    'beige': dict(clair=True, fond=(246, 240, 229), fond2=(236, 227, 211), texte=(34, 27, 20), muet=(122, 108, 90),
                  accent=(196, 106, 18), positif=(30, 132, 86), negatif=(190, 50, 48), info=(48, 86, 168),
                  grille=(60, 44, 24), ombre=(80, 60, 30), ombre_a=0.12, carte=(60, 44, 24), vignette=24,
                  nappes=((236, 170, 90, 50), (200, 170, 120, 46), (150, 190, 160, 26)),
                  st_texte=(34, 27, 20), st_contour=(255, 252, 245), pastille=(255, 250, 240, 220)),
    # gris perle
    'gris': dict(clair=True, fond=(233, 236, 240), fond2=(218, 223, 230), texte=(18, 22, 30), muet=(96, 105, 120),
                 accent=(222, 136, 0), positif=(12, 146, 94), negatif=(208, 44, 58), info=(36, 92, 210),
                 grille=(18, 22, 30), ombre=(20, 30, 50), ombre_a=0.12, carte=(18, 22, 30), vignette=22,
                 nappes=((255, 200, 110, 40), (130, 165, 230, 46), (120, 200, 170, 24)),
                 st_texte=(18, 22, 30), st_contour=(255, 255, 255), pastille=(255, 255, 255, 200)),
}
THEMES['finance'] = THEMES['nuit']
ROTATION = ['blanc', 'nuit', 'beige', 'gris']


# ------------------------------------------------------------------ outils

_POL = {}


def P(poids, taille):
    k = (poids, int(taille))
    if k in _POL:
        return _POL[k]
    noms = {'regular': ['Inter-Regular.otf', 'inter-latin-400-normal.woff'],
            'semibold': ['Inter-SemiBold.otf', 'inter-latin-600-normal.woff'],
            'bold': ['Inter-Bold.otf', 'inter-latin-700-normal.woff', 'inter-latin-800-normal.woff'],
            'black': ['Inter-Black.otf', 'Inter-ExtraBold.otf', 'inter-latin-800-normal.woff']}[poids]
    for d in ['/usr/share/fonts/opentype/inter', os.path.join(os.path.dirname(__file__), 'polices')]:
        for n in noms:
            p = os.path.join(d, n)
            if os.path.exists(p):
                _POL[k] = ImageFont.truetype(p, int(taille))
                return _POL[k]
    _POL[k] = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', int(taille))
    return _POL[k]


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def e_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def e_in(x):
    x = clamp(x)
    return x ** 3


def e_back(x):
    x = clamp(x)
    c1 = 1.70158
    c3 = c1 + 1
    return 1 + c3 * (x - 1) ** 3 + c1 * (x - 1) ** 2


def rgba(c, a=1.0):
    return (c[0], c[1], c[2], int(255 * clamp(a)))


def apparait(t, debut, duree=0.4):
    """alpha, décalage vertical (px) d'un élément qui entre à `debut`."""
    a = e_out((t - debut) / duree)
    return a, (1 - a) * 46


def nombre_anime(valeur, a):
    m = re.search(r'[-−]?\d+(?:[ \u202f]\d{3})*(?:,\d+)?', valeur)
    if not m or a >= 1:
        return valeur
    brut = m.group(0)
    neg = brut.startswith(('-', '−'))
    s = re.sub(r'[\s ]', '', brut.lstrip('-−'))
    dec = len(s.split(',')[1]) if ',' in s else 0
    v = float(s.replace(',', '.')) * e_out(a)
    txt = f"{v:.{dec}f}".replace('.', ',') if dec else f"{int(round(v)):,}".replace(',', ' ')
    return valeur[:m.start()] + ('−' if neg else '') + txt + valeur[m.end():]


def couper(d, txt, pol, largeur):
    mots, lignes, cur = txt.split(), [], ''
    for m in mots:
        essai = (cur + ' ' + m).strip()
        if d.textlength(essai, font=pol) <= largeur or not cur:
            cur = essai
        else:
            lignes.append(cur)
            cur = m
    if cur:
        lignes.append(cur)
    return lignes


def centre(d, y, txt, pol, couleur, a=1.0, dy=0, x_centre=W / 2, ombre=True, th=None):
    bb = d.textbbox((0, 0), txt, font=pol)
    w = bb[2] - bb[0]
    x = x_centre - w / 2 - bb[0]
    if ombre and th is not None:
        d.text((x + 4, y + dy + 6), txt, font=pol, fill=rgba(th['ombre'], th.get('ombre_a', 0.45) * a))
    d.text((x, y + dy), txt, font=pol, fill=rgba(couleur, a))
    return bb[3] - bb[1]


# ------------------------------------------------------------------ fond animé

class Fond:
    """Dégradé + nappes lumineuses mobiles + grille qui défile (calculé en demi-résolution)."""

    def __init__(self, th, graine=3):
        self.th = th
        w, h = W // 2, H // 2
        self.w, self.h = w, h
        base = Image.new('RGB', (w, h), th['fond'])
        g = Image.new('L', (w, h), 0)
        ImageDraw.Draw(g).ellipse([-w * 0.2, -h * 0.6, w * 1.2, h * 0.9], fill=150 if th.get('clair') else 110)
        g = g.filter(ImageFilter.GaussianBlur(120))
        self.base = Image.composite(Image.new('RGB', (w, h), th['fond2']), base, g)
        rng = np.random.default_rng(graine)
        self.nappes = []
        for *c, al in th['nappes']:
            r = int(h * 0.8)
            s = Image.new('RGBA', (2 * r, 2 * r), (0, 0, 0, 0))
            ImageDraw.Draw(s).ellipse([r * 0.68, r * 0.68, r * 1.32, r * 1.32], fill=(*tuple(c), al))
            s = s.filter(ImageFilter.GaussianBlur(r * 0.2))
            self.nappes.append(dict(img=s, r=r, cx=rng.uniform(0.15, 0.85), cy=rng.uniform(0.15, 0.85),
                                    ax=rng.uniform(0.12, 0.25), ay=rng.uniform(0.10, 0.2),
                                    wx=rng.uniform(0.05, 0.11), wy=rng.uniform(0.04, 0.09), ph=rng.uniform(0, 6.28)))
        pas = 60
        self.pas = pas
        gr = Image.new('RGBA', (w + pas, h + pas), (0, 0, 0, 0))
        dg = ImageDraw.Draw(gr)
        for x in range(0, w + pas, pas):
            dg.line([x, 0, x, h + pas], fill=(*th['grille'], 9))
        for y in range(0, h + pas, pas):
            dg.line([0, y, w + pas, y], fill=(*th['grille'], 9))
        self.grille = gr
        # vignette
        v = Image.new('L', (w, h), 0)
        ImageDraw.Draw(v).ellipse([-w * 0.25, -h * 0.35, w * 1.25, h * 1.35], fill=255)
        v = v.filter(ImageFilter.GaussianBlur(90))
        self.vignette = Image.composite(Image.new('RGBA', (w, h), (0, 0, 0, 0)), Image.new('RGBA', (w, h), (0, 0, 0, th['vignette'])), v)

    def image(self, t):
        R = max(n['r'] for n in self.nappes) * 2
        if not hasattr(self, '_pad'):
            self._pad = Image.new('RGBA', (self.w + 2 * R, self.h + 2 * R), (0, 0, 0, 0))
            self._pad.paste(self.base.convert('RGBA'), (R, R))
            self._R = R
        img = self._pad.copy()
        for n in self.nappes:
            x = int(self.w * (n['cx'] + n['ax'] * math.sin(n['wx'] * t * 6.28 + n['ph'])) - n['r']) + R
            y = int(self.h * (n['cy'] + n['ay'] * math.cos(n['wy'] * t * 6.28 + n['ph'])) - n['r']) + R
            img.alpha_composite(n['img'], (max(0, x), max(0, y)))
        img = img.crop((R, R, R + self.w, R + self.h))
        off = int(t * 14) % self.pas
        img.alpha_composite(self.grille.crop((off, off, off + self.w, off + self.h)))
        img.alpha_composite(self.vignette)
        return img.convert('RGB').resize((W, H), Image.BILINEAR)


# ------------------------------------------------------------------ visuels (calque RGBA)

def dessiner(v, t, dur, th):
    """Dessine le visuel `v` au temps local `t` (depuis le début du groupe) sur un calque transparent."""
    img = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    typ = v['type']
    marge = 170
    T = lambda nom: th.get(nom, th['texte'])

    if typ == 'punch':
        lignes = v.get('lignes') or [v.get('texte', '')]
        coul = T(v.get('ton', 'texte'))
        k = e_back(t / 0.45)
        taille = v.get('taille', 170)
        pol = P('black', taille)
        while max(d.textlength(l, font=pol) for l in lignes) > W - 2 * marge and pol.size > 60:
            pol = P('black', pol.size - 8)
        hl = int(pol.size * 1.12)
        y0 = (H - hl * len(lignes)) / 2
        a = clamp(t / 0.12)
        for i, l in enumerate(lignes):
            c = T('accent') if v.get('accent') == i else coul
            centre(d, y0 + i * hl, l, pol, c, a, 0, th=th)
        if v.get('sous'):
            a2, dy2 = apparait(t, 0.35)
            centre(d, y0 + hl * len(lignes) + 30, v['sous'], P('semibold', 50), T('muet'), a2, dy2, th=th)
        img = _zoom_calque(img, 1.25 - 0.25 * k) if t < 0.45 else img
        return img

    if typ in ('titre', 'citation', 'section'):
        lignes = v.get('lignes') or [v.get('texte') or v.get('titre')]
        pol = P('black', 128) if typ == 'section' else P('bold', 74) if typ == 'citation' else P('black', 104)
        tout = []
        for i, l in enumerate(lignes):
            for sl in couper(d, l, pol, W - 2 * marge):
                tout.append((i, sl))
        hl = int(pol.size * 1.18)
        sous = v.get('sous') if typ == 'section' else None
        y0 = (H - hl * len(tout) - (90 if sous else 0)) / 2
        if typ == 'section':
            a, _ = apparait(t, 0, 0.3)
            lw = int(150 * e_out(t / 0.5))
            d.rounded_rectangle([W / 2 - lw, y0 - 60, W / 2 + lw, y0 - 48], radius=6, fill=rgba(T('accent'), a))
            if v.get('numero'):
                centre(d, y0 - 150, v['numero'], P('bold', 44), T('accent'), a, 0, th=th)
        for k_, (i, sl) in enumerate(tout):
            a, dy = apparait(t, 0.05 + 0.32 * i)
            c = T('accent') if v.get('accent') == i else T('texte')
            centre(d, y0 + k_ * hl, sl, pol, c, a, dy, th=th)
        if sous:
            a, dy = apparait(t, 0.45)
            centre(d, y0 + len(tout) * hl + 24, sous, P('semibold', 52), T('muet'), a, dy, th=th)
        return img

    if typ == 'chiffre':
        a = clamp(t / 0.15)
        k = e_back(t / 0.5)
        val = nombre_anime(v['valeur'], t / 1.1) if v.get('compteur', True) else v['valeur']
        coul = T(v.get('couleur', 'accent'))
        pol = P('black', 270)
        while d.textlength(v['valeur'], font=pol) > W - 2 * marge and pol.size > 80:
            pol = P('black', pol.size - 10)
        y = (H - pol.size) / 2 - 70
        # halo
        halo = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(halo)
        centre(hd, y, val, pol, coul, (0.3 if th.get('clair') else 0.55) * a, 0, ombre=False)
        halo = halo.filter(ImageFilter.GaussianBlur(28))
        img.alpha_composite(halo)
        d = ImageDraw.Draw(img)
        centre(d, y, val, pol, coul, a, 0, th=th)
        if v.get('label'):
            a2, dy2 = apparait(t, 0.5)
            for i, l in enumerate(couper(d, v['label'], P('semibold', 54), W - 2 * marge)):
                centre(d, y + pol.size + 70 + i * 68, l, P('semibold', 54), T('muet'), a2, dy2, th=th)
        if t < 0.5:
            img = _zoom_calque(img, 1.18 - 0.18 * k)
        return img

    if typ == 'ledger':
        lignes, tot, titre = v['lignes'], v.get('total'), v.get('titre')
        polL, polV = P('semibold', 60), P('bold', 62)
        besoin = max(d.textlength(l[0], font=polL) + d.textlength(l[1], font=polV) for l in lignes) + 120
        x0 = min(W * 0.2, (W - besoin) / 2)
        x1 = W - x0
        pas = 104
        n = len(lignes) + (1 if tot else 0)
        y = (H - n * pas - (120 if titre else 0)) / 2
        # carte
        a, _ = apparait(t, 0, 0.3)
        d.rounded_rectangle([x0 - 60, y - 50, x1 + 60, y + n * pas + (120 if titre else 0) + 30], radius=28,
                            fill=(*th['carte'], int(14 * a)), outline=(*th['carte'], int(30 * a)), width=2)
        if titre:
            a, dy = apparait(t, 0)
            centre(d, y, titre, P('semibold', 50), T('muet'), a, dy, th=th)
            y += 120
        esp = clamp((dur * 0.55) / max(1, n), 0.45, 1.6)
        for i, l in enumerate(lignes):
            a, dy = apparait(t, 0.25 + i * esp)
            cv = T(l[2]) if len(l) > 2 else T('texte')
            d.text((x0, y + dy), l[0], font=polL, fill=rgba(T('texte'), a))
            val = nombre_anime(l[1], (t - 0.25 - i * esp) / 0.8)
            wv = d.textlength(val, font=polV)
            d.text((x1 - wv, y + dy), val, font=polV, fill=rgba(cv, a))
            y += pas
        if tot:
            deb = 0.25 + len(lignes) * esp
            a, dy = apparait(t, deb)
            d.rectangle([x0, y - 24, x0 + (x1 - x0) * e_out((t - deb) / 0.5), y - 19], fill=rgba(T('muet'), a))
            d.text((x0, y + dy), tot[0], font=P('black', 68), fill=rgba(T('texte'), a))
            val = nombre_anime(tot[1], (t - deb) / 0.9)
            pv = P('black', 78)
            wv = d.textlength(val, font=pv)
            d.text((x1 - wv, y + dy - 6), val, font=pv, fill=rgba(T(tot[2] if len(tot) > 2 else 'accent'), a))
        return img

    if typ == 'barres':
        items, titre = v['items'], v.get('titre')
        maxv = max(it[1] for it in items)
        polL, polV = P('bold', 52), P('black', 60)
        lab_w = max(d.textlength(it[0], font=polL) for it in items)
        val_w = max(d.textlength(it[2], font=polV) for it in items)
        x0 = max(W * 0.26, marge + lab_w + 40)
        xl = W - marge - val_w - 30
        pas = 160
        y = (H - len(items) * pas) / 2 + (50 if titre else 0)
        if titre:
            a, dy = apparait(t, 0)
            centre(d, y - 120, titre, P('semibold', 52), T('muet'), a, dy, th=th)
        esp = clamp((dur * 0.5) / len(items), 0.4, 1.4)
        for i, it in enumerate(items):
            deb = 0.25 + i * esp
            a, dy = apparait(t, deb)
            g = e_out((t - deb) / 0.9)
            ton = it[3] if len(it) > 3 else 'accent'
            c = T(ton)
            lw = d.textlength(it[0], font=polL)
            d.text((x0 - 40 - lw, y + 24 + dy), it[0], font=polL, fill=rgba(T('texte'), a))
            d.rounded_rectangle([x0, y + 10, xl, y + 100], radius=16, fill=(*th['carte'], int(12 * a)))
            lg = (xl - x0) * it[1] / maxv * g
            if lg > 4:
                d.rounded_rectangle([x0, y + 10, x0 + lg, y + 100], radius=16, fill=rgba(c, a))
            d.text((x0 + lg + 26, y + 16), nombre_anime(it[2], g), font=polV, fill=rgba(T('texte'), a))
            y += pas
        return img

    if typ == 'liste':
        items, titre = v['items'], v.get('titre')
        pol = P('semibold', 58)
        x0 = W * 0.16
        blocs = [couper(d, it, pol, W * 0.64) for it in items]
        htot = sum(len(b) * 74 + 54 for b in blocs) + (140 if titre else 0)
        y = (H - htot) / 2
        if titre:
            a, dy = apparait(t, 0)
            centre(d, y, titre, P('black', 76), T('texte'), a, dy, th=th)
            y += 140
        actif = v.get('actif')  # index de l'élément mis en avant (plans successifs)
        esp = clamp((dur * 0.7) / len(items), 0.5, 3.0) if actif is None else 0.0
        for i, b in enumerate(blocs):
            deb = 0.25 + i * esp if actif is None else (0.1 if i <= actif else 99)
            a, dy = apparait(t, deb)
            if actif is not None and i < actif:
                a *= 0.45
            r = 42
            cx, cy = x0 + r, y + 38 + dy
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=rgba(T('accent'), a))
            num = str(i + 1)
            nw = d.textlength(num, font=P('black', 46))
            d.text((cx - nw / 2, cy - 30), num, font=P('black', 46), fill=rgba(th['fond'], a))
            for k_, l in enumerate(b):
                d.text((x0 + 124, y + k_ * 74 + dy), l, font=pol, fill=rgba(T('texte'), a))
            y += len(b) * 74 + 54
        return img

    if typ == 'equation':
        termes = v['termes']
        polv, poll = P('black', 118), P('semibold', 40)
        larg = [max(d.textlength(tm[0], font=polv), d.textlength(tm[1], font=poll) if len(tm) > 1 else 0) for tm in termes]
        gap = 54
        x = (W - sum(larg) - gap * (len(termes) - 1)) / 2
        y = H / 2 - 100
        esp = clamp(dur * 0.5 / len(termes), 0.35, 1.0)
        for i, tm in enumerate(termes):
            deb = 0.2 + i * esp
            a, dy = apparait(t, deb)
            ton = tm[2] if len(tm) > 2 else ('muet' if len(tm) == 1 else 'texte')
            sc = 1.0
            w = d.textlength(tm[0], font=polv)
            d.text((x + (larg[i] - w) / 2 + 4, y + dy + 6), tm[0], font=polv, fill=rgba(th['ombre'], th.get('ombre_a', 0.4) * a))
            d.text((x + (larg[i] - w) / 2, y + dy), tm[0], font=polv, fill=rgba(T(ton), a))
            if len(tm) > 1 and tm[1]:
                wl = d.textlength(tm[1], font=poll)
                d.text((x + (larg[i] - wl) / 2, y + 160 + dy), tm[1], font=poll, fill=rgba(T('muet'), a))
            x += larg[i] + gap
        return img

    if typ == 'comparatif':
        cols = v['colonnes']
        n = len(cols)
        lw = (W - 2 * marge - 70 * (n - 1)) / n
        for i, col in enumerate(cols):
            deb = 0.1 + i * 0.6
            a, dy = apparait(t, deb, 0.45)
            dx = (1 - e_out((t - deb) / 0.45)) * (-120 if i == 0 else 120)
            x = marge + i * (lw + 70) + dx
            c = T(col.get('ton', 'accent'))
            y0 = H * 0.2
            d.rounded_rectangle([x, y0 + dy, x + lw, H * 0.8 + dy], radius=32, fill=(*c, int(22 * a)),
                                outline=rgba(c, a), width=5)
            pt = P('black', 70)
            tw = d.textlength(col['titre'], font=pt)
            d.text((x + (lw - tw) / 2, y0 + 56 + dy), col['titre'], font=pt, fill=rgba(c, a))
            yy = y0 + 190
            for j, l in enumerate(col['lignes']):
                a2, dy2 = apparait(t, deb + 0.25 + 0.2 * j)
                for sl in couper(d, l, P('bold', 50), lw - 80):
                    sw = d.textlength(sl, font=P('bold', 50))
                    d.text((x + (lw - sw) / 2, yy + dy + dy2), sl, font=P('bold', 50), fill=rgba(T('texte'), a2))
                    yy += 68
                yy += 22
        return img

    if typ == 'courbe':
        series, titre = v['series'], v.get('titre')
        gx0, gx1, gy0, gy1 = W * 0.1, W * 0.7, H * 0.31, H * 0.8
        maxv = max(max(s['points']) for s in series)
        rang = sorted(range(len(series)), key=lambda k: -series[k]['points'][-1])
        if titre:
            a, dy = apparait(t, 0)
            centre(d, H * 0.19, titre, P('semibold', 48), T('muet'), a, dy, th=th)
        for k in range(5):
            yy = gy1 - (gy1 - gy0) * k / 4
            d.line([gx0, yy, gx1, yy], fill=(*th['carte'], 26), width=2)
        for k, lab in enumerate(v.get('axe_x', [])):
            xx = gx0 + (gx1 - gx0) * k / (len(v['axe_x']) - 1)
            lw = d.textlength(lab, font=P('semibold', 36))
            d.text((xx - lw / 2, gy1 + 22), lab, font=P('semibold', 36), fill=rgba(T('muet')))
        etiq_y = {}
        for i in rang:  # la série la plus basse est dessinée en dernier, donc visible au-dessus
            s = series[i]
            deb = 0.3 + i * 0.6
            dt = max(1.6, dur * 0.35)
            g = e_out((t - deb) / dt)
            pts = s['points']
            n = len(pts)
            # interpolation fine pour une courbe qui se trace en continu
            fine = []
            for j in range(41):
                u = j / 40 * (n - 1)
                k0 = min(int(u), n - 2)
                fr = u - k0
                val = pts[k0] + (pts[k0 + 1] - pts[k0]) * fr
                fine.append((gx0 + (gx1 - gx0) * u / (n - 1), gy1 - (gy1 - gy0) * val / maxv))
            m = max(2, int(len(fine) * g))
            c = T(s.get('ton', 'accent'))
            if g > 0:
                poly = fine[:m] + [(fine[m - 1][0], gy1), (fine[0][0], gy1)]
                d.polygon(poly, fill=(*c, 26))
                d.line(fine[:m], fill=rgba(c), width=10 if rang.index(i) else 8, joint='curve')
                xe, ye = fine[m - 1]
                d.ellipse([xe - 13, ye - 13, xe + 13, ye + 13], fill=rgba(c))
            if g >= 1:
                a, _ = apparait(t, deb + dt)
                xe, ye = fine[-1]
                yl = ye - 50
                for autre in etiq_y.values():
                    if abs(yl - autre) < 112:
                        yl = autre + 112
                etiq_y[i] = yl
                d.text((xe + 34, yl), s['nom'], font=P('semibold', 38), fill=rgba(T('muet'), a))
                d.text((xe + 34, yl + 44), s.get('fin', ''), font=P('black', 56), fill=rgba(c, a))
        return img

    raise ValueError('type de visuel inconnu : ' + typ)


def _zoom_calque(img, s):
    if abs(s - 1) < 0.002:
        return img
    a = 1 / s
    return img.transform((W, H), Image.AFFINE, (a, 0, W / 2 - W / 2 * a, 0, a, H / 2 - H / 2 * a), resample=Image.BILINEAR)


# ------------------------------------------------------------------ sous-titres

def segments_mots(mots, max_mots=3, max_car=22):
    """Regroupe les mots en segments affichés ensemble."""
    segs, cur = [], []
    for m in mots:
        txt = ' '.join(x[2] for x in cur + [m])
        if cur and (len(cur) >= max_mots or len(txt) > max_car or cur[-1][2][-1:] in '.,:;?!'):
            segs.append(cur)
            cur = []
        cur.append(m)
    if cur:
        segs.append(cur)
    return segs


def dessiner_sous_titres(calque, segs, t, th):
    seg = None
    for i, s in enumerate(segs):
        fin = segs[i + 1][0][0] if i + 1 < len(segs) else s[-1][1] + 0.3
        if s[0][0] - 0.02 <= t < fin:
            seg = s
            break
    if not seg:
        return
    d = ImageDraw.Draw(calque)
    pol = P('black', 66)
    mots = [m[2] for m in seg]
    largeurs = [d.textlength(m, font=pol) for m in mots]
    esp = d.textlength(' ', font=pol)
    tot = sum(largeurs) + esp * (len(mots) - 1)
    k = e_back((t - seg[0][0]) / 0.18)
    y = H * 0.835 + (1 - k) * 18
    x = (W - tot) / 2
    for (t0, t1, m), w in zip(seg, largeurs):
        actif = t0 <= t < t1 + 0.05
        c = th['accent'] if actif else th['st_texte']
        d.text((x, y), m, font=pol, fill=rgba(c), stroke_width=7, stroke_fill=rgba(th['st_contour'], 0.95))
        x += w + esp


# ------------------------------------------------------------------ composition d'une image

class Compositeur:
    def __init__(self, plans, theme='finance', sous_titres=True):
        self.th = THEMES[theme]
        self.theme_defaut = theme
        self.fonds = {}
        self.plans = plans
        self.sous_titres = sous_titres
        self._cache = {}
        self.segs = [segments_mots(p.get('mots', [])) for p in plans]
        self.premier = {}
        for k, p in enumerate(plans):
            self.premier.setdefault(p['groupe'], k)

    def fond_de(self, nom):
        if nom not in self.fonds:
            self.fonds[nom] = Fond(THEMES[nom])
        return self.fonds[nom]

    def calque_visuel(self, i, tg):
        p = self.plans[i]
        th = THEMES[p.get('theme', self.theme_defaut)]
        fin_anim = min(p['d_groupe'], 0.75 * p['d_groupe'] + 1.6)
        cle = (p['groupe'], 'fixe')
        if tg > fin_anim + 0.05:
            if cle not in self._cache:
                self._cache = {cle: dessiner(p['visuel'], fin_anim + 0.05, p['d_groupe'], th)}
            return self._cache[cle]
        return dessiner(p['visuel'], tg, p['d_groupe'], th)

    def image(self, i, tl, t_abs):
        """Plan i, temps local tl dans le plan, temps absolu t_abs."""
        p = self.plans[i]
        tg = p['debut'] - p['t_groupe'] + tl
        nom = p.get('theme', self.theme_defaut)
        th = THEMES[nom]
        fond = self.fond_de(nom).image(t_abs)
        prec = self.plans[i - 1].get('theme', self.theme_defaut) if i > 0 else nom
        if prec != nom and tl < 0.35:
            fond = Image.blend(self.fond_de(prec).image(t_abs), fond, e_out(tl / 0.35))
        calque = self.calque_visuel(i, tg)
        # caméra : poussée lente sur le groupe + coup de zoom à chaque nouveau plan
        u = tg / max(0.1, p['d_groupe'])
        # cadrages successifs (effet multi-caméra) à chaque phrase d'un même visuel
        rang = i - self.premier[p['groupe']]
        CAD = [(1.0, 0), (1.06, -36), (0.975, 28), (1.035, 18)]
        z1, x1 = CAD[rang % 4]
        if rang > 0 and tl < 0.2:
            z0, x0 = CAD[(rang - 1) % 4]
            k = e_out(tl / 0.2)
            z1, x1 = z0 + (z1 - z0) * k, x0 + (x1 - x0) * k
        s = 0.94 * (1 + 0.035 * u) * z1
        dx = float(x1)
        ent = 0.24
        if p['nouveau'] and tg < ent:
            dx += (1 - e_out(tg / ent)) * W * 0.10
        fin_groupe = p['t_groupe'] + p['d_groupe']
        reste = fin_groupe - (p['debut'] + tl)
        sortie = 0.16
        alpha = 1.0
        if reste < sortie:
            dx += -e_in(1 - reste / sortie) * W * 0.10
            alpha = clamp(reste / sortie)
        cy = H * 0.45 - (0 if not self.sous_titres else 10)
        a = 1 / s
        c = W / 2 - (W / 2 + dx) * a
        f = H / 2 - cy * a
        cal = calque.transform((W, H), Image.AFFINE, (a, 0, c, 0, a, f), resample=Image.BILINEAR)
        if alpha < 1:
            al = cal.getchannel('A').point(lambda v: int(v * alpha))
            cal.putalpha(al)
        img = fond.convert('RGBA')
        img.alpha_composite(cal)
        # étiquette de chapitre
        if p.get('chapitre'):
            d = ImageDraw.Draw(img)
            txt = p['chapitre'].upper()
            pol = P('bold', 28)
            tw = d.textlength(txt, font=pol)
            d.rounded_rectangle([60, 54, 60 + tw + 64, 106], radius=26, fill=th['pastille'], outline=(*th['carte'], 40), width=2)
            d.ellipse([80, 72, 96, 88], fill=rgba(th['accent']))
            d.text((110, 62), txt, font=pol, fill=rgba(th['texte'], 0.92))
        if self.sous_titres and self.segs[i] and not p['visuel'].get('_texte'):
            dessiner_sous_titres(img, self.segs[i], tl, th)
        return img.convert('RGB')


def rendre_segment(plans, indices, t_depart, sortie, theme='finance', sous_titres=True):
    comp = Compositeur(plans, theme, sous_titres)
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '19', '-pix_fmt', 'yuv420p', sortie]
    pr = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in indices:
        p = plans[i]
        nf = int(round((p['debut'] + p['duree']) * FPS)) - int(round(p['debut'] * FPS))
        for f in range(nf):
            tl = f / FPS
            pr.stdin.write(comp.image(i, tl, p['debut'] + tl).tobytes())
    pr.stdin.close()
    pr.wait()
    return sortie
