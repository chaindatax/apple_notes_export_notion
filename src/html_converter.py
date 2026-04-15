"""
Conversion du contenu texte d'une note Apple Notes en blocs Notion.

Note : apple-notes-parser retourne le contenu en texte brut (pas HTML).
Les images sont des pièces jointes séparées, ajoutées à la fin du contenu.
"""

# Limite Notion : 2000 caractères par bloc de texte
NOTION_TEXT_LIMIT = 2000


def _rich_text(text: str) -> dict:
    return {
        "type": "text",
        "text": {"content": text[:NOTION_TEXT_LIMIT]},
        "annotations": {
            "bold": False,
            "italic": False,
            "code": False,
            "strikethrough": False,
            "underline": False,
            "color": "default",
        },
    }


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [_rich_text(text)] if text else []},
    }


def _image_block(file_upload_id: str) -> dict:
    return {
        "object": "block",
        "type": "image",
        "image": {
            "type": "file_upload",
            "file_upload": {"id": file_upload_id},
        },
    }


def html_to_notion_blocks(content: str, image_upload_ids: list[str]) -> list[dict]:
    """
    Convertit le contenu texte d'une note en blocs Notion.

    Le texte est converti ligne par ligne en paragraphes.
    Les images uploadées sont ajoutées à la fin.

    Args:
        content: Texte brut de la note (tel que retourné par apple-notes-parser)
        image_upload_ids: IDs de file_upload Notion pour les images de la note

    Returns:
        Liste de blocs Notion
    """
    blocks = []

    if content:
        lines = content.split("\n")
        prev_empty = False
        for line in lines:
            stripped = line.rstrip()
            is_empty = not stripped

            # Éviter deux blocs vides consécutifs
            if is_empty and prev_empty:
                continue

            blocks.append(_paragraph(stripped))
            prev_empty = is_empty

    # Ajouter les images à la fin
    for fid in image_upload_ids:
        if fid:
            blocks.append(_image_block(fid))

    return blocks
