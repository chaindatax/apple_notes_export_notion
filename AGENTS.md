# apple_notes_export

Script Python pour exporter les notes Apple Notes vers une base de données Notion.

## Stack

- Python 3.13, virtualenv dans `.venv/`
- `apple-notes-parser` — lecture directe de la base SQLite Apple Notes
- `requests` — appels API Notion (pas de SDK officiel)
- `beautifulsoup4` / `lxml` — parsing HTML (réservé à une utilisation future)
- `python-dotenv` — configuration via `.env`

## Structure

```
export.py                  # Point d'entrée CLI
src/
  notes_reader.py          # Lecture des notes depuis SQLite + extraction Pencil via AppleScript
  applescript_reader.py    # Extraction des dessins Apple Pencil (com.apple.paper) via osascript
  html_converter.py        # Conversion texte brut → blocs Notion
  notion_uploader.py       # Upload images (file_uploads API) + création entrées database
```

## Configuration

Copier `.env.example` en `.env` et remplir :

```
NOTION_TOKEN=secret_xxx          # Token d'intégration Notion
NOTION_DATABASE_ID=xxx           # ID de la database cible
NOTES_FOLDER=B4B                 # Dossier Apple Notes à exporter
```

La database Notion doit avoir :
- Une propriété **titre** nommée `Name`
- Une propriété **Date** nommée `date`

## Usage

```bash
# Installer les dépendances
pip install -r requirements.txt

# Tester sans modifier Notion
python export.py --dry-run

# Exporter
python export.py

# Autres options
python export.py --folder "AutreDossier"
python export.py --skip-images
```

## Permissions macOS requises

Le terminal doit avoir **Accès complet au disque** :
> Paramètres système → Confidentialité et sécurité → Accès complet au disque

Sans cette permission, la lecture de la base SQLite Apple Notes échoue.

## Fonctionnement des images

Deux sources d'images sont gérées :

1. **Images standard** (JPEG, PNG, HEIC…) — lues depuis le dossier Media Apple Notes via `apple-notes-parser` (`attachment.get_media_file_path()`)
2. **Dessins Apple Pencil** (`com.apple.paper`) — extraits via AppleScript (`body` HTML de la note) puis décodés depuis les data URIs base64

Les images sont uploadées vers Notion via l'API `POST /v1/file_uploads` (upload en deux étapes : création de l'objet puis envoi multipart), puis référencées dans des blocs `image` avec `"type": "file_upload"`.

## Points d'attention

- Les liens entre notes (`com.apple.paper` sans `has_data`) sont ignorés silencieusement
- Les notes iCloud non téléchargées localement n'ont pas de fichier media accessible
- L'API Notion limite à 100 blocs par requête — les lots supplémentaires sont envoyés par PATCH
- Rate limit Notion : délai de 350 ms entre les lots de blocs
