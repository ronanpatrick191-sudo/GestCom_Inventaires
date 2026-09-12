# -*- coding: utf-8 -*-
# Indique à Python que ce fichier peut contenir des caractères accentués (encodage UTF-8).
"""
scripts/init_db.py -- Initialisation de la base de donnees GestCom
Lance ce script UNE SEULE FOIS pour creer les tables et inserer des donnees de test.

Usage :
    cd GestCom_Inventaires
    python scripts/init_db.py
"""
import sys
# Module standard : accès aux paramètres d'exécution Python (arguments, chemins, sortie console...).
import os
# Module standard : manipulation de fichiers/dossiers et du système d'exploitation.

sys.stdout.reconfigure(encoding='utf-8')
# Force la console à afficher correctement les caractères accentués (é, à...) sur tous les systèmes.

# Ajouter le dossier parent au path Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Calcule le dossier racine du projet (parent de "scripts/") et l'ajoute à la liste des chemins
# où Python cherche les modules — sinon "from GestCom.main_models import Base" échouerait.

from sqlalchemy import create_engine, text
# create_engine : crée une connexion directe à MySQL (sans passer par Pyramid).
from sqlalchemy.orm import sessionmaker
# Fabrique de sessions de base de données, comme dans main_models.py.
from datetime import timedelta
# Pour générer des dates de ventes de test réparties sur les derniers jours.

from GestCom.temps import maintenant_cameroun
# Heure locale du Cameroun (UTC+1) : même référence de temps que l'application.
from GestCom.main_models import Base
# Classe de base commune, nécessaire pour créer les tables (Base.metadata.create_all).
from GestCom.models import Produit, Transaction, Alerte
# Les 3 modèles de données à peupler avec des exemples.

# -- Connexion MySQL ---------------------------------------------------------
# Priorité identique à l'application (voir GestCom/__init__.py) :
#   1. la variable d'environnement DATABASE_URL (chargée depuis .env à l'import
#      du package GestCom ci-dessus) — c'est la vraie URL, avec le vrai mot de passe ;
#   2. sinon, la ligne sqlalchemy.url de development.ini (qui ne contient qu'un
#      mot de passe d'EXEMPLE et échouerait à se connecter en l'état).
DATABASE_URL = os.environ.get('DATABASE_URL')
# Variable qui contiendra l'adresse de connexion à la base de données.

if DATABASE_URL:
    print("[OK] URL MySQL lue depuis DATABASE_URL (.env)")
else:
    try:
        import configparser
        # Module standard qui sait lire les fichiers .ini.
        ini_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'GestCom', 'config', 'development.ini'
        )
        # Construit le chemin complet vers GestCom/config/development.ini.
        cfg = configparser.ConfigParser()
        # Crée un lecteur de fichier .ini.
        cfg.read(ini_path)
        # Charge le contenu du fichier.
        DATABASE_URL = cfg['app:main']['sqlalchemy.url']
        # Récupère la ligne "sqlalchemy.url" dans la section [app:main] (la même que Pyramid utilise).
        print("[!] DATABASE_URL absente de .env — repli sur development.ini")
        print("[!] (mot de passe d'exemple : la connexion echouera probablement)")
    except Exception as e:
        # Si le fichier .ini est introuvable ou mal formé...
        print(f"[!] Impossible de lire development.ini : {e}")
        print("[!] Utilisation de la valeur par defaut : root sans mot de passe")
        DATABASE_URL = "mysql+pymysql://root:@localhost/gestcom_db"
        # ...on utilise une valeur de secours pour ne pas bloquer le script.

print(f"[>] Connexion a : {DATABASE_URL}\n")
# Affiche l'adresse utilisée, pour que l'utilisateur puisse vérifier avant que ça échoue.

engine  = create_engine(DATABASE_URL, echo=False)
# Crée le moteur de connexion à MySQL ; echo=False = ne pas afficher chaque requête SQL exécutée.
Session = sessionmaker(bind=engine)
# Prépare une fabrique de sessions reliée à ce moteur.


def reinitialiser_tables():
    """Remet la base a zero : supprime puis recree toutes les tables."""
    print("[!] SUPPRESSION des tables existantes (produits, transactions, alertes)...")
    Base.metadata.drop_all(engine)
    # Efface complètement les 3 tables et TOUTES leurs données : c'est le
    # "repartir de zéro". À ne lancer que sur la base de développement.
    print("[...] Recreation des tables...")
    Base.metadata.create_all(engine)
    # Recrée des tables vides produits/transactions/alertes.
    print("[OK] Base remise a zero : produits, transactions, alertes\n")


def inserer_produits(session):
    """Insere 8 produits typiques d'un commerce camerounais."""
    print("[...] Insertion des produits...")
    produits = [
        # Liste de produits de démonstration, avec des prix réalistes en FCFA.
        Produit(nom="Riz importe 25kg",      categorie="Alimentation",
                prix_achat=13000, prix_vente=17500, stock=42, seuil=10,  unite="sac"),
        Produit(nom="Huile de palme 5L",      categorie="Alimentation",
                prix_achat=6500,  prix_vente=9000,  stock=6,  seuil=15,  unite="bidon"),
        # Stock (6) déjà sous le seuil (15) : ce produit sera "en stock bas" dès le départ.
        Produit(nom="Farine de ble 1kg",      categorie="Alimentation",
                prix_achat=950,   prix_vente=1400,  stock=38, seuil=20,  unite="kg"),
        Produit(nom="Savon Omo 500g",         categorie="Hygiene",
                prix_achat=650,   prix_vente=950,   stock=0,  seuil=20,  unite="unite"),
        # Stock à 0 : ce produit est volontairement en rupture totale dès le départ.
        Produit(nom="Sucre cristallise 1kg",  categorie="Alimentation",
                prix_achat=500,   prix_vente=750,   stock=4,  seuil=10,  unite="kg"),
        Produit(nom="Tomate concentree",      categorie="Alimentation",
                prix_achat=220,   prix_vente=350,   stock=55, seuil=20,  unite="boite"),
        Produit(nom="Lait Gloria 400g",       categorie="Alimentation",
                prix_achat=900,   prix_vente=1300,  stock=0,  seuil=12,  unite="boite"),
        # Deuxième produit volontairement en rupture, pour tester les alertes.
        Produit(nom="Savon de Marseille",     categorie="Hygiene",
                prix_achat=400,   prix_vente=600,   stock=28, seuil=15,  unite="unite"),
    ]
    for p in produits:
        session.add(p)
        # Ajoute chaque produit à la session, un par un.
    session.flush()
    # Envoie les insertions à MySQL immédiatement pour que chaque produit obtienne son ID
    # (nécessaire pour créer ensuite les transactions et alertes qui les référencent).
    print(f"[OK] {len(produits)} produits inseres\n")
    return produits
    # Renvoie la liste des produits créés (avec leurs ID), utilisée par les fonctions suivantes.


def inserer_transactions(session, produits):
    """Insere des ventes de test sur les 3 derniers jours."""
    print("[...] Insertion des transactions...")
    now = maintenant_cameroun()
    # Heure actuelle au Cameroun, point de départ pour calculer les dates des ventes passées.
    ventes = [
        # Chaque vente référence un produit via son index dans la liste "produits" (0 = Riz...).
        Transaction(produit_id=produits[0].id, quantite=2, montant=35000,
                    mode_paiement='mtn',    date_vente=now - timedelta(hours=1)),
        # Vente d'il y a 1 heure, payée par MTN MoMo.
        Transaction(produit_id=produits[1].id, quantite=3, montant=27000,
                    mode_paiement='cash',   date_vente=now - timedelta(hours=2)),
        Transaction(produit_id=produits[2].id, quantite=5, montant=7000,
                    mode_paiement='orange', date_vente=now - timedelta(hours=3)),
        Transaction(produit_id=produits[5].id, quantite=10, montant=3500,
                    mode_paiement='cash',   date_vente=now - timedelta(hours=4)),
        Transaction(produit_id=produits[0].id, quantite=3, montant=52500,
                    mode_paiement='mtn',    date_vente=now - timedelta(days=1, hours=2)),
        # Vente d'hier.
        Transaction(produit_id=produits[3].id, quantite=6, montant=5700,
                    mode_paiement='cash',   date_vente=now - timedelta(days=1, hours=5)),
        Transaction(produit_id=produits[2].id, quantite=8, montant=11200,
                    mode_paiement='orange', date_vente=now - timedelta(days=2, hours=1)),
        # Vente d'avant-hier.
    ]
    for v in ventes:
        session.add(v)
        # Note : contrairement aux produits, ces transactions ne sont pas "flush" immédiatement ;
        # elles seront envoyées à MySQL avec le commit final dans le bloc principal ci-dessous.
    print(f"[OK] {len(ventes)} transactions inserees\n")


def inserer_alertes(session, produits):
    """Cree des alertes pour les produits en rupture."""
    print("[...] Insertion des alertes...")
    alertes = [
        # Alertes correspondant aux 2 produits mis volontairement en rupture (index 3 et 6),
        # et aux 2 produits en stock bas (index 1 et 4).
        Alerte(produit_id=produits[3].id,
               message="Stock epuise : Savon Omo 500g (0 unites)",
               type_alerte='rupture'),
        Alerte(produit_id=produits[6].id,
               message="Stock epuise : Lait Gloria 400g (0 boites)",
               type_alerte='rupture'),
        Alerte(produit_id=produits[1].id,
               message="Stock bas : Huile de palme 5L (6 bidons restants)",
               type_alerte='seuil_bas'),
        Alerte(produit_id=produits[4].id,
               message="Stock bas : Sucre cristallise (4 kg restants)",
               type_alerte='seuil_bas'),
    ]
    for a in alertes:
        session.add(a)
    print(f"[OK] {len(alertes)} alertes inserees\n")


if __name__ == '__main__':
    # Ce bloc ne s'exécute que si le fichier est lancé directement (python scripts/init_db.py),
    # pas s'il est importé depuis un autre fichier Python.
    print("=" * 50)
    # Affiche une ligne de 50 signes "=" pour délimiter visuellement le début du script.
    print("  GestCom -- Initialisation base de donnees")
    print("=" * 50 + "\n")

    reinitialiser_tables()
    # Étape 1 : repartir de zéro — supprimer et recréer les tables vides.

    session = Session()
    # Ouvre une nouvelle session de base de données pour insérer toutes les données de test.
    try:
        produits = inserer_produits(session)
        # Étape 2 : insère les 8 produits, récupère la liste avec leurs ID.
        inserer_transactions(session, produits)
        # Étape 3 : insère des ventes de test liées à ces produits.
        inserer_alertes(session, produits)
        # Étape 4 : insère des alertes de stock liées à ces produits.
        session.commit()
        # Valide définitivement toutes les insertions dans la base de données MySQL.
        print("=" * 50)
        print("[OK] Base de donnees GestCom initialisee !")
        print("[>] Lance maintenant :")
        print("    pserve GestCom/config/development.ini --reload")
        print("[>] Puis ouvre :")
        print("    http://localhost:6543/dashboard")
        print("=" * 50)
    except Exception as e:
        # Si une erreur survient à n'importe quelle étape ci-dessus...
        session.rollback()
        # ...on annule toutes les insertions en attente pour ne pas laisser la base à moitié remplie.
        print(f"[ERREUR] {e}")
        raise
        # On relance l'erreur pour que le script s'arrête avec un message d'erreur visible.
    finally:
        session.close()
        # Ferme proprement la session dans tous les cas (succès ou échec).
