"""Production v2 : un plan par phrase, sous-titres mot à mot, SFX, musique rythmée, rendu parallèle.

Usage : python3 produire2.py spec.json dossier [--scenes a-b] [--voix piper|studio] [--audio-dir DIR]

Spec (par scène) :
  {"chapitre"?: str, "visuel": {...}, "voix": "texte"}                      → découpé en phrases (même visuel)
  {"chapitre"?: str, "visuel": {...}, "beats": [{"voix": "...", "visuel"?: {...}|"suite"}]}
  Un beat sans visuel (ou "suite") prolonge le visuel précédent ; un beat avec visuel ouvre un nouveau plan.
--voix studio : lit les fichiers audio pré-générés (DIR/bNNN.wav, + bNNN.json de minutage mot à mot si fourni).
"""
import json, os, re, sys, wave, argparse, subprocess, glob
import numpy as np
from multiprocessing import Process

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voix import synthetiser
import rendu2

SR = 22050
PAUSE_PHRASE = 0.10
PAUSE_SCENE = 0.32


# ------------------------------------------------------------------ découpage

def phrases(txt):
    morceaux = re.split(r'(?<=[.!?…])\s+(?=[A-ZÀ-ÖØ-Ý0-9«"])', txt.strip())
    return [m for m in morceaux if m.strip()]


TYPES_DONNEES = ('ledger', 'barres', 'liste', 'equation', 'comparatif', 'courbe')
RE_NOMBRE = re.compile(r'(?<![\w,])(\d{1,3}(?:[ \u202f]\d{3})*(?:,\d+)?)\s?(%|€|ans\b|euros\b)?')


def auto_visuel(phrase, deja):
    """Visuel automatique d'une phrase dans une scène « parlée » (titre, section, chiffre…)."""
    nus = phrase.strip()
    for m in RE_NOMBRE.finditer(nus):
        val = m.group(1) + ((' ' if m.group(2) not in ('%', '€') else '\u202f') + m.group(2).replace('euros', '€') if m.group(2) else '')
        if m.group(2) is None:
            continue  # un nombre sans unité n'a pas de sens isolé à l'écran
        if val in deja:
            continue
        deja.add(val)
        neg = re.search(r"\b(perds|pertes?|impôt|taxé|coûte|frais|moins|recul)", nus, re.I)
        return {'type': 'chiffre', 'valeur': val.replace('\u202f', ' '), 'compteur': True, 'couleur': 'negatif' if neg else 'accent'}
    mots = nus.split()
    if len(mots) <= 6:
        return {'type': 'punch', 'lignes': [nus], 'taille': 150, '_texte': True}
    if len(mots) <= 14:
        return {'type': 'titre', 'lignes': [nus], '_texte': True}
    return None


def beats_de(spec, plage=None):
    scenes = spec['scenes'][plage[0] - 1:plage[1]] if plage else spec['scenes']
    out = []
    chap = None
    for si, sc in enumerate(scenes):
        chap = sc.get('chapitre') or (sc['visuel'].get('titre') if sc.get('visuel', {}).get('type') == 'section' else None) or chap
        if 'beats' in sc:
            bl = sc['beats']
        else:
            bl = [{'voix': p} for p in phrases(sc['voix'])]
            if sc['visuel']['type'] not in TYPES_DONNEES and sc.get('auto', True):
                deja = set()
                for b in bl[1:]:
                    b['visuel'] = auto_visuel(b['voix'], deja)
        for bi, b in enumerate(bl):
            vis = b.get('visuel')
            if bi == 0 and (vis is None or vis == 'suite'):
                vis = sc['visuel']
            out.append({'voix': b['voix'], 'visuel': vis if vis not in (None, 'suite') else None,
                        'scene': si, 'fin_scene': bi == len(bl) - 1, 'chapitre': chap,
                        'sfx': b.get('sfx')})
    return out


# ------------------------------------------------------------------ audio

def lire_wav(p):
    with wave.open(p) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            x = x.reshape(-1, 2).mean(axis=1)
        return x, w.getframerate()


def ecrire_wav(p, x, sr):
    x = np.clip(x, -1, 1)
    with wave.open(p, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def reechantillonner(x, sr, cible):
    if sr == cible:
        return x
    n = int(len(x) * cible / sr)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)


def rogner_silences(x, sr, seuil=0.012, avec_decalage=False):
    env = np.convolve(np.abs(x), np.ones(int(sr * 0.01)) / int(sr * 0.01), mode='same')
    idx = np.where(env > seuil)[0]
    if len(idx) == 0:
        return (x, 0.0) if avec_decalage else x
    a = max(0, idx[0] - int(0.03 * sr))
    b = min(len(x), idx[-1] + int(0.06 * sr))
    return (x[a:b], a / sr) if avec_decalage else x[a:b]


def mots_affiches(txt):
    toks = txt.replace('’', "'").split()
    out = []
    for t in toks:
        if out and (t in ('%', '€', '?', '!', ':', ';', '»') or re.fullmatch(r'\d{3}([,.]\d+)?(\s?[%€])?[.,;:!?]*', t) and re.fullmatch(r'\d{1,3}', out[-1].rstrip('−-'))):
            out[-1] = out[-1] + (' ' if t in ('%', '€', '?', '!', ':', ';') else ' ') + t
        elif t in ('«',):
            continue
        else:
            out.append(t)
    return out


def minutage_estime(txt, duree):
    mots = mots_affiches(txt)
    poids = [max(2, len(re.sub(r'[^\wÀ-ÿ%€]', '', m))) + (4 if m[-1:] in '.,;:!?' else 0) for m in mots]
    tot = sum(poids)
    t, res = 0.0, []
    for m, w in zip(mots, poids):
        d = duree * w / tot
        res.append((t, t + d * 0.92, m))
        t += d
    return res


def sfx_whoosh(sr=44100, d=0.42, graine=0):
    rng = np.random.default_rng(graine)
    n = int(sr * d)
    bruit = rng.standard_normal(n).astype(np.float32)
    spec = np.fft.rfft(bruit)
    f = np.fft.rfftfreq(n, 1 / sr)
    spec *= np.exp(-((np.log(f + 1) - np.log(1800)) ** 2) / 1.2)
    x = np.fft.irfft(spec, n)
    t = np.linspace(0, 1, n)
    env = np.where(t < 0.55, (t / 0.55) ** 2, ((1 - t) / 0.45) ** 1.5)
    x = x * env
    return x / (np.max(np.abs(x)) + 1e-9)


def sfx_pop(sr=44100):
    n = int(sr * 0.11)
    t = np.arange(n) / sr
    f = 900 * np.exp(-t * 18) + 260
    x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 38)
    return x / np.max(np.abs(x))


def sfx_impact(sr=44100):
    n = int(sr * 0.5)
    t = np.arange(n) / sr
    f = 110 * np.exp(-t * 9) + 42
    x = np.sin(2 * np.pi * np.cumsum(f) / sr) * np.exp(-t * 7)
    return x / np.max(np.abs(x))


def musique_rythmee(duree, sr=44100, bpm=102, graine=11):
    """Boucle électro sobre (libre de droits, générée) : kick, charleston, basse, nappe."""
    rng = np.random.default_rng(graine)
    n = int(duree * sr)
    out = np.zeros(n, np.float32)
    temps = 60 / bpm
    # notes de basse (la mineur : A F C G), une mesure de 4 temps par accord
    basses = [55.0, 43.65, 65.41, 49.0]
    accords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63], [196.0, 261.63, 329.63], [196.0, 246.94, 293.66]]
    kick_n = int(0.32 * sr)
    tk = np.arange(kick_n) / sr
    kick = np.sin(2 * np.pi * np.cumsum(55 + 90 * np.exp(-tk * 30)) / sr) * np.exp(-tk * 9)
    hat_n = int(0.05 * sr)
    hat = rng.standard_normal(hat_n) * np.exp(-np.arange(hat_n) / sr * 90)
    hat = np.diff(hat, prepend=0)
    nb = int(duree / temps) + 1
    for b in range(nb):
        i = int(b * temps * sr)
        mesure = b // 4
        if i >= n:
            break
        def add(sig, pos, g):
            j = min(n, pos + len(sig))
            if pos < n:
                out[pos:j] += g * sig[:j - pos]
        add(kick, i, 0.55)
        add(hat, i + int(temps / 2 * sr), 0.16)
        if b % 2 == 1:
            add(hat, i + int(temps * 0.75 * sr), 0.07)
        # basse en croches
        f0 = basses[mesure % 4]
        bn = int(temps / 2 * sr)
        tb = np.arange(bn) / sr
        for k in range(2):
            sig = (np.sign(np.sin(2 * np.pi * f0 * tb)) * 0.5 + np.sin(2 * np.pi * f0 * tb)) * np.exp(-tb * 6)
            add(sig * 0.5, i + k * bn, 0.22)
        if b % 4 == 0:
            pn = int(4 * temps * sr)
            tp = np.arange(pn) / sr
            env = np.minimum(1, tp / 0.4) * np.minimum(1, (4 * temps - tp) / 0.6)
            pad = sum(np.sin(2 * np.pi * f * tp + rng.uniform(0, 6)) for f in accords[mesure % 4]) * env
            add(pad, i, 0.05)
    k = 6
    out = np.convolve(out, np.ones(k) / k, mode='same')
    fade = int(2 * sr)
    out[:fade] *= np.linspace(0, 1, fade)
    out[-fade:] *= np.linspace(1, 0, fade)
    return out / (np.max(np.abs(out)) + 1e-9) * 0.6, sr


# ------------------------------------------------------------------ production

def produire(spec, dossier, plage=None, mode_voix='piper', audio_dir=None, sous_titres=True):
    os.makedirs(dossier, exist_ok=True)
    tmp = os.path.join(dossier, '_tmp')
    os.makedirs(tmp, exist_ok=True)
    beats = beats_de(spec, plage)
    v = dict(spec['voix'])
    if mode_voix == 'piper' and not os.path.exists(v['modele']):
        c = glob.glob(os.path.join(os.environ.get('VOIX_DIR', os.path.join(os.path.dirname(__file__), '..', 'voix')), '**', v['modele']), recursive=True)
        v['modele'] = c[0]
    pistes, plans = [], []
    t = 0.0
    groupe = -1
    vis_courant = None
    for i, b in enumerate(beats):
        if mode_voix == 'studio':
            src = os.path.join(audio_dir, f'b{i:03d}.wav')
            if not os.path.exists(src):
                subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', os.path.join(audio_dir, f'b{i:03d}.mp3'), '-ac', '1', '-ar', str(SR), src], check=True)
            x, sr = lire_wav(src)
            x = reechantillonner(x, sr, SR)
        else:
            p = os.path.join(tmp, f'b{i:03d}.wav')
            synthetiser(b['voix'], v['modele'], v.get('locuteur', 0), p, v.get('vitesse', 1.0))
            x, sr = lire_wav(p)
            x = reechantillonner(x, sr, SR)
        x, decalage = rogner_silences(x, SR, avec_decalage=True)
        parole = len(x) / SR
        pause = PAUSE_SCENE if b['fin_scene'] else PAUSE_PHRASE
        seg = np.concatenate([x, np.zeros(int(pause * SR), np.float32)])
        pistes.append(seg)
        jm = os.path.join(audio_dir, f'b{i:03d}.json') if audio_dir else None
        if jm and os.path.exists(jm):
            mots = [(max(0.0, m[0] - decalage), max(0.0, m[1] - decalage), m[2]) for m in json.load(open(jm))]
        else:
            mots = minutage_estime(b['voix'], parole)
        nouveau = b['visuel'] is not None
        if nouveau:
            groupe += 1
            vis_courant = b['visuel']
        plans.append({'debut': t, 'duree': len(seg) / SR, 'visuel': vis_courant, 'groupe': groupe, 'nouveau': nouveau,
                      'mots': mots, 'chapitre': b['chapitre'], 'sfx': b.get('sfx')})
        t += len(seg) / SR
        print(f'  voix {i + 1}/{len(beats)} : {len(seg) / SR:.1f} s', flush=True)
    # ambiances : rotation par chapitre, point de départ propre à chaque vidéo
    rot = spec.get('ambiances') or rendu2.ROTATION
    dep = spec.get('ambiance_depart')
    if dep is None:
        dep = sum(map(ord, spec['id'])) % len(rot)
    chap_idx, dernier = -1, object()
    for p in plans:
        if p['chapitre'] != dernier:
            chap_idx += 1
            dernier = p['chapitre']
        p['theme'] = rot[(dep + chap_idx) % len(rot)]
    # bornes de groupes
    for g in set(p['groupe'] for p in plans):
        pg = [p for p in plans if p['groupe'] == g]
        for p in pg:
            p['t_groupe'] = pg[0]['debut']
            p['d_groupe'] = pg[-1]['debut'] + pg[-1]['duree'] - pg[0]['debut']
    duree = t
    voix_wav = os.path.join(tmp, 'voix.wav')
    ecrire_wav(voix_wav, np.concatenate(pistes), SR)

    # rendu parallèle en 2 moitiés (frontière sur un plan)
    print(f'  rendu visuel ({duree:.0f} s, {len(plans)} plans)…', flush=True)
    cumul, coupe = 0.0, len(plans)
    for i, p in enumerate(plans):
        cumul += p['duree']
        if cumul >= duree / 2:
            coupe = i + 1
            break
    parts = [list(range(0, coupe)), list(range(coupe, len(plans)))]
    fichiers, procs = [], []
    for k, idx in enumerate(parts):
        if not idx:
            continue
        f = os.path.join(tmp, f'part{k}.mp4')
        fichiers.append(f)
        pr = Process(target=rendu2.rendre_segment, args=(plans, idx, 0, f, spec.get('theme', 'finance'), sous_titres))
        pr.start()
        procs.append(pr)
    for pr in procs:
        pr.join()
    liste = os.path.join(tmp, 'parts.txt')
    open(liste, 'w').write(''.join(f"file '{os.path.abspath(f)}'\n" for f in fichiers))
    muet = os.path.join(tmp, 'muet.mp4')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', liste, '-c', 'copy', muet], check=True)

    # musique + effets sonores
    msr = 44100
    mus, _ = musique_rythmee(duree + 1, msr)
    fx = np.zeros_like(mus)
    wh, pop, imp = sfx_whoosh(msr), sfx_pop(msr), sfx_impact(msr)
    for k, p in enumerate(plans):
        if not p['nouveau'] or k == 0:
            continue
        pos = int(max(0, p['debut'] - 0.18) * msr)
        typ = p['visuel']['type']
        son = imp if typ in ('punch', 'section') else wh
        g = 0.32 if son is wh else 0.45
        j = min(len(fx), pos + len(son))
        fx[pos:j] += g * son[:j - pos]
        if typ in ('chiffre',):
            pos2 = int((p['debut'] + 0.02) * msr)
            j = min(len(fx), pos2 + len(pop))
            fx[pos2:j] += 0.3 * pop[:j - pos2]
    mus_wav = os.path.join(tmp, 'musique.wav')
    fx_wav = os.path.join(tmp, 'sfx.wav')
    ecrire_wav(mus_wav, mus, msr)
    ecrire_wav(fx_wav, fx / max(1.0, np.max(np.abs(fx))), msr)

    sortie = os.path.join(dossier, spec['id'] + '.mp4')
    filtre = ("[1:a]aresample=44100,loudnorm=I=-15:TP=-1.5:LRA=9,asplit[v][vs];"
              "[2:a]volume=0.13[m];[m][vs]sidechaincompress=threshold=0.04:ratio=5:attack=15:release=350[md];"
              "[3:a]volume=0.55[fx];"
              "[v][md][fx]amix=inputs=3:normalize=0:duration=first[a];"
              f"[0:v]drawbox=x=0:y=ih-8:w='iw*t/{duree:.3f}':h=8:color=0xFFBE3C:t=fill[vid]")
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', muet, '-i', voix_wav, '-i', mus_wav, '-i', fx_wav,
                    '-filter_complex', filtre, '-map', '[vid]', '-map', '[a]', '-c:v', 'libx264', '-preset', 'veryfast',
                    '-crf', '20', '-c:a', 'aac', '-b:a', '192k', '-movflags', '+faststart', sortie], check=True)
    chap, vu = [], set()
    for p in plans:
        if p['chapitre'] and p['chapitre'] not in vu:
            vu.add(p['chapitre'])
            chap.append((round(p['debut'], 2), p['chapitre']))
    return sortie, duree, chap


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('spec'); ap.add_argument('sortie')
    ap.add_argument('--scenes'); ap.add_argument('--voix', default='piper'); ap.add_argument('--audio-dir')
    ap.add_argument('--sans-sous-titres', action='store_true')
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    plage = tuple(map(int, a.scenes.split('-'))) if a.scenes else None
    out, d, chap = produire(spec, a.sortie, plage, a.voix, a.audio_dir, not a.sans_sous_titres)
    print(json.dumps({'fichier': out, 'duree': round(d, 1), 'chapitres': chap}, ensure_ascii=False))
