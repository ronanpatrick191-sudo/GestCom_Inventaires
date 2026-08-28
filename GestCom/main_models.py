
"""
main_models.py — Configuration SQLAlchemy pour GestCom
Gère la connexion MySQL et la session de base de données.
Même style que ton projet Tetris/Mitarbeiter_Verwaltung.
"""
from sqlalchemy import engine_from_config
# Fonction qui construit un "moteur" de base de données à partir des réglages du fichier .ini.
from sqlalchemy.orm import sessionmaker, DeclarativeBase
# sessionmaker : fabrique des sessions (des "conversations" avec la base de données).
# DeclarativeBase : classe de base dont héritent tous les modèles (Produit, Transaction, Alerte).
import zope.sqlalchemy
# Bibliothèque qui relie les sessions SQLAlchemy au système de transactions de Pyramid.


# ── Base déclarative — toutes les tables héritent de cette classe ──
class Base(DeclarativeBase):
    pass
    # Classe vide : elle sert uniquement de "socle commun" pour que SQLAlchemy
    # sache que Produit, Transaction et Alerte (dans models.py) sont des tables.


def get_engine(settings, prefix='sqlalchemy.'):
    """Crée le moteur SQLAlchemy depuis development.ini."""
    return engine_from_config(settings, prefix)
    # Lit tous les réglages commençant par "sqlalchemy." (ex: sqlalchemy.url)
    # et construit l'objet "engine" qui sait se connecter physiquement à MySQL.


def get_session_factory(engine):
    """Crée la factory de sessions de base de données."""
    factory = sessionmaker()
    # Crée un "moule" à sessions, pas encore relié à une base de données.
    factory.configure(bind=engine)
    # Relie ce moule au moteur de connexion créé juste avant.
    return factory
    # Renvoie la factory prête à produire des sessions à la demande.


def get_tm_session(session_factory, transaction_manager, request=None):
    """
    Crée une session liée au gestionnaire de transactions.
    zope.sqlalchemy.register() est indispensable : sans lui, pyramid_tm
    ignore complètement cette session et ne fait jamais de commit — les
    ajouts/modifications restent invisibles après la fin de la requête.
    """
    db_session = session_factory()
    # Crée une nouvelle session de base de données (une connexion active) à partir de la factory.
    zope.sqlalchemy.register(db_session, transaction_manager=transaction_manager)
    # Enregistre cette session auprès du gestionnaire de transactions de Pyramid,
    # pour qu'un commit automatique ait lieu à la fin de chaque requête réussie.
    return db_session
    # Renvoie la session prête à l'emploi (utilisée ensuite comme request.dbsession).


def includeme(config):
    """
    Appelé par Pyramid via config.include('.main_models').
    Configure la connexion MySQL et ajoute request.dbsession.
    """
    settings = config.get_settings()
    # Récupère tous les réglages de l'application (venant du fichier .ini + .env).

    config.include('pyramid_tm')
    # Active la gestion automatique des transactions (commit/rollback) à chaque requête.
    config.include('pyramid_retry')
    # Active le mécanisme qui réessaye automatiquement une requête en cas d'erreur temporaire.

    # Créer le moteur de base de données
    engine = get_engine(settings)
    # Construit la connexion vers MySQL en utilisant les réglages sqlalchemy.url du .ini.

    # Importer les modèles pour que SQLAlchemy les connaisse
    from . import models  # noqa : F401 — nécessaire pour create_all
    # Cet import "silencieux" force Python à charger models.py, ce qui déclare les tables
    # Produit/Transaction/Alerte auprès de Base — sans ça, create_all() ci-dessous ne les verrait pas.

    # Créer toutes les tables si elles n'existent pas encore
    Base.metadata.create_all(engine)
    # Vérifie dans MySQL si les tables produits/transactions/alertes existent déjà ;
    # si non, il les crée automatiquement selon la structure définie dans models.py.

    # Créer la factory de sessions
    session_factory = get_session_factory(engine)
    # Prépare la fabrique de sessions réutilisable pour toute l'application.
    config.registry['db_session_factory'] = session_factory
    # Stocke cette factory dans le registre global de Pyramid, accessible partout dans l'app.

    # Ajouter request.dbsession — utilisé dans toutes les vues
    def db_session(request):
        return get_tm_session(
            session_factory,
            request.tm,
            request=request
        )
        # Crée une session liée à la transaction de la requête HTTP en cours (request.tm).

    config.add_request_method(db_session, 'dbsession', reify=True)
    # Ajoute un raccourci "request.dbsession" utilisable dans toutes les vues (views.py) ;
    # reify=True signifie que la session n'est créée qu'une seule fois par requête, puis réutilisée.
