"""Sous-titres incrustés des shorts : transcription (faster-whisper, facultative) → fichier ASS « pop » par groupes de mots.

La transcription est facultative : si le modèle n'est pas disponible ou si rien d'intelligible n'est détecté,
le short sort sans sous-titres (jamais de sous-titres inventés).
"""
import re


def transcrire(video, langue='fr', modele='small'):
    """Renvoie [(debut, fin, mot)] ou [] si la transcription est indisponible."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return []
    try:
        m = WhisperModel(modele, device='cpu', compute_type='int8')
        segments, _ = m.transcribe(video, language=langue, word_timestamps=True, vad_filter=True,
                                   condition_on_previous_text=False, no_speech_threshold=0.5)
        mots = []
        for s in segments:
            if s.no_speech_prob > 0.6 or s.avg_logprob < -1.1:
                continue  # passage douteux : on préfère ne rien afficher
            for w in (s.words or []):
                t = w.word.strip()
                if t and w.probability >= 0.35:
                    mots.append((float(w.start), float(w.end), t))
        return mots
    except Exception as e:  # modèle non téléchargeable, audio illisible…
        print(f'  sous-titres indisponibles : {e}', flush=True)
        return []


def grouper(mots, max_mots=3, max_car=16, trou=0.45):
    """Regroupe les mots en petits blocs lisibles d'un coup d'œil."""
    blocs, cour = [], []
    for d, f, t in mots:
        long = sum(len(x[2]) for x in cour) + len(cour) + len(t)
        if cour and (len(cour) >= max_mots or long > max_car or d - cour[-1][1] > trou or cour[-1][2][-1:] in '.!?'):
            blocs.append(cour)
            cour = []
        cour.append((d, f, t))
    if cour:
        blocs.append(cour)
    out = []
    for i, b in enumerate(blocs):
        debut, fin = b[0][0], b[-1][1]
        suivant = blocs[i + 1][0][0] if i + 1 < len(blocs) else fin + 0.6
        fin = min(max(fin + 0.15, debut + 0.35), suivant)  # tient un peu, sans chevaucher le bloc suivant
        out.append((debut, fin, ' '.join(x[2] for x in b)))
    return out


def _t(s):
    s = max(0.0, s)
    return f'{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:05.2f}'


def ecrire_ass(mots, chemin, y=1340, police='Inter', taille=92, decalage=0.0, duree_max=None):
    """Écrit le fichier ASS (repère 1080×1920). Renvoie le nombre de blocs écrits."""
    entete = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: S,{police},{taille},&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,-1,0,0,0,100,100,0,0,1,7,3,8,70,70,{y},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lignes = []
    for d, f, txt in grouper(mots):
        d, f = d - decalage, f - decalage
        if f <= 0 or (duree_max and d >= duree_max):
            continue
        txt = re.sub(r'[{}\\]', '', txt).upper()
        # petit « pop » à l'apparition : 112 % → 100 % en 90 ms
        lignes.append(f'Dialogue: 0,{_t(d)},{_t(min(f, duree_max) if duree_max else f)},S,,0,0,0,,{{\\fscx112\\fscy112\\t(0,90,\\fscx100\\fscy100)}}{txt}')
    open(chemin, 'w', encoding='utf-8').write(entete + '\n'.join(lignes) + '\n')
    return len(lignes)
