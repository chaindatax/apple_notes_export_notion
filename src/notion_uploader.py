"""
Interaction avec l'API Notion :
- Upload d'images via l'endpoint file_uploads
- Création d'entrées dans une base de données Notion existante
"""

import time
from pathlib import Path
from typing import Optional

import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"  # version stable ; file_uploads supporte toutes les versions

# Limite : 100 blocs par appel API
BLOCKS_PER_REQUEST = 100


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _check_response(resp: requests.Response, context: str) -> dict:
    if not resp.ok:
        raise RuntimeError(
            f"[Notion API] Erreur lors de {context} (HTTP {resp.status_code}): {resp.text}"
        )
    return resp.json()


def upload_image(image_path: Path, token: str) -> Optional[str]:
    """
    Upload une image vers Notion via l'API file_uploads.

    Étape 1 : créer l'objet upload
    Étape 2 : envoyer le contenu du fichier
    Retourne le file_upload_id ou None en cas d'erreur.
    """
    if not image_path or not image_path.exists():
        print(f"  [upload] Fichier introuvable : {image_path}")
        return None

    print(f"  [upload] Upload de {image_path.name} ({image_path.stat().st_size} octets)…")

    # Étape 1 : créer l'objet file_upload
    resp = requests.post(
        f"{NOTION_API_BASE}/file_uploads",
        headers=_headers(token),
        json={},
    )
    print(f"  [upload] Étape 1 (create) → HTTP {resp.status_code}")
    try:
        data = _check_response(resp, f"création file_upload pour {image_path.name}")
    except RuntimeError as e:
        print(f"  [upload] ERREUR : {e}")
        return None

    file_upload_id = data.get("id")
    upload_url = data.get("upload_url")

    if not file_upload_id or not upload_url:
        print(f"  [upload] Réponse inattendue (pas d'id/upload_url) : {data}")
        return None

    # Étape 2 : envoyer le contenu du fichier en multipart
    mime_type = _guess_mime(image_path)
    with open(image_path, "rb") as f:
        upload_resp = requests.post(
            upload_url,
            files={"file": (image_path.name, f, mime_type)},
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_VERSION,
            },
        )
    print(f"  [upload] Étape 2 (send file) → HTTP {upload_resp.status_code}")
    if not upload_resp.ok:
        print(f"  [upload] ERREUR upload : {upload_resp.text[:300]}")
        return None

    print(f"  [upload] OK : {image_path.name} → id={file_upload_id}")
    return file_upload_id


def _guess_mime(path: Path) -> str:
    ext = path.suffix.lower()
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".heic": "image/heic",
        ".heif": "image/heif",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }.get(ext, "application/octet-stream")


def create_database_entry(
    database_id: str,
    title: str,
    blocks: list[dict],
    token: str,
    extra_properties: Optional[dict] = None,
) -> str:
    """
    Crée une nouvelle entrée dans une base de données Notion.

    Args:
        database_id: ID de la base de données cible
        title: Titre de la page (propriété Name/title)
        blocks: Liste de blocs Notion à ajouter comme contenu
        token: Token d'intégration Notion
        extra_properties: Propriétés supplémentaires à définir (optionnel)

    Returns:
        ID de la page créée
    """
    # Propriétés minimales : le titre
    properties = {
        "Name": {
            "title": [{"text": {"content": title}}]
        }
    }
    if extra_properties:
        properties.update(extra_properties)

    # On envoie les 100 premiers blocs à la création, le reste par PATCH
    first_batch = blocks[:BLOCKS_PER_REQUEST]
    remaining = blocks[BLOCKS_PER_REQUEST:]

    payload = {
        "parent": {"database_id": database_id},
        "properties": properties,
        "children": first_batch,
    }

    resp = requests.post(
        f"{NOTION_API_BASE}/pages",
        headers=_headers(token),
        json=payload,
    )
    data = _check_response(resp, f"création de la page '{title}'")
    page_id = data["id"]
    print(f"  [notion] Page créée : '{title}' ({page_id})")

    # Ajout des blocs supplémentaires si > 100
    if remaining:
        _append_blocks_in_batches(page_id, remaining, token)

    return page_id


def _append_blocks_in_batches(page_id: str, blocks: list[dict], token: str) -> None:
    """Ajoute des blocs à une page en lots de 100."""
    for i in range(0, len(blocks), BLOCKS_PER_REQUEST):
        batch = blocks[i:i + BLOCKS_PER_REQUEST]
        resp = requests.patch(
            f"{NOTION_API_BASE}/blocks/{page_id}/children",
            headers=_headers(token),
            json={"children": batch},
        )
        _check_response(resp, f"ajout de blocs (lot {i // BLOCKS_PER_REQUEST + 2})")
        # Respecter le rate limit Notion (3 req/s par intégration)
        time.sleep(0.35)
