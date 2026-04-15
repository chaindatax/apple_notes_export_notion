"""
Lecture des notes Apple Notes depuis la base SQLite.
Utilise apple-notes-parser pour accéder au contenu et aux pièces jointes.
"""

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Chemin par défaut vers la base de données Apple Notes
NOTES_DB_PATH = Path.home() / "Library" / "Group Containers" / "group.com.apple.notes" / "NoteStore.sqlite"


@dataclass
class NoteAttachment:
    uuid: str
    filename: str
    mime_type: str
    # Chemin vers le fichier sur disque (résolu via get_media_file_path ou save_to_file)
    file_path: Optional[Path] = None
    # Flag is_image tel que déterminé par apple-notes-parser (fiable même si mime_type est None)
    _is_image: bool = False

    @property
    def is_image(self) -> bool:
        if self._is_image:
            return True
        if self.mime_type and self.mime_type.startswith("image/"):
            return True
        # Fallback sur l'extension du fichier
        ext = Path(self.filename).suffix.lower() if self.filename else ""
        return ext in {".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".tiff", ".tif", ".webp", ".bmp"}


@dataclass
class Note:
    title: str
    content: str          # Texte brut de la note
    folder: str
    creation_date: object = None
    modification_date: object = None
    attachments: list[NoteAttachment] = field(default_factory=list)

    @property
    def image_attachments(self) -> list[NoteAttachment]:
        return [a for a in self.attachments if a.is_image]


def get_notes_from_folder(folder_name: str) -> list[Note]:
    """
    Retourne toutes les notes du dossier Apple Notes spécifié.

    Args:
        folder_name: Nom du dossier Apple Notes (ex: "B4B")

    Returns:
        Liste d'objets Note avec leur contenu texte et leurs pièces jointes
    """
    try:
        from apple_notes_parser import AppleNotesParser
    except ImportError:
        raise ImportError(
            "Le package apple-notes-parser n'est pas installé. "
            "Lancez: pip install apple-notes-parser"
        )

    if not NOTES_DB_PATH.exists():
        raise FileNotFoundError(
            f"Base de données Apple Notes introuvable : {NOTES_DB_PATH}\n"
            "Assurez-vous que l'application Notes est installée et a été ouverte au moins une fois."
        )

    try:
        parser = AppleNotesParser(str(NOTES_DB_PATH))
        # get_notes_by_folder filtre directement par nom de dossier (insensible à la casse)
        raw_notes = parser.get_notes_by_folder(folder_name)
    except Exception as e:
        if "unable to open database" in str(e) or "Failed to connect" in str(e):
            raise PermissionError(
                "Accès refusé à la base de données Apple Notes.\n\n"
                "Solution : accorder l'accès complet au disque à votre terminal :\n"
                "  Paramètres système → Confidentialité et sécurité\n"
                "  → Accès complet au disque → ajouter Terminal (ou iTerm2)\n\n"
                "Puis relancer le script."
            ) from e
        raise

    notes = []
    for raw in raw_notes:
        attachments = _load_attachments(raw)

        # Si la note contient des dessins Pencil (com.apple.paper), les extraire via AppleScript
        has_pencil = any(a.type_uti == "com.apple.paper" for a in (raw.attachments or []))
        if has_pencil and raw.applescript_id:
            pencil_attachments = _load_pencil_drawings(raw.applescript_id, raw.title or "")
            attachments.extend(pencil_attachments)

        notes.append(Note(
            title=raw.title or "Sans titre",
            content=raw.content or "",
            folder=raw.folder.name if raw.folder else folder_name,
            creation_date=raw.creation_date,
            modification_date=raw.modification_date,
            attachments=attachments,
        ))

    print(f"[notes_reader] {len(notes)} note(s) trouvée(s) dans le dossier '{folder_name}'")
    return notes


def _load_attachments(raw_note) -> list[NoteAttachment]:
    """Charge les pièces jointes fichier d'une note (images, docs) et résout leurs chemins.

    Les liens vers d'autres notes (note-to-note links) sont ignorés silencieusement —
    Apple Notes les stocke comme des attachments mais ce ne sont pas des fichiers.
    """
    result = []
    tmp_dir = None

    for att in (raw_note.attachments or []):
        # Ignorer les liens vers d'autres notes et les objets non-fichier
        # (type_uti contenant "note", "table", "drawing", "mention", etc.)
        uti = att.type_uti or ""
        if _is_note_link(uti):
            continue

        # Ne traiter que les attachments qui sont des fichiers réels
        if not (att.is_image or att.is_video or att.is_audio or att.is_document):
            # Tenter quand même si le MIME type ou l'extension suggère un fichier connu
            ext = att.file_extension or ""
            known_ext = {"jpg", "jpeg", "png", "gif", "heic", "heif", "tiff", "tif",
                         "webp", "bmp", "pdf", "mp4", "mov", "mp3", "m4a", "wav"}
            if ext not in known_ext:
                continue

        uuid = att.uuid or ""
        filename = att.filename if att.filename else att.get_suggested_filename()
        mime_type = att.mime_type or ""

        # Essai 1 : accès direct au fichier media sur disque
        file_path = att.get_media_file_path()

        # Essai 2 : extraction depuis le BLOB SQLite vers un fichier temporaire
        if file_path is None and att.has_data:
            if tmp_dir is None:
                tmp_dir = Path(tempfile.mkdtemp(prefix="apple_notes_export_"))
            dest = tmp_dir / (filename or f"att_{att.id}")
            if att.save_to_file(dest):
                file_path = dest

        if file_path is not None:
            result.append(NoteAttachment(
                uuid=uuid,
                filename=filename,
                mime_type=mime_type,
                file_path=Path(file_path),
                _is_image=bool(att.is_image),
            ))
        # else : fichier iCloud non téléchargé localement — on l'ignore silencieusement

    return result


# UTIs Apple Notes qui correspondent à des liens/objets non-fichier
_NON_FILE_UTIS = {
    "com.apple.paper",                        # lien vers une autre note
    "com.apple.notes.secure-body",
    "com.apple.notes.table",
    "com.apple.drawing",
    "com.apple.drawing.2",
    "com.apple.notes.inlinetextattachment",
    "com.apple.notes.mention",
    "com.apple.notes.link",
    "com.apple.smartfolderentry",
    "com.apple.notes.gallery",
    "com.apple.notes.referencedNote",
}


def _is_note_link(uti: str) -> bool:
    """Retourne True si l'UTI correspond à un lien ou objet interne Notes (pas un fichier)."""
    if not uti:
        return False
    if uti in _NON_FILE_UTIS:
        return True
    lower = uti.lower()
    return "secure-body" in lower or "inline" in lower or "mention" in lower


def _load_pencil_drawings(applescript_id: str, note_title: str) -> list[NoteAttachment]:
    """
    Extrait les dessins Apple Pencil d'une note via AppleScript.
    Retourne une liste de NoteAttachment (PNG temporaires).
    """
    from .applescript_reader import get_note_html_body, extract_pencil_drawings

    html = get_note_html_body(applescript_id)
    if not html:
        return []

    paths = extract_pencil_drawings(html, note_title)
    if not paths:
        return []

    print(f"  [pencil] {len(paths)} dessin(s) extrait(s) via AppleScript")
    return [
        NoteAttachment(
            uuid="",
            filename=p.name,
            mime_type="image/png",
            file_path=p,
            _is_image=True,
        )
        for p in paths
    ]
