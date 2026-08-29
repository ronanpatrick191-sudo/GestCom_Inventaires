import os
# Module standard Python pour lire les variables d'environnement du système.

from dotenv import load_dotenv
# Fonction qui lit le fichier .env et charge son contenu dans les variables d'environnement.
from pyramid.config import Configurator
# Classe principale de Pyramid : sert à construire/configurer l'application (routes, includes...).

load_dotenv()
# Charge immédiatement le fichier .env (à la racine du projet) au démarrage du programme,
# pour que os.environ.get(...) plus bas puisse retrouver les identifiants secrets.


def main(global_config, **settings):
    """Point d'entrée principal de GestCom — Pyramid démarre ici."""
    # Cette fonction est appelée par pserve (voir "main = GestCom:main" dans pyproject.toml).
    # global_config : réglages globaux du fichier .ini (non utilisés ici).
    # **settings : tous les réglages de la section [app:main] du fichier development.ini.

    # Identifiants SMTP / paiements mobiles chargés depuis .env (jamais depuis
    # le .ini versionné). Tant que les clés Orange/MTN ne sont pas définies,
    # le service de paiement mobile bascule automatiquement en mode démo.
    for cle_ini, var_env in [
        # Liste de paires (nom de réglage Pyramid, nom de variable d'environnement).
        ('sqlalchemy.url', 'DATABASE_URL'),
        # URL complète de connexion MySQL. Le development.ini versionné ne contient
        # qu'un exemple sans vrai mot de passe ; la vraie valeur vient de .env et
        # écrase la ligne du .ini ici, au démarrage.
        ('acces.utilisateur', 'ACCES_UTILISATEUR'),
        # Identifiant unique de connexion à l'application (protection niveau A).
        ('acces.motdepasse',  'ACCES_MOTDEPASSE'),
        # Mot de passe unique associé. Sans lui, l'application est ouverte à tous
        # (voir securite.py) — DOIT être défini en production.
        ('smtp.user',     'SMTP_USER'),
        # Adresse email Gmail utilisée pour envoyer les alertes de stock.
        ('smtp.password', 'SMTP_PASSWORD'),
        # Mot de passe d'application Gmail associé à ce compte.
        ('smtp.dest',     'SMTP_DEST'),
        # Adresse email du commerçant qui doit recevoir les alertes.
        ('orange_money.api_key',    'ORANGE_MONEY_API_KEY'),
        # Clé API pour appeler le vrai service Orange Money (si disponible).
        ('orange_money.merchant_id','ORANGE_MONEY_MERCHANT_ID'),
        # Identifiant marchand Orange Money (si disponible).
        ('mtn_momo.api_key',        'MTN_MOMO_API_KEY'),
        # Clé API pour appeler le vrai service MTN MoMo (si disponible).
        ('mtn_momo.subscription_key','MTN_MOMO_SUBSCRIPTION_KEY'),
        # Clé d'abonnement MTN MoMo (si disponible).
    ]:
        valeur = os.environ.get(var_env)
        # Cherche la variable d'environnement correspondante ; renvoie None si elle n'existe pas.
        if valeur:
            # Si une valeur a bien été trouvée dans .env...
            settings[cle_ini] = valeur
            # ...on l'ajoute aux réglages Pyramid sous le nom attendu (ex: "smtp.user").

    config = Configurator(settings=settings)
    # Crée l'objet de configuration principal de Pyramid avec tous les réglages rassemblés.

    # ── Extensions Pyramid ──
    config.include('pyramid_jinja2')
    # Active le moteur de templates Jinja2 (fichiers .jinja2 dans templates/).
    config.include('.securite')         # protection d'accès (mot de passe unique)
    # Ajoute le tween qui exige l'identifiant/mot de passe ACCES_* avant toute page.
    config.include('.main_models')      # connexion MySQL via SQLAlchemy
    # Exécute la fonction includeme() de main_models.py : prépare la connexion à la base MySQL.

    # ── Fichiers statiques (CSS, images) ──
    config.add_static_view('static', 'GestCom:static', cache_max_age=3600)
    # Rend accessible le dossier GestCom/static/ via l'URL /static/,
    # avec mise en cache d'1 heure (3600 secondes) côté navigateur.

    # ── Routes ──────────────────────────────────────────────────────
    # Une "route" relie une URL à un nom, utilisé ensuite dans views.py avec @view_config.
    # Accueil
    config.add_route('home',      '/')
    # Route "home" → page d'accueil à l'adresse "/".

    # Dashboard
    config.add_route('dashboard', '/dashboard')
    # Route "dashboard" → tableau de bord à l'adresse "/dashboard".

    # Inventaire — page "Produits" (catalogue + CRUD)
    config.add_route('inventaire',      '/inventaire')
    # Route "inventaire" → liste des produits.
    config.add_route('produit_ajouter', '/inventaire/ajouter')
    # Route "produit_ajouter" → formulaire/traitement d'ajout d'un produit.
    config.add_route('produit_modifier','/inventaire/modifier/{id}')
    # Route "produit_modifier" → modification d'un produit ; {id} est un paramètre dynamique.
    config.add_route('produit_supprimer','/inventaire/supprimer/{id}')
    # Route "produit_supprimer" → suppression d'un produit identifié par {id}.

    # Stock — niveaux, valeur, ruptures
    config.add_route('stock', '/stock')
    # Route "stock" → page d'état des stocks.
    config.add_route('stock_alerte_groupee', '/stock/alerte-email')
    # Route "stock_alerte_groupee" → envoi d'un email groupé listant toutes les ruptures.

    # Rapport financier
    config.add_route('rapport', '/rapport')
    # Route "rapport" → page des statistiques financières (CA, profit, tendance).

    # Recherche globale (topbar)
    config.add_route('recherche', '/recherche')
    # Route "recherche" → résultats de recherche déclenchés depuis la barre du haut.

    # Caisse / Ventes
    config.add_route('caisse',            '/caisse')
    # Route "caisse" → page de vente (point de caisse).
    config.add_route('vente_enregistrer', '/caisse/vendre')
    # Route "vente_enregistrer" → traitement d'une vente (enregistre la transaction).
    config.add_route('caisse_mtn',        '/caisse/mtn/payer')
    # Route "caisse_mtn" → déclenche un paiement MTN MoMo.
    config.add_route('caisse_mtn_verif',  '/caisse/mtn/verifier/{ref_id}')
    # Route "caisse_mtn_verif" → vérifie le statut d'un paiement MTN identifié par {ref_id}.
    config.add_route('caisse_orange',       '/caisse/orange/payer')
    # Route "caisse_orange" → déclenche un paiement Orange Money.
    config.add_route('caisse_orange_verif', '/caisse/orange/verifier/{ref_id}')
    # Route "caisse_orange_verif" → vérifie le statut d'un paiement Orange identifié par {ref_id}.

    # Alertes
    config.add_route('alertes',          '/alertes')
    # Route "alertes" → liste des alertes de stock.
    config.add_route('alerte_lire',      '/alertes/lire/{id}')
    # Route "alerte_lire" → marque une alerte comme lue.
    config.add_route('alerte_email_test','/alertes/test-email')
    # Route "alerte_email_test" → envoie un email de test pour vérifier la config SMTP.
    # ────────────────────────────────────────────────────────────────

    config.scan('.views')   # Pyramid découvre toutes les vues automatiquement
    # Parcourt le fichier views.py et enregistre toutes les fonctions marquées @view_config,
    # en les reliant à leurs routes respectives.
    return config.make_wsgi_app()
    # Construit et renvoie l'application WSGI finale, prête à être servie par waitress.
