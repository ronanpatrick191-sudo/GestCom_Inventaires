# Contenu à COPIER-COLLER intégralement dans le fichier WSGI de PythonAnywhere
# (onglet Web → section "Code" → lien "WSGI configuration file").
# Remplace TONNOM par ton nom d'utilisateur PythonAnywhere avant de coller.
#
# Ce fichier n'est pas exécuté par GestCom lui-même : c'est PythonAnywhere qui
# l'exécute pour savoir comment démarrer l'application (voir deploy/PYTHONANYWHERE.md).

import sys
import os

# ── Chemin du projet sur le serveur ──────────────────────────
chemin_projet = '/home/TONNOM/GestCom_Inventaires'
if chemin_projet not in sys.path:
    sys.path.insert(0, chemin_projet)

# ── Démarrage de l'application Pyramid via production.ini ───
from pyramid.paster import get_app

application = get_app(
    os.path.join(chemin_projet, 'GestCom', 'config', 'production.ini'),
    'main',
)
