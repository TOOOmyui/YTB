"""Agent Monteur — rendu des scènes animées (PIL) et assemblage (ffmpeg).

Spécification d'une scène (JSON) :
  {"voix": "texte lu", "visuel": {"type": ..., ...}}
Types de visuels : titre, chiffre, section, citation, ledger, barres, liste, equation, comparatif, courbe
"""
import math, os, subprocess, glob
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FPS = 30

THEMES = {
    'finance': dict(fond=(11, 14, 19), fond2=(20, 26, 36), texte=(242, 244, 247), muet=(138, 148, 166),
                    accent=(245, 184, 61), positif=(61, 220, 151), negatif=(255, 90, 95), grille=(38, 46, 60)),
}


def _police(poids, taille):
    noms = {'regular': ['Inter-Regular.otf', 'inter-latin-400-normal.woff'],
            'semibold': ['Inter-SemiBold.otf', 'inter-latin-600-normal.woff'],
            'bold': ['Inter-ExtraBold.otf', 'Inter-Bold.otf', 'inter-latin-800-normal.woff']}[poids]
    dossiers = ['/usr/share/fonts/opentype/inter', os.path.join(os.path.dirname(__file__), 'polices')]
    for d in dossiers:
        for n in noms:
            p = os.path.join(d, n)
            if os.path.exists(p):
                return ImageFont.truetype(p, taille)
    return ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', taille)


_CACHE = {}


def P(poids, taille):
    k = (poids, taille)
    if k not in _CACHE:
        _CACHE[k] = _police(poids, taille)
    return _CACHE[k]


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def melange(c1, c2, a):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * a) for i in range(3))


class Toile:
    def __init__(self, w, h, th):
        self.w, self.h, self.th = w, h, th
        self.s = h / 1080.0  # échelle (1080p = 1)
        self.fond = self._fond()

    def _fond(self):
        img = Image.new('RGB', (self.w, self.h), self.th['fond'])
        # léger dégradé radial
        g = Image.new('L', (self.w, self.h), 0)
        d = ImageDraw.Draw(g)
        r = int(max(self.w, self.h) * 0.75)
        d.ellipse([self.w // 2 - r, -r // 2, self.w // 2 + r, r + r // 2], fill=90)
        g = g.filter(ImageFilter.GaussianBlur(int(250 * self.s)))
        haut = Image.new('RGB', (self.w, self.h), self.th['fond2'])
        return Image.composite(haut, img, g)

    def nouvelle(self):
        return self.fond.copy()

    def z(self, v):
        return int(v * self.s)


def texte_centre(d, toile, y, txt, police, couleur, alpha=1.0, dy=0):
    fond = toile.th['fond']
    c = melange(fond, couleur, alpha)
    bb = d.textbbox((0, 0), txt, font=police)
    w = bb[2] - bb[0]
    d.text(((toile.w - w) / 2 - bb[0], y + dy), txt, font=police, fill=c)
    return bb[3] - bb[1]


def couper(d, txt, police, largeur):
    mots, lignes, cur = txt.split(), [], ''
    for m in mots:
        essai = (cur + ' ' + m).strip()
        if d.textlength(essai, font=police) <= largeur:
            cur = essai
        else:
            if cur:
                lignes.append(cur)
            cur = m
    if cur:
        lignes.append(cur)
    return lignes


def apparition(t, debut, duree=0.55):
    a = ease((t - debut) / duree)
    return a, (1 - a) * 40


def nombre_anime(valeur, a):
    """Compte progressif pour '31,4 %', '15 700 €', '≈ 41 000 €'…"""
    import re
    m = re.search(r'[-−]?\d[\d\s]*(?:,\d+)?', valeur)
    if not m or a >= 1:
        return valeur
    brut = m.group(0)
    neg = brut.startswith(('-', '−'))
    s = brut.lstrip('-−').replace(' ', '').replace(' ', '')
    dec = len(s.split(',')[1]) if ',' in s else 0
    v = float(s.replace(',', '.')) * a
    if dec:
        txt = f"{v:.{dec}f}".replace('.', ',')
    else:
        txt = f"{int(round(v)):,}".replace(',', ' ')
    if neg:
        txt = '−' + txt
    return valeur[:m.start()] + txt + valeur[m.end():]


# ---------------------------------------------------------------- scènes

def dessiner(toile, v, t, dur):
    img = toile.nouvelle()
    d = ImageDraw.Draw(img)
    th, z, W, H = toile.th, toile.z, toile.w, toile.h
    typ = v['type']
    marge = z(160)

    if typ in ('titre', 'citation', 'section'):
        lignes = v.get('lignes') or [v.get('texte') or v.get('titre')]
        if typ == 'section':
            pol, coul = P('bold', z(120)), th['texte']
        elif typ == 'citation':
            pol, coul = P('semibold', z(72)), th['texte']
        else:
            pol, coul = P('bold', z(96)), th['texte']
        tout = []
        for i, l in enumerate(lignes):
            for sl in couper(d, l, pol, W - 2 * marge):
                tout.append((i, sl))
        hl = z(int(pol.size / z(1) * 1.25)) if False else int(pol.size * 1.25)
        extra = []
        if typ == 'section' and v.get('sous'):
            extra = [v['sous']]
        htot = hl * len(tout) + (z(80) if extra else 0)
        y0 = (H - htot) / 2
        if typ == 'section':
            a, dy = apparition(t, 0.0)
            lw = int(z(120) * a)
            d.rectangle([W / 2 - lw, y0 - z(60), W / 2 + lw, y0 - z(52)], fill=th['accent'])
        for k, (i, sl) in enumerate(tout):
            a, dy = apparition(t, 0.1 + 0.45 * i)
            c = th['accent'] if v.get('accent') == i else coul
            texte_centre(d, toile, y0 + k * hl, sl, pol, c, a, dy)
        if extra:
            a, dy = apparition(t, 0.5)
            texte_centre(d, toile, y0 + len(tout) * hl + z(20), extra[0], P('regular', z(48)), th['muet'], a, dy)

    elif typ == 'chiffre':
        a, dy = apparition(t, 0.0, 0.4)
        ac = ease(t / 1.2) if v.get('compteur', True) else 1
        val = nombre_anime(v['valeur'], ac)
        coul = th.get(v.get('couleur', 'accent'), th['accent'])
        pol = P('bold', z(260))
        while d.textlength(val, font=pol) > W - 2 * marge and pol.size > 60:
            pol = P('bold', pol.size - 10)
        hauteur = pol.size
        y = (H - hauteur) / 2 - z(60)
        texte_centre(d, toile, y, val, pol, coul, a, dy)
        if v.get('label'):
            a2, dy2 = apparition(t, 0.6)
            for k, l in enumerate(couper(d, v['label'], P('semibold', z(52)), W - 2 * marge)):
                texte_centre(d, toile, y + hauteur + z(70) + k * z(66), l, P('semibold', z(52)), th['muet'], a2, dy2)

    elif typ == 'ledger':
        titre = v.get('titre')
        lignes = v['lignes']
        tot = v.get('total')
        x0, x1 = W * 0.22, W * 0.78
        # élargit le tableau si un libellé et son montant risquent de se toucher
        besoin = max(d.textlength(l[0], font=P('semibold', z(58))) + d.textlength(l[1], font=P('bold', z(58))) for l in lignes) + z(80)
        if besoin > x1 - x0:
            x0 = max(marge * 0.6, (W - besoin) / 2)
            x1 = W - x0
        pas = z(96)
        n = len(lignes) + (1 if tot else 0)
        y = (H - n * pas - (z(110) if titre else 0)) / 2
        if titre:
            a, dy = apparition(t, 0)
            texte_centre(d, toile, y, titre, P('semibold', z(52)), th['muet'], a, dy)
            y += z(110)
        espace = max(0.5, min(1.3, (dur * 0.55) / max(1, n)))
        for i, l in enumerate(lignes):
            a, dy = apparition(t, 0.2 + i * espace)
            ton = l[2] if len(l) > 2 else None
            cv = th.get(ton, th['texte']) if ton else th['texte']
            pol = P('semibold', z(58))
            d.text((x0, y + dy), l[0], font=pol, fill=melange(th['fond'], th['texte'], a))
            w = d.textlength(l[1], font=P('bold', z(58)))
            d.text((x1 - w, y + dy), l[1], font=P('bold', z(58)), fill=melange(th['fond'], cv, a))
            y += pas
        if tot:
            a, dy = apparition(t, 0.2 + len(lignes) * espace)
            d.rectangle([x0, y - z(22), x0 + (x1 - x0) * a, y - z(18)], fill=th['grille'] if a < 1 else th['muet'])
            ton = tot[2] if len(tot) > 2 else 'accent'
            d.text((x0, y + dy), tot[0], font=P('bold', z(64)), fill=melange(th['fond'], th['texte'], a))
            val = nombre_anime(tot[1], ease((t - 0.2 - len(lignes) * espace) / 1.0))
            w = d.textlength(val, font=P('bold', z(72)))
            d.text((x1 - w, y + dy - z(4)), val, font=P('bold', z(72)), fill=melange(th['fond'], th.get(ton, th['accent']), a))

    elif typ == 'barres':
        items = v['items']
        titre = v.get('titre')
        maxv = max(it[1] for it in items)
        lab_w = max(d.textlength(it[0], font=P('semibold', z(50))) for it in items)
        val_w = max(d.textlength(it[2], font=P('bold', z(56))) for it in items)
        x0 = max(W * 0.26, marge + lab_w + z(40))
        xl = W - marge - val_w - z(24)
        pas = z(150)
        y = (H - len(items) * pas - (z(120) if titre else 0)) / 2 + (z(120) if titre else 0)
        if titre:
            a, dy = apparition(t, 0)
            texte_centre(d, toile, y - z(130), titre, P('semibold', z(54)), th['muet'], a, dy)
        espace = max(0.5, min(1.4, (dur * 0.5) / len(items)))
        for i, it in enumerate(items):
            deb = 0.3 + i * espace
            a, dy = apparition(t, deb)
            g = ease((t - deb) / 1.0)
            ton = it[3] if len(it) > 3 else ('accent' if it[1] == maxv else 'positif')
            coul = th.get(ton, th['accent'])
            pol = P('semibold', z(50))
            lw = d.textlength(it[0], font=pol)
            d.text((x0 - z(40) - lw, y + z(20)), it[0], font=pol, fill=melange(th['fond'], th['texte'], a))
            lg = (xl - x0) * it[1] / maxv * g
            d.rounded_rectangle([x0, y + z(10), x0 + max(lg, 2), y + z(90)], radius=z(12), fill=coul)
            lab = nombre_anime(it[2], g)
            d.text((x0 + lg + z(24), y + z(18)), lab, font=P('bold', z(56)), fill=melange(th['fond'], th['texte'], a))
            y += pas

    elif typ == 'liste':
        titre = v.get('titre')
        items = v['items']
        pol = P('semibold', z(56))
        x0 = W * 0.18
        lignes_par = [couper(d, it, pol, W * 0.62) for it in items]
        htot = sum(len(l) * z(72) + z(48) for l in lignes_par) + (z(130) if titre else 0)
        y = (H - htot) / 2
        if titre:
            a, dy = apparition(t, 0)
            texte_centre(d, toile, y, titre, P('bold', z(72)), th['texte'], a, dy)
            y += z(130)
        espace = max(0.6, min(3.0, (dur * 0.7) / len(items)))
        for i, ls in enumerate(lignes_par):
            a, dy = apparition(t, 0.3 + i * espace)
            r = z(40)
            cx, cy = x0 + r, y + z(36)
            d.ellipse([cx - r, cy - r + dy, cx + r, cy + r + dy], fill=melange(th['fond'], th['accent'], a))
            num = str(i + 1)
            nw = d.textlength(num, font=P('bold', z(44)))
            d.text((cx - nw / 2, cy - z(28) + dy), num, font=P('bold', z(44)), fill=melange(th['fond'], th['fond'], a))
            for k, l in enumerate(ls):
                d.text((x0 + z(120), y + k * z(72) + dy), l, font=pol, fill=melange(th['fond'], th['texte'], a))
            y += len(ls) * z(72) + z(48)

    elif typ == 'equation':
        termes = v['termes']
        polv, poll = P('bold', z(110)), P('semibold', z(40))
        largeurs = [max(d.textlength(tm[0], font=polv), d.textlength(tm[1], font=poll) if len(tm) > 1 else 0) for tm in termes]
        gap = z(50)
        tot = sum(largeurs) + gap * (len(termes) - 1)
        x = (W - tot) / 2
        y = H / 2 - z(90)
        espace = max(0.4, min(1.0, dur * 0.5 / len(termes)))
        for i, tm in enumerate(termes):
            a, dy = apparition(t, 0.2 + i * espace)
            ton = tm[2] if len(tm) > 2 else ('muet' if len(tm) == 1 else 'texte')
            c = th.get(ton, th['texte'])
            w = d.textlength(tm[0], font=polv)
            d.text((x + (largeurs[i] - w) / 2, y + dy), tm[0], font=polv, fill=melange(th['fond'], c, a))
            if len(tm) > 1 and tm[1]:
                wl = d.textlength(tm[1], font=poll)
                d.text((x + (largeurs[i] - wl) / 2, y + z(150) + dy), tm[1], font=poll, fill=melange(th['fond'], th['muet'], a))
            x += largeurs[i] + gap

    elif typ == 'comparatif':
        cols = v['colonnes']  # [{"titre":..,"lignes":[..],"ton":..}, ...]
        n = len(cols)
        lw = (W - 2 * marge - z(60) * (n - 1)) / n
        for i, col in enumerate(cols):
            a, dy = apparition(t, 0.2 + i * 0.8)
            x = marge + i * (lw + z(60))
            c = th.get(col.get('ton', 'accent'), th['accent'])
            y0 = H * 0.24
            d.rounded_rectangle([x, y0 + dy, x + lw, H * 0.78 + dy], radius=z(28),
                                outline=melange(th['fond'], c, a), width=z(4))
            tw = d.textlength(col['titre'], font=P('bold', z(64)))
            d.text((x + (lw - tw) / 2, y0 + z(50) + dy), col['titre'], font=P('bold', z(64)), fill=melange(th['fond'], c, a))
            yy = y0 + z(170)
            for l in col['lignes']:
                for sl in couper(d, l, P('semibold', z(46)), lw - z(80)):
                    sw = d.textlength(sl, font=P('semibold', z(46)))
                    d.text((x + (lw - sw) / 2, yy + dy), sl, font=P('semibold', z(46)), fill=melange(th['fond'], th['texte'], a))
                    yy += z(62)
                yy += z(20)

    elif typ == 'courbe':
        series = v['series']  # [{"nom":..,"points":[..],"ton":..,"fin":"185 000 €"}]
        titre = v.get('titre')
        gx0, gx1, gy0, gy1 = W * 0.10, W * 0.70, H * 0.24, H * 0.82
        rang = sorted(range(len(series)), key=lambda k: -series[k]['points'][-1])
        maxv = max(max(s['points']) for s in series)
        if titre:
            a, dy = apparition(t, 0)
            texte_centre(d, toile, H * 0.08, titre, P('semibold', z(52)), th['muet'], a, dy)
        for k in range(5):
            yy = gy1 - (gy1 - gy0) * k / 4
            d.line([gx0, yy, gx1, yy], fill=th['grille'], width=max(1, z(2)))
        if v.get('axe_x'):
            for k, lab in enumerate(v['axe_x']):
                xx = gx0 + (gx1 - gx0) * k / (len(v['axe_x']) - 1)
                lw = d.textlength(lab, font=P('regular', z(34)))
                d.text((xx - lw / 2, gy1 + z(20)), lab, font=P('regular', z(34)), fill=th['muet'])
        for i, s in enumerate(series):
            deb = 0.4 + i * (dur * 0.35)
            g = ease((t - deb) / max(1.5, dur * 0.3))
            pts = s['points']
            n = len(pts)
            m = max(2, int(1 + (n - 1) * g))
            coords = [(gx0 + (gx1 - gx0) * j / (n - 1), gy1 - (gy1 - gy0) * pts[j] / maxv) for j in range(m)]
            c = th.get(s.get('ton', 'accent'), th['accent'])
            if g > 0 and len(coords) > 1:
                d.line(coords, fill=c, width=z(8), joint='curve')
            if g >= 1:
                a, dy = apparition(t, deb + max(1.5, dur * 0.3))
                xe, ye = coords[-1]
                d.ellipse([xe - z(12), ye - z(12), xe + z(12), ye + z(12)], fill=c)
                off = -z(110) if rang.index(i) == 0 else z(14) + z(100) * (rang.index(i) - 1)
                d.text((xe + z(30), ye + off), s['nom'], font=P('semibold', z(36)), fill=melange(th['fond'], th['muet'], a))
                d.text((xe + z(30), ye + off + z(42)), s.get('fin', ''), font=P('bold', z(52)), fill=melange(th['fond'], c, a))
    else:
        raise ValueError('type de visuel inconnu : ' + typ)
    return img


# ---------------------------------------------------------------- assemblage

def rendre_video(scenes, durees, sortie, theme='finance', taille=(1920, 1080), fondu=0.25):
    """scenes : liste de visuels ; durees : durée (s) de chaque scène. Écrit une vidéo muette."""
    W, H = taille
    toile = Toile(W, H, THEMES[theme])
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}',
           '-r', str(FPS), '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
           '-pix_fmt', 'yuv420p', sortie]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total_frames = 0
    for i, (v, dur) in enumerate(zip(scenes, durees)):
        nf = max(1, int(round(dur * FPS)))
        dernier, fin_anim = None, min(dur - fondu, 0.75 * dur + 1.6)
        for f in range(nf):
            t = f / FPS
            if dernier is not None and t > fin_anim and f < nf - int(fondu * FPS):
                p.stdin.write(dernier)
                continue
            img = dessiner(toile, v, t, dur)
            # fondu d'entrée / sortie (vers le fond)
            if t < fondu:
                img = Image.blend(toile.fond, img, t / fondu)
            elif t > dur - fondu:
                img = Image.blend(toile.fond, img, max(0, (dur - t) / fondu))
            b = img.tobytes()
            if t > fin_anim:
                dernier = b
            p.stdin.write(b)
        total_frames += nf
    p.stdin.close()
    p.wait()
    return total_frames / FPS
