"""
Extraction des dessins Apple Pencil via AppleScript.

L'API SQLite (apple-notes-parser) ne donne pas accès aux données com.apple.paper.
AppleScript retourne le body HTML de la note, dans lequel les dessins Pencil
apparaissent comme des <img src="data:image/png;base64,..."> inline.
"""

import base64
import re
import subprocess
import tempfile
from pathlib import Path


def get_note_html_body(applescript_id: str) -> str | None:
    """
    Récupère le corps HTML d'une note via son AppleScript ID.

    Args:
        applescript_id: ID de la forme "x-coredata://UUID/ICNote/pXXX"

    Returns:
        Corps HTML de la note, ou None en cas d'erreur
    """
    script = f"""
tell application "Notes"
    try
        set theNote to note id "{applescript_id}"
        return body of theNote
    on error errMsg
        return ""
    end try
end tell
"""
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    return result.stdout.strip()


def extract_pencil_drawings(html: str, note_title: str = "") -> list[Path]:
    """
    Extrait les dessins Pencil (base64 PNG) d'un corps HTML Apple Notes
    et les sauvegarde dans des fichiers temporaires.

    Args:
        html: Corps HTML retourné par AppleScript
        note_title: Utilisé pour nommer les fichiers (debug)

    Returns:
        Liste de Path vers les fichiers PNG temporaires créés
    """
    # Pattern pour les data URIs images dans le HTML
    pattern = re.compile(
        r'<img[^>]+src=["\']data:(image/[a-zA-Z+]+);base64,([A-Za-z0-9+/=\s]+)["\']',
        re.IGNORECASE | re.DOTALL,
    )

    tmp_dir = Path(tempfile.mkdtemp(prefix="apple_pencil_"))
    paths = []

    for i, match in enumerate(pattern.finditer(html)):
        mime_type = match.group(1).lower()
        b64_data = re.sub(r'\s+', '', match.group(2))  # supprimer les espaces/newlines

        try:
            image_data = base64.b64decode(b64_data)
        except Exception:
            continue

        ext = _mime_to_ext(mime_type)
        filename = f"drawing_{i + 1}{ext}"
        dest = tmp_dir / filename

        dest.write_bytes(image_data)
        paths.append(dest)

    return paths


def _mime_to_ext(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "image/tiff": ".tiff",
    }.get(mime_type, ".png")
