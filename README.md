# Apple Notes → Notion Export

Exporte les notes d'un dossier Apple Notes vers une base de données Notion, en préservant le contenu texte, les images et les dessins Apple Pencil.

## Pourquoi ce projet ?

Apple Notes est pratique pour la prise de notes rapide, notamment sur iPad avec l'Apple Pencil. Mais il est difficile d'y organiser, partager ou retrouver des informations sur le long terme. Notion offre un meilleur espace de travail collaboratif avec des bases de données structurées.

Ce script fait le pont entre les deux : il lit directement la base SQLite d'Apple Notes, extrait le contenu et les médias, puis crée une entrée Notion par note avec le texte, les images et les dessins reconstitués.

## Fonctionnalités

- 📝 Export du contenu texte des notes
- 🖼️ Images standard (JPEG, PNG, HEIC…) uploadées vers Notion
- ✏️ Dessins Apple Pencil extraits via AppleScript et uploadés vers Notion
- 📅 Date de dernière modification conservée dans la database Notion
- 🔍 Mode `--dry-run` pour vérifier sans toucher à Notion

## Prérequis

- macOS avec Apple Notes
- Python 3.13+
- Un token d'intégration Notion et une database cible
- **Accès complet au disque** accordé au terminal (voir ci-dessous)

## Accès complet au disque

Apple protège la base de données de Notes (`~/Library/Group Containers/group.com.apple.notes/NoteStore.sqlite`) via le mécanisme **TCC** (*Transparency, Consent and Control*) de macOS. Ce système empêche toute application - y compris les scripts Python lancés depuis un terminal - d'accéder aux données sensibles sans autorisation explicite de l'utilisateur.

Sans cette permission, toute tentative de lecture du fichier SQLite se solde par une erreur `unable to open database file`, même si le fichier est techniquement lisible par l'utilisateur courant.

Pour accorder l'accès :

> **Paramètres système → Confidentialité et sécurité → Accès complet au disque**  
> Cliquer sur **+** et ajouter l'application Terminal (ou iTerm2, VS Code, etc.) utilisée pour lancer le script.

Un redémarrage du terminal est nécessaire pour que la permission prenne effet.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditer .env avec le token Notion et l'ID de la database
```

## Usage

```bash
# Vérifier sans modifier Notion
python export.py --dry-run

# Lancer l'export
python export.py

# Exporter un autre dossier
python export.py --folder "MonDossier"

# Exporter sans les images
python export.py --skip-images
```

## Structure de la database Notion attendue

| Propriété | Type   |
|-----------|--------|
| `Name`    | Titre  |
| `date`    | Date   |
