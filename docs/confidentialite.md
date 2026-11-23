# Privacy Policy — Régie Clips (YouTube API Client)

_Last updated: 23 November 2026_

**Régie Clips** is a private, internal tool operated by Thomas Kames. It publishes short vertical videos (YouTube Shorts) to a single YouTube channel owned by its operator. It has no other users.

## What the tool accesses
- **YouTube Data API v3 — `videos.insert` only**, with the OAuth scope `https://www.googleapis.com/auth/youtube.upload`, on the operator's own channel.
- The tool does not read, collect or store any data about YouTube viewers, other channels or other Google users.

## What the tool stores
- An OAuth refresh token for the operator's own channel, kept as an encrypted GitHub Actions secret. It is never shared.
- For each published Short: its title, description, YouTube video ID and publication date, kept in the operator's private records to avoid duplicate uploads.

## Sharing
No data obtained through YouTube API Services is sold, shared with third parties or used for advertising.

## Retention and deletion
Records are kept as long as the channel is operated. The operator can revoke the tool's access at any time from https://myaccount.google.com/permissions, which immediately disables uploads.

## Google privacy policy
This tool uses YouTube API Services. See the YouTube Terms of Service (https://www.youtube.com/t/terms) and the Google Privacy Policy (https://policies.google.com/privacy).

## Contact
Questions or removal requests: open an issue at https://github.com/TOOOmyui/YTB/issues or comment on the relevant video.

---

### Résumé en français
Outil interne et privé : il publie des Shorts sur une seule chaîne YouTube appartenant à son exploitant, par l'API YouTube (envoi de vidéos uniquement). Aucune donnée sur les spectateurs ou d'autres utilisateurs n'est collectée ; le jeton d'accès est conservé chiffré dans les secrets GitHub et révocable à tout moment depuis myaccount.google.com/permissions.
