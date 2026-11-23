"""Agent Monteur (shorts) — transforme un clip horizontal en short vertical 1080×1920.

Composition :
  - fond : le clip agrandi et flouté ;
  - sans zone de facecam renseignée : l'image complète du stream, centrée (facecam et incrustations comprises) ;
  - avec facecam (zone [x, y, l, h] en fractions de l'image, fournie par streamer) : la facecam en haut, le jeu dessous ;
  - accroche en haut (2 premières secondes décisives), crédit du streamer, sous-titres « pop » facultatifs ;
  - zones de sécurité Shorts/Reels respectées (rien d'important sous 1 560 px ni à droite de 930 px en bas).

Usage : python3 monter.py clip.mp4 sortie.mp4 --accroche "TEXTE" --streamer Nom --login nom [--facecam x,y,l,h]
                          [--debut s] [--fin s] [--sans-sous-titres]
"""
import argparse, json, os, re, shutil, subprocess, sys, textwrap

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import soustitres

L, H = 1080, 1920
DUREE_MAX = 59.0
POLICES = ['/usr/share/fonts/opentype/inter/Inter-Black.otf', '/usr/share/fonts/opentype/inter/Inter-ExtraBold.otf',
           '/usr/share/fonts/truetype/inter/Inter-Black.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']


def police(taille):
    for p in POLICES:
        if os.path.exists(p):
            return ImageFont.truetype(p, taille)
    return ImageFont.load_default()


def sonde(video):
    r = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries',
                        'stream=width,height,r_frame_rate:format=duration', '-of', 'json', video],
                       capture_output=True, text=True, check=True)
    d = json.loads(r.stdout)
    s = d['streams'][0]
    n, den = s['r_frame_rate'].split('/')
    return {'l': s['width'], 'h': s['height'], 'ips': float(n) / float(den or 1), 'duree': float(d['format']['duration'])}


def calque(accroche, streamer, login, y_titre, h_titre, y_credit, chemin):
    """PNG transparent 1080×1920 : accroche + pastille de crédit."""
    img = Image.new('RGBA', (L, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if accroche:
        # typographie française : espace insécable avant ! ? : ; pour ne jamais isoler la ponctuation
        texte = re.sub(r'\s+([!?:;»])', '\u00a0\\1', accroche.strip().upper())
        for taille in range(104, 52, -6):
            f = police(taille)
            car = max(8, int(940 / (taille * 0.62)))
            lignes = textwrap.wrap(texte, car)
            boite = d.multiline_textbbox((0, 0), '\n'.join(lignes), font=f, spacing=10, stroke_width=8, align='center')
            if len(lignes) <= 3 and boite[2] - boite[0] <= 960 and boite[3] - boite[1] <= h_titre:
                break
        hb = boite[3] - boite[1]
        d.multiline_text((L / 2, y_titre + (h_titre - hb) / 2 - boite[1]), '\n'.join(lignes), font=f, fill=(255, 255, 255, 255),
                         spacing=10, stroke_width=8, stroke_fill=(0, 0, 0, 255), align='center', anchor='ma')
    # crédit : obligatoire (le streamer est toujours nommé à l'écran)
    f = police(40)
    txt = f'twitch.tv/{login}' if login else streamer
    lt = d.textlength(txt, font=f)
    x0, larg, haut = 60, lt + 120, 76
    d.rounded_rectangle((x0, y_credit, x0 + larg, y_credit + haut), radius=38, fill=(18, 18, 22, 215))
    d.ellipse((x0 + 22, y_credit + 22, x0 + 54, y_credit + 54), fill=(145, 70, 255, 255))  # pastille violette (générique)
    d.text((x0 + 76, y_credit + haut / 2), txt, font=f, fill=(255, 255, 255, 255), anchor='lm')
    img.save(chemin)


def monter(clip, sortie, accroche='', streamer='', login='', facecam=None, debut=0.0, fin=None,
           sous_titres=True, langue='fr', zoom=1.0):
    s = sonde(clip)
    fin = min(fin or s['duree'], s['duree'])
    duree = min(fin - debut, DUREE_MAX)
    if duree < 5:
        raise ValueError(f'clip trop court ({duree:.1f} s)')
    tmp = os.path.splitext(sortie)[0] + '_tmp'
    os.makedirs(tmp, exist_ok=True)
    ips = min(60, round(s['ips']) or 30)

    if facecam:
        fx, fy, fl, fh = facecam
        # facecam : pleine largeur, hauteur plafonnée ; jeu dessous
        cl, ch = int(s['l'] * fl) // 2 * 2, int(s['h'] * fh) // 2 * 2
        hf = min(500, int(L * ch / cl) // 2 * 2)
        y_titre, h_titre, y_face = 150, 190, 350
        y_jeu = y_face + hf + 8
        h_jeu = min(760, 1500 - y_jeu) // 2 * 2
        y_sub, y_credit = y_jeu + h_jeu - 150, min(1480, y_jeu + h_jeu + 24)
        blocs = (f"[0:v]split=3[a][b][c];"
                 f"[a]scale={L}:{H}:force_original_aspect_ratio=increase,crop={L}:{H},gblur=sigma=28,eq=brightness=-0.22:saturation=0.9[fond];"
                 f"[b]crop={cl}:{ch}:{int(s['l'] * fx)}:{int(s['h'] * fy)},scale={L}:{hf}:force_original_aspect_ratio=increase,crop={L}:{hf}[face];"
                 f"[c]scale=-2:{int(h_jeu * 1.0)},crop='min(iw,{L})':{h_jeu},pad={L}:{h_jeu}:(ow-iw)/2:0:black[jeu];"
                 f"[fond][face]overlay=0:{y_face}[f1];[f1][jeu]overlay=0:{y_jeu}[v1]")
    else:
        lz = int(L * zoom) // 2 * 2
        hz = int(lz * s['h'] / s['l']) // 2 * 2
        # image complète par défaut (zoom 1) : la facecam et les incrustations du streamer restent visibles
        y_jeu = 560 if zoom <= 1.01 else 470
        y_titre, h_titre = (230, 290) if zoom <= 1.01 else (170, 270)
        y_sub, y_credit = y_jeu + hz + 50, y_jeu + hz + 200
        blocs = (f"[0:v]split=2[a][b];"
                 f"[a]scale={L}:{H}:force_original_aspect_ratio=increase,crop={L}:{H},gblur=sigma=28,eq=brightness=-0.22:saturation=0.9[fond];"
                 f"[b]scale={lz}:{hz},crop={L}:{hz}[jeu];"
                 f"[fond][jeu]overlay=0:{y_jeu}[v1]")
    y_credit = min(y_credit, 1480)

    png = os.path.join(tmp, 'calque.png')
    calque(accroche, streamer, login, y_titre, h_titre, y_credit, png)

    nb_sous = 0
    filtre_sub = ''
    if sous_titres:
        mots = soustitres.transcrire(clip, langue)
        if mots:
            ass = os.path.join(tmp, 'sous.ass')
            nb_sous = soustitres.ecrire_ass(mots, ass, y=y_sub, decalage=debut, duree_max=duree)
            if nb_sous:
                filtre_sub = f",ass='{ass}'"
    filtre = (blocs + f";[v1][1:v]overlay=0:0{filtre_sub},fps={ips},format=yuv420p[v];"
              f"[0:a]aresample=48000,loudnorm=I=-14:TP=-1.5:LRA=11[a2]")
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-ss', f'{debut:.2f}', '-t', f'{duree:.2f}', '-i', clip, '-loop', '1', '-i', png,
           '-filter_complex', filtre, '-map', '[v]', '-map', '[a2]', '-t', f'{duree:.2f}',
           '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', '-profile:v', 'high', '-c:a', 'aac', '-b:a', '160k',
           '-movflags', '+faststart', sortie]
    subprocess.run(cmd, check=True)
    couv = os.path.splitext(sortie)[0] + '.jpg'
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', '1.5', '-i', sortie, '-frames:v', '1', '-q:v', '3', couv], check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    r = sonde(sortie)
    return {'fichier': sortie, 'couverture': couv, 'duree': round(r['duree'], 1), 'largeur': r['l'], 'hauteur': r['h'],
            'sous_titres': nb_sous, 'facecam': bool(facecam)}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('clip'); ap.add_argument('sortie')
    ap.add_argument('--accroche', default=''); ap.add_argument('--streamer', default=''); ap.add_argument('--login', default='')
    ap.add_argument('--facecam'); ap.add_argument('--debut', type=float, default=0.0); ap.add_argument('--fin', type=float)
    ap.add_argument('--sans-sous-titres', action='store_true'); ap.add_argument('--langue', default='fr')
    a = ap.parse_args()
    fc = [float(x) for x in a.facecam.split(',')] if a.facecam else None
    print(json.dumps(monter(a.clip, a.sortie, a.accroche, a.streamer, a.login, fc, a.debut, a.fin,
                            not a.sans_sous_titres, a.langue), ensure_ascii=False))
