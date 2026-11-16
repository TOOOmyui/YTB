"""Client minimal de l'API Twitch (Helix) — lecture seule, bibliothèque standard uniquement.

Identifiants lus dans l'environnement : TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
(application créée par le PDG sur dev.twitch.tv ; jamais écrits dans le dépôt).
"""
import json, os, time, urllib.parse, urllib.request, urllib.error

API = 'https://api.twitch.tv/helix'
AUTH = 'https://id.twitch.tv/oauth2/token'


class ErreurTwitch(RuntimeError):
    pass


class Twitch:
    def __init__(self, client_id=None, secret=None, ouvrir=None):
        self.client_id = client_id or os.environ.get('TWITCH_CLIENT_ID', '')
        self.secret = secret or os.environ.get('TWITCH_CLIENT_SECRET', '')
        self._ouvrir = ouvrir or self._http  # injectable pour les tests
        self._jeton = None

    @property
    def configure(self):
        return bool(self.client_id and self.secret)

    def _http(self, url, donnees=None, entetes=None):
        req = urllib.request.Request(url, data=donnees, headers=entetes or {})
        for essai in range(3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode('utf-8'))
            except urllib.error.HTTPError as e:
                if e.code == 429 and essai < 2:
                    time.sleep(5 * (essai + 1))
                    continue
                raise ErreurTwitch(f'HTTP {e.code} sur {url.split("?")[0]} : {e.read().decode("utf-8", "replace")[:200]}')
            except urllib.error.URLError as e:
                if essai < 2:
                    time.sleep(3)
                    continue
                raise ErreurTwitch(f'Réseau : {e.reason}')

    def jeton(self):
        if not self._jeton:
            if not self.configure:
                raise ErreurTwitch('TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET absents')
            corps = urllib.parse.urlencode({'client_id': self.client_id, 'client_secret': self.secret,
                                            'grant_type': 'client_credentials'}).encode()
            self._jeton = self._ouvrir(AUTH, corps, {})['access_token']
        return self._jeton

    def get(self, chemin, **params):
        q = urllib.parse.urlencode([(k, v) for k, vs in params.items() if vs is not None
                                    for v in (vs if isinstance(vs, (list, tuple)) else [vs])])
        return self._ouvrir(f'{API}/{chemin}?{q}', None,
                            {'Client-Id': self.client_id, 'Authorization': 'Bearer ' + self.jeton()})

    # ---------------------------------------------------------------- jeux
    def trouver_jeu(self, noms):
        """Renvoie (id, nom) de la première catégorie trouvée parmi `noms` (nom exact, puis recherche)."""
        for nom in noms:
            d = self.get('games', name=nom).get('data', [])
            if d:
                return d[0]['id'], d[0]['name']
        for nom in noms:
            for c in self.get('search/categories', query=nom, first=20).get('data', []):
                if c['name'].lower() in [n.lower() for n in noms]:
                    return c['id'], c['name']
        return None, None

    # ---------------------------------------------------------------- streamers
    def utilisateurs(self, logins):
        out = {}
        logins = [l.lower() for l in logins if l]
        for i in range(0, len(logins), 100):
            for u in self.get('users', login=logins[i:i + 100]).get('data', []):
                out[u['login'].lower()] = u
        return out

    # ---------------------------------------------------------------- clips
    def clips(self, debut, fin, jeu_id=None, diffuseur_id=None, pages=3):
        """Clips créés entre `debut` et `fin` (RFC 3339), triés par vues décroissantes par Twitch."""
        out, curseur = [], None
        for _ in range(pages):
            d = self.get('clips', game_id=None if diffuseur_id else jeu_id, broadcaster_id=diffuseur_id,
                         started_at=debut, ended_at=fin, first=100, after=curseur)
            out += d.get('data', [])
            curseur = (d.get('pagination') or {}).get('cursor')
            if not curseur:
                break
        return out
