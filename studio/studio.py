"""Studio voix — exécuté par GitHub Actions (accès Internet), appelé par la régie.

Chaque fichier commandes/<nom>.json non encore traité produit sorties/<nom>/ puis est marqué traité.

Commande « casting » :
  {"mode": "casting", "langue": "fr", "max": 12, "recherche": ["news", "narration"]}
  → sorties/<nom>/voix.json (liste des voix) + apercus/<voice_id>.mp3 (échantillons d'origine)

Commande « essai » (même texte, plusieurs voix de la bibliothèque) :
  {"mode": "essai", "texte": "...", "voix": [{"voice_id": "...", "public_owner_id": "...", "nom": "..."}],
   "model_id": "eleven_multilingual_v2", "reglages": {...}}

Commande « tts » (une vidéo) :
  {"mode": "tts", "voice_id": "...", "model_id": "...", "reglages": {...},
   "beats": ["phrase 1", "phrase 2", ...]}
  → sorties/<nom>/bNNN.mp3 + bNNN.json (minutage mot à mot : [[t0, t1, "mot"], ...])
"""
import base64, json, os, sys, time, urllib.request, urllib.parse, urllib.error

API = 'https://api.elevenlabs.io/v1'
CLE = os.environ.get('ELEVENLABS_API_KEY', '')
AZ_CLE = os.environ.get('AZURE_SPEECH_KEY', '')
AZ_REGION = os.environ.get('AZURE_SPEECH_REGION', '')

# ------------------------------------------------------------------ Azure

import re
from xml.sax.saxutils import escape

SIGLES_MOTS = {'SPIVA', 'INSEE', 'CAC', 'NASDAQ', 'UNESCO', 'OCDE'}


def ssml(texte, voix, debit='+6%', hauteur='+0%', style=None, degre=None, langue='fr-FR'):
    t = escape(texte)
    t = re.sub(r'\b([A-Z]{2,5})\b', lambda m: m.group(1) if m.group(1) in SIGLES_MOTS
               else f'<say-as interpret-as="characters">{m.group(1)}</say-as>', t)
    corps = f'<prosody rate="{debit}" pitch="{hauteur}">{t}</prosody>'
    if style:
        corps = f'<mstts:express-as style="{style}"' + (f' styledegree="{degre}"' if degre else '') + f'>{corps}</mstts:express-as>'
    return ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xmlns:mstts="https://www.w3.org/2001/mstts" '
            f'xml:lang="{langue}"><voice name="{voix}">{corps}</voice></speak>')


def azure_tts(doc_ssml):
    import azure.cognitiveservices.speech as sdk
    cfg = sdk.SpeechConfig(subscription=AZ_CLE, region=AZ_REGION)
    cfg.set_speech_synthesis_output_format(sdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3)
    synth = sdk.SpeechSynthesizer(speech_config=cfg, audio_config=None)
    mots = []

    def frontiere(evt):
        if evt.boundary_type == sdk.SpeechSynthesisBoundaryType.Word:
            d = evt.audio_offset / 1e7
            mots.append([round(d, 3), round(d + evt.duration.total_seconds(), 3), evt.text])
    synth.synthesis_word_boundary.connect(frontiere)
    for essai in range(4):
        r = synth.speak_ssml_async(doc_ssml).get()
        if r.reason == sdk.ResultReason.SynthesizingAudioCompleted:
            return r.audio_data, mots
        det = r.cancellation_details
        if essai < 3 and det and '429' in str(det.error_details):
            time.sleep(6 * (essai + 1)); mots.clear(); continue
        raise RuntimeError(f'Azure : {det.reason if det else r.reason} {det.error_details if det else ""}')


def azure_voix(langue='fr-FR'):
    url = f'https://{AZ_REGION}.tts.speech.microsoft.com/cognitiveservices/voices/list'
    req = urllib.request.Request(url, headers={'Ocp-Apim-Subscription-Key': AZ_CLE})
    with urllib.request.urlopen(req, timeout=60) as r:
        tout = json.loads(r.read())
    return [v for v in tout if v.get('Locale') == langue or langue in (v.get('SecondaryLocaleList') or [])]


def azure_casting(c, dossier):
    os.makedirs(dossier, exist_ok=True)
    rapport = []
    voix = azure_voix(c.get('langue', 'fr-FR'))
    if c.get('genre'):
        voix = [v for v in voix if v.get('Gender', '').lower() == c['genre'].lower()]
    for v in voix:
        nom = v['ShortName']
        variantes = [(None, '')]
        for st in (v.get('StyleList') or []):
            if st in c.get('styles', ['newscast', 'excited', 'cheerful', 'narration-professional']):
                variantes.append((st, '-' + st))
        for st, suffixe in variantes:
            try:
                audio, _ = azure_tts(ssml(c['texte'], nom, c.get('debit', '+6%'), style=st, degre=c.get('degre')))
                f = nom + suffixe + '.mp3'
                open(os.path.join(dossier, f), 'wb').write(audio)
                rapport.append({'fichier': f, 'voix': nom, 'style': st, 'genre': v.get('Gender'), 'ok': True})
            except Exception as e:
                rapport.append({'voix': nom, 'style': st, 'ok': False, 'erreur': str(e)[:300]})
    json.dump(rapport, open(os.path.join(dossier, 'rapport.json'), 'w'), ensure_ascii=False, indent=1)


def azure_production(c, dossier):
    os.makedirs(dossier, exist_ok=True)
    for i, txt in enumerate(c['beats']):
        cible = os.path.join(dossier, f'b{i:03d}.mp3')
        if os.path.exists(cible):
            continue
        audio, mots = azure_tts(ssml(txt, c['voix'], c.get('debit', '+6%'), c.get('hauteur', '+0%'), c.get('style'), c.get('degre')))
        open(cible, 'wb').write(audio)
        json.dump(mots, open(os.path.join(dossier, f'b{i:03d}.json'), 'w'), ensure_ascii=False)
        print(f'beat {i + 1}/{len(c["beats"])}', flush=True)



def appel(methode, chemin, corps=None, params=None, brut=False):
    url = API + chemin + ('?' + urllib.parse.urlencode(params, doseq=True) if params else '')
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=data, method=methode,
                                 headers={'xi-api-key': CLE, 'Content-Type': 'application/json', 'Accept': '*/*'})
    for essai in range(4):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                contenu = r.read()
                return contenu if brut else json.loads(contenu or b'{}')
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors='replace')[:500]
            if e.code in (429, 500, 502, 503) and essai < 3:
                time.sleep(5 * (essai + 1))
                continue
            raise RuntimeError(f'{methode} {chemin} -> {e.code} {msg}')


def mots_depuis_alignement(al):
    chars = al['characters']
    t0s, t1s = al['character_start_times_seconds'], al['character_end_times_seconds']
    mots, cur, deb, fin = [], '', None, None
    for c, a, b in zip(chars, t0s, t1s):
        if c.isspace():
            if cur:
                mots.append([round(deb, 3), round(fin, 3), cur])
            cur, deb = '', None
            continue
        if deb is None:
            deb = a
        cur += c
        fin = b
    if cur:
        mots.append([round(deb, 3), round(fin, 3), cur])
    return mots


def tts(voice_id, texte, model_id, reglages, prev=None, suiv=None):
    corps = {'text': texte, 'model_id': model_id, 'voice_settings': reglages or {}}
    if prev:
        corps['previous_text'] = prev
    if suiv:
        corps['next_text'] = suiv
    r = appel('POST', f'/text-to-speech/{voice_id}/with-timestamps', corps, {'output_format': 'mp3_44100_128'})
    return base64.b64decode(r['audio_base64']), mots_depuis_alignement(r.get('alignment') or r['normalized_alignment'])


def telecharger(url, chemin):
    with urllib.request.urlopen(url, timeout=60) as r:
        open(chemin, 'wb').write(r.read())


def casting(c, dossier):
    os.makedirs(os.path.join(dossier, 'apercus'), exist_ok=True)
    vues, liste = set(), []
    for terme in c.get('recherche', ['']):
        params = {'language': c.get('langue', 'fr'), 'page_size': 30, 'sort': 'cloned_by_count'}
        if terme:
            params['search'] = terme
        if c.get('genre'):
            params['gender'] = c['genre']
        r = appel('GET', '/shared-voices', params=params)
        for v in r.get('voices', []):
            if v['voice_id'] in vues:
                continue
            vues.add(v['voice_id'])
            liste.append({k: v.get(k) for k in ('voice_id', 'public_owner_id', 'name', 'gender', 'age', 'accent',
                                                 'descriptive', 'use_case', 'category', 'description', 'preview_url',
                                                 'cloned_by_count', 'language')})
    liste = liste[:c.get('max', 12)]
    for v in liste:
        if v.get('preview_url'):
            try:
                telecharger(v['preview_url'], os.path.join(dossier, 'apercus', v['voice_id'] + '.mp3'))
            except Exception as e:
                v['erreur_apercu'] = str(e)
    json.dump(liste, open(os.path.join(dossier, 'voix.json'), 'w'), ensure_ascii=False, indent=1)


def ajouter_voix(v):
    """Ajoute une voix de la bibliothèque partagée au compte (nécessaire pour l'utiliser)."""
    mes = appel('GET', '/voices').get('voices', [])
    if any(m['voice_id'] == v['voice_id'] for m in mes):
        return v['voice_id']
    r = appel('POST', f"/voices/add/{v['public_owner_id']}/{v['voice_id']}", {'new_name': v.get('nom') or v['voice_id']})
    return r.get('voice_id', v['voice_id'])


def essai(c, dossier):
    os.makedirs(dossier, exist_ok=True)
    rapport = []
    for v in c['voix']:
        try:
            vid = ajouter_voix(v) if v.get('public_owner_id') else v['voice_id']
            audio, mots = tts(vid, c['texte'], c.get('model_id', 'eleven_multilingual_v2'), c.get('reglages'))
            nom = (v.get('nom') or vid).replace('/', '-')
            open(os.path.join(dossier, nom + '.mp3'), 'wb').write(audio)
            rapport.append({'nom': nom, 'voice_id': vid, 'ok': True})
        except Exception as e:
            rapport.append({'nom': v.get('nom'), 'voice_id': v.get('voice_id'), 'ok': False, 'erreur': str(e)})
    json.dump(rapport, open(os.path.join(dossier, 'rapport.json'), 'w'), ensure_ascii=False, indent=1)


def production(c, dossier):
    os.makedirs(dossier, exist_ok=True)
    beats = c['beats']
    for i, txt in enumerate(beats):
        cible = os.path.join(dossier, f'b{i:03d}.mp3')
        if os.path.exists(cible):
            continue
        prev = ' '.join(beats[max(0, i - 2):i]) or None
        suiv = beats[i + 1] if i + 1 < len(beats) else None
        audio, mots = tts(c['voice_id'], txt, c.get('model_id', 'eleven_multilingual_v2'), c.get('reglages'), prev, suiv)
        open(cible, 'wb').write(audio)
        json.dump(mots, open(os.path.join(dossier, f'b{i:03d}.json'), 'w'), ensure_ascii=False)
        print(f'beat {i + 1}/{len(beats)}', flush=True)


def main():
    os.makedirs('sorties', exist_ok=True)
    for f in sorted(os.listdir('commandes')):
        if not f.endswith('.json'):
            continue
        nom = f[:-5]
        chemin = os.path.join('commandes', f)
        c = json.load(open(chemin))
        if c.get('statut') == 'traitée':
            continue
        dossier = os.path.join('sorties', nom)
        try:
            fournisseur = c.get('fournisseur', 'azure')
            if fournisseur == 'azure' and not (AZ_CLE and AZ_REGION):
                raise RuntimeError('Secrets AZURE_SPEECH_KEY / AZURE_SPEECH_REGION absents (Settings > Secrets and variables > Actions).')
            if fournisseur == 'elevenlabs' and not CLE:
                raise RuntimeError('Secret ELEVENLABS_API_KEY absent (Settings > Secrets and variables > Actions).')
            table = {('azure', 'casting'): azure_casting, ('azure', 'tts'): azure_production,
                     ('elevenlabs', 'casting'): casting, ('elevenlabs', 'essai'): essai, ('elevenlabs', 'tts'): production}
            table[(fournisseur, c['mode'])](c, dossier)
            c['statut'] = 'traitée'
        except Exception as e:
            c['statut'] = 'erreur'
            c['erreur'] = str(e)[:800]
            print('ERREUR', nom, e, flush=True)
        c['traitee_le'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        json.dump(c, open(chemin, 'w'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
