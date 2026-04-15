#!/usr/bin/env python3
"""
Export des notes Apple Notes (dossier B4B) vers une base de données Notion.

Usage:
    python export.py
    python export.py --folder "B4B" --dry-run
    python export.py --folder "B4B" --skip-images

Configuration via .env :
    NOTION_TOKEN         : Token d'intégration Notion
    NOTION_DATABASE_ID   : ID de la base de données cible
    NOTES_FOLDER         : Nom du dossier Apple Notes (défaut : B4B)
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from src.notes_reader import get_notes_from_folder
from src.html_converter import html_to_notion_blocks
from src.notion_uploader import upload_image, create_database_entry


def main():
    parser = argparse.ArgumentParser(description="Export Apple Notes → Notion Database")
    parser.add_argument("--folder", default=None, help="Dossier Apple Notes à exporter")
    parser.add_argument("--dry-run", action="store_true", help="Affiche ce qui serait exporté sans rien créer dans Notion")
    parser.add_argument("--skip-images", action="store_true", help="Ignore les images (texte uniquement)")
    args = parser.parse_args()

    # Chargement de la configuration
    token = os.getenv("NOTION_TOKEN")
    database_id = os.getenv("NOTION_DATABASE_ID")
    folder_name = args.folder or os.getenv("NOTES_FOLDER", "B4B")

    if not token:
        print("ERREUR : NOTION_TOKEN manquant. Copiez .env.example en .env et remplissez-le.")
        sys.exit(1)
    if not database_id and not args.dry_run:
        print("ERREUR : NOTION_DATABASE_ID manquant. Copiez .env.example en .env et remplissez-le.")
        sys.exit(1)

    print(f"Dossier Apple Notes : '{folder_name}'")
    print(f"Base de données Notion : {database_id or '(dry-run)'}")
    print()

    # Lecture des notes
    try:
        notes = get_notes_from_folder(folder_name)
    except (ImportError, FileNotFoundError) as e:
        print(f"ERREUR : {e}")
        sys.exit(1)

    if not notes:
        print(f"Aucune note trouvée dans le dossier '{folder_name}'.")
        sys.exit(0)

    print(f"\n{len(notes)} note(s) à exporter :\n")

    success = 0
    errors = 0

    for i, note in enumerate(notes, 1):
        print(f"[{i}/{len(notes)}] '{note.title}'")
        images = note.image_attachments
        print(f"  Images : {len(images)}")

        if args.dry_run:
            blocks = html_to_notion_blocks(note.content, ["<dry-run-id>"] * len(images))
            print(f"  Blocs Notion générés : {len(blocks)}")
            if images:
                for img in images:
                    print(f"  Image : {img.filename} | mime={img.mime_type!r} | path={img.file_path}")
            continue

        try:
            # 1. Upload des images
            image_upload_ids = []
            if not args.skip_images:
                if images:
                    print(f"  Upload de {len(images)} image(s)…")
                for att in images:
                    if att.file_path:
                        fid = upload_image(att.file_path, token)
                        image_upload_ids.append(fid or "")
                    else:
                        print(f"  [!] Image sans chemin local : {att.filename} ({att.uuid})")
                        image_upload_ids.append("")

            # Filtrer les IDs vides (images non uploadées) pour ne pas créer de blocs invalides
            valid_ids = [fid for fid in image_upload_ids if fid]
            print(f"  Images uploadées avec succès : {len(valid_ids)}/{len(images)}")

            # 2. Conversion HTML → blocs Notion
            blocks = html_to_notion_blocks(note.content, valid_ids)
            print(f"  Blocs Notion : {len(blocks)}")

            # 3. Création de l'entrée dans la database
            create_database_entry(
                database_id=database_id,
                title=note.title,
                blocks=blocks,
                token=token,
                modification_date=note.modification_date,
            )
            success += 1

        except Exception as e:
            print(f"  ERREUR lors de l'export de '{note.title}' : {e}")
            errors += 1

    print(f"\nTerminé : {success} exportée(s), {errors} erreur(s).")


if __name__ == "__main__":
    main()
