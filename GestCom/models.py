"""
models.py — Modèles SQLAlchemy de GestCom
Contient toutes les tables : Produit, Transaction, Alerte.
Style : un seul fichier, comme Tetris/Mitarbeiter_Verwaltung.
"""
from sqlalchemy import (
    Column, Integer, String, Float,
    DateTime, ForeignKey, Text
)
# Column : définit une colonne de table. Integer/String/Float/DateTime/Text : types de données.
# ForeignKey : crée un lien vers l'identifiant d'une autre table (clé étrangère).
from sqlalchemy.orm import relationship
# Permet de naviguer facilement entre objets liés (ex: produit.transactions).
from .temps import maintenant_cameroun
# Génère l'heure locale du Cameroun (UTC+1) au moment de la création d'une ligne,
# pour que les dates stockées correspondent à ce que voit le commerçant, quel
# que soit le pays où tourne le serveur.

from .main_models import Base
# Importe la classe de base commune définie dans main_models.py : toutes les tables en héritent.


# ══════════════════════════════════════════════════════════════
# TABLE : produits
# Stocke tous les articles du magasin avec leurs prix et stock
# ══════════════════════════════════════════════════════════════
class Produit(Base):
    __tablename__ = 'produits'
    # Nom exact de la table créée dans MySQL.

    id          = Column(Integer, primary_key=True, autoincrement=True)
    # Identifiant unique auto-incrémenté (1, 2, 3...) : clé primaire de la table.
    nom         = Column(String(100), nullable=False)
    # Nom du produit, texte de 100 caractères max, obligatoire (nullable=False).
    categorie   = Column(String(50), default='')
    # Catégorie du produit (texte 50 caractères), vide par défaut si non précisée.
    prix_achat  = Column(Float, default=0.0)    # coût fournisseur en FCFA
    # Prix payé au fournisseur, nombre décimal, 0 par défaut.
    prix_vente  = Column(Float, nullable=False)  # prix client en FCFA
    # Prix vendu au client, obligatoire.
    stock       = Column(Integer, default=0)     # quantité en stock
    # Quantité actuellement disponible, 0 par défaut.
    seuil       = Column(Integer, default=10)    # seuil alerte rupture
    # En dessous de cette quantité, une alerte de stock bas est déclenchée.
    unite       = Column(String(20), default='unité')  # ex: kg, sac, bidon
    # Unité de mesure du produit (pièce, kg, sac...), "unité" par défaut.
    date_ajout  = Column(
        DateTime,
        default=maintenant_cameroun
    )
    # Date/heure de création automatique (heure du Cameroun), calculée au moment de l'ajout.

    # Relation : un produit peut avoir plusieurs transactions
    transactions = relationship(
        'Transaction',
        back_populates='produit',
        cascade='all, delete-orphan'
    )
    # Donne accès à produit.transactions (toutes les ventes de ce produit) ;
    # cascade='all, delete-orphan' : si le produit est supprimé, ses transactions le sont aussi.

    # ── Méthodes utiles ──────────────────────────────────────
    def marge_pct(self):
        """Retourne la marge bénéficiaire en pourcentage."""
        if self.prix_vente == 0:
            # Évite une division par zéro si le prix de vente n'est pas encore défini.
            return 0
        return round(
            (self.prix_vente - self.prix_achat) / self.prix_vente * 100
        )
        # Calcule : (bénéfice / prix de vente) * 100, arrondi à l'entier le plus proche.

    def est_en_rupture(self):
        """True si le stock est inférieur ou égal au seuil d'alerte."""
        return self.stock <= self.seuil
        # Renvoie Vrai/Faux selon que le stock a atteint (ou dépassé) le seuil critique.

    def statut_stock(self):
        """Retourne 'ok', 'bas', ou 'rupture' pour l'affichage."""
        if self.stock == 0:
            # Aucun exemplaire restant : rupture totale.
            return 'rupture'
        if self.stock <= self.seuil:
            # Il en reste, mais peu : stock bas, à réapprovisionner bientôt.
            return 'bas'
        return 'ok'
        # Stock suffisant, rien à signaler.

    def __repr__(self):
        return f"<Produit {self.nom!r} — stock: {self.stock}>"
        # Représentation textuelle utile pour le débogage (ex: dans la console Python).


# ══════════════════════════════════════════════════════════════
# TABLE : transactions
# Enregistre chaque vente effectuée en caisse
# ══════════════════════════════════════════════════════════════
class Transaction(Base):
    __tablename__ = 'transactions'
    # Nom exact de la table créée dans MySQL.

    id              = Column(Integer, primary_key=True, autoincrement=True)
    # Identifiant unique auto-incrémenté de la transaction.
    produit_id      = Column(
        Integer,
        ForeignKey('produits.id'),
        nullable=False
    )
    # Référence vers le produit vendu (correspond à Produit.id) ; obligatoire.
    quantite        = Column(Integer, nullable=False)
    # Nombre d'unités vendues lors de cette transaction.
    montant         = Column(Float, nullable=False)       # total FCFA
    # Montant total payé par le client pour cette vente, en FCFA.
    mode_paiement   = Column(String(20), default='cash')  # cash/orange/mtn
    # Moyen de paiement utilisé : "cash" par défaut, sinon "orange" ou "mtn".
    statut          = Column(String(20), default='paye')  # paye/en_attente
    # État du paiement : "paye" par défaut, ou "en_attente" pour un paiement mobile non confirmé.
    reference_mtn   = Column(String(100), default='')    # ID retourné MTN API
    # Référence externe renvoyée par l'API MTN/Orange (utile pour vérifier le paiement plus tard).
    date_vente      = Column(
        DateTime,
        default=maintenant_cameroun
    )
    # Date/heure automatique de la vente (heure du Cameroun).

    # Relation : chaque transaction appartient à un produit
    produit = relationship('Produit', back_populates='transactions')
    # Donne accès à transaction.produit (l'objet Produit complet lié à cette vente).

    # ── Méthodes utiles ──────────────────────────────────────
    def heure(self):
        """Retourne l'heure formatée : 14:32"""
        return self.date_vente.strftime('%H:%M')
        # Transforme la date/heure brute en texte "heures:minutes" pour l'affichage.

    def date_courte(self):
        """Retourne la date formatée : 12/08/2026"""
        return self.date_vente.strftime('%d/%m/%Y')
        # Transforme la date brute en texte "jour/mois/année" pour l'affichage.

    def badge_paiement(self):
        """Retourne le libellé du mode de paiement."""
        modes = {
            'cash':   'Cash',
            'orange': 'Orange Money',
            'mtn':    'MTN MoMo',
        }
        # Dictionnaire qui associe le code technique à un texte lisible pour l'utilisateur.
        return modes.get(self.mode_paiement, self.mode_paiement)
        # Cherche le libellé correspondant ; si non trouvé, renvoie le code brut tel quel.

    def __repr__(self):
        return (
            f"<Transaction produit_id={self.produit_id} "
            f"montant={self.montant} FCFA>"
        )
        # Représentation textuelle utile pour le débogage.


# ══════════════════════════════════════════════════════════════
# TABLE : alertes
# Stocke les alertes de rupture de stock générées automatiquement
# ══════════════════════════════════════════════════════════════
class Alerte(Base):
    __tablename__ = 'alertes'
    # Nom exact de la table créée dans MySQL.

    id          = Column(Integer, primary_key=True, autoincrement=True)
    # Identifiant unique auto-incrémenté de l'alerte.
    produit_id  = Column(Integer, ForeignKey('produits.id'), nullable=True)
    # Référence vers le produit concerné (peut être vide si l'alerte n'est liée à aucun produit).
    message     = Column(Text, nullable=False)
    # Texte complet de l'alerte (peut être long), obligatoire.
    type_alerte = Column(String(30), default='rupture')  # rupture/seuil_bas
    # Catégorie de l'alerte : "rupture" par défaut, ou "seuil_bas".
    lue         = Column(Integer, default=0)              # 0=non lue, 1=lue
    # Indique si l'alerte a déjà été consultée (0 = non lue, 1 = lue) ; 0 par défaut.
    date_alerte = Column(
        DateTime,
        default=maintenant_cameroun
    )
    # Date/heure automatique de création de l'alerte (heure du Cameroun).

    produit = relationship('Produit')
    # Donne accès à alerte.produit (l'objet Produit concerné, s'il existe).

    def est_lue(self):
        return self.lue == 1
        # Renvoie Vrai si l'alerte a déjà été marquée comme lue.

    def date_formatee(self):
        return self.date_alerte.strftime('%d/%m/%Y à %H:%M')
        # Transforme la date brute en texte lisible "jour/mois/année à heures:minutes".

    def __repr__(self):
        return f"<Alerte {self.type_alerte!r} — produit_id={self.produit_id}>"
        # Représentation textuelle utile pour le débogage.
