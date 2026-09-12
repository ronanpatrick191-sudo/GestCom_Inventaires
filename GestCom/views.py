"""
views.py — Toutes les vues de GestCom
Chaque vue reçoit une requête HTTP, interroge MySQL,
et retourne les données au template Jinja2.
Style : un seul fichier, comme Tetris/Mitarbeiter_Verwaltung.
"""
from pyramid.view import view_config
# Décorateur qui relie une fonction Python à une route (voir @view_config plus bas).
from pyramid.httpexceptions import HTTPFound
# HTTPFound : réponse de redirection (code 302), utilisée par home_view.
from sqlalchemy import func
# "func" donne accès aux fonctions SQL (SUM, COUNT, HOUR, DATE...) directement depuis Python.
from datetime import datetime, timezone, timedelta
# Outils de manipulation de dates : date du jour, horodatage, fuseau UTC, durées.
import threading
# Permet de lancer une tâche (ici : l'envoi d'email) dans un fil d'exécution séparé,
# pour ne pas ralentir la réponse envoyée au navigateur.

from .models import Produit, Transaction, Alerte
# Importe les 3 tables définies dans models.py.
from .temps import aujourd_hui_cameroun
# Date du jour dans le fuseau du Cameroun (UTC+1), pour que les filtres
# jour/semaine/mois correspondent à la journée réelle du commerçant même
# si le serveur tourne en Europe.
from .smtp_service import envoyer_alerte_stock, envoyer_email_test, envoyer_alertes_groupees
# Importe les fonctions d'envoi d'email définies dans smtp_service.py.
from .mobile_money_service import generer_qr_base64, initier_paiement, verifier_paiement
# Importe les fonctions de paiement mobile définies dans mobile_money_service.py.

NOMS_MOIS = {
    1: 'Janvier', 2: 'Février', 3: 'Mars', 4: 'Avril', 5: 'Mai', 6: 'Juin',
    7: 'Juillet', 8: 'Août', 9: 'Septembre', 10: 'Octobre', 11: 'Novembre', 12: 'Décembre',
}
# Dictionnaire : numéro de mois (1-12) → nom complet en français, pour l'affichage.
MOIS_COURTS = {
    '01': 'Jan', '02': 'Fév', '03': 'Mar', '04': 'Avr', '05': 'Mai', '06': 'Jun',
    '07': 'Jul', '08': 'Août', '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Déc',
}
# Dictionnaire : numéro de mois (texte "01"-"12") → abréviation, utilisé pour les graphiques.


def _nb_alertes_non_lues(db):
    """
    Nombre d'alertes non lues — utilisé pour le badge rouge à côté de
    "Alertes" dans la sidebar (base.jinja2), sur toutes les pages.
    Ne pas confondre avec 'nb_ruptures' (nombre de produits actuellement
    sous leur seuil), qui est un indicateur différent affiché dans le
    contenu du dashboard et de l'inventaire.
    """
    return db.query(func.count(Alerte.id)).filter(Alerte.lue == 0).scalar() or 0
    # Compte les lignes de la table alertes où lue == 0 (non lue) ;
    # .scalar() renvoie une seule valeur ; "or 0" évite un résultat None si la table est vide.


# ══════════════════════════════════════════════════════════════
# ACCUEIL
# ══════════════════════════════════════════════════════════════
@view_config(route_name='home')
# Relie cette fonction à la route "home" (URL "/") définie dans __init__.py.
def home_view(request):
    """Page d'accueil — redirige vers le dashboard."""
    return HTTPFound(location=request.route_url('dashboard'))
    # Renvoie une redirection HTTP vers l'URL de la route "dashboard" (donc "/dashboard").


# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════
def _graphique_periode(db, periode, aujourd_hui):
    """Construit les labels/valeurs du graphique Ventes selon la période choisie."""
    if periode == 'jour':
        # Cas "vue par jour" : on regroupe les ventes du jour par heure.
        par_heure = dict(
            db.query(func.hour(Transaction.date_vente), func.sum(Transaction.montant))
            # Sélectionne l'heure de la vente et la somme des montants pour cette heure.
            .filter(func.date(Transaction.date_vente) == aujourd_hui)
            # Ne garde que les ventes du jour précis "aujourd_hui".
            .filter(Transaction.statut == 'paye')
            # Ne compte que les ventes réellement payées.
            .group_by(func.hour(Transaction.date_vente))
            # Regroupe les résultats heure par heure.
            .all()
        )
        # Convertit la liste de paires (heure, montant) en dictionnaire {heure: montant}.
        heures = range(7, 19)  # plage horaire habituelle d'une boutique
        # Génère les heures de 7h à 18h (19 exclu), les horaires d'ouverture typiques.
        return (
            [f'{h}h' for h in heures],
            # Labels du graphique : "7h", "8h", ... "18h".
            [round(par_heure.get(h, 0) or 0) for h in heures],
            # Valeurs correspondantes ; 0 si aucune vente cette heure-là.
            "Aujourd'hui · par heure",
            # Sous-titre affiché au-dessus du graphique.
        )

    if periode == 'mois':
        # Cas "vue par mois" : on regroupe les ventes du mois par semaine.
        debut_mois = aujourd_hui.replace(day=1)
        # Premier jour du mois en cours.
        lignes = (
            db.query(Transaction.date_vente, Transaction.montant)
            .filter(func.date(Transaction.date_vente) >= debut_mois)
            .filter(func.date(Transaction.date_vente) <= aujourd_hui)
            .filter(Transaction.statut == 'paye')
            .all()
        )
        # Récupère chaque vente individuelle du mois (date + montant).
        par_semaine = {}
        # Dictionnaire qui va cumuler le total de chaque semaine du mois.
        for date_vente, montant in lignes:
            indice = (date_vente.day - 1) // 7
            # Calcule le numéro de semaine dans le mois (0 = semaine 1, 1 = semaine 2, etc.).
            par_semaine[indice] = par_semaine.get(indice, 0) + montant
            # Additionne le montant de cette vente au total de sa semaine.
        nb_semaines = ((aujourd_hui.day - 1) // 7) + 1
        # Nombre de semaines écoulées depuis le début du mois jusqu'à aujourd'hui.
        return (
            [f'S{i + 1}' for i in range(nb_semaines)],
            # Labels : "S1", "S2", "S3"...
            [round(par_semaine.get(i, 0)) for i in range(nb_semaines)],
            # Total de chaque semaine, 0 si pas de vente.
            f'{NOMS_MOIS[aujourd_hui.month]} {aujourd_hui.year} · par semaine',
            # Sous-titre avec le nom du mois et l'année en cours.
        )

    # ── semaine (par défaut) ──
    jours_semaine = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
    # Abréviations des jours de la semaine en français, dans l'ordre.
    debut_semaine = aujourd_hui - timedelta(days=6)
    # Date d'il y a 6 jours : point de départ de "cette semaine" (7 derniers jours glissants).
    ventes_par_jour = dict(
        db.query(func.date(Transaction.date_vente), func.sum(Transaction.montant))
        .filter(func.date(Transaction.date_vente) >= debut_semaine)
        .filter(Transaction.statut == 'paye')
        .group_by(func.date(Transaction.date_vente))
        .all()
    )
    # Dictionnaire {date: total des ventes de ce jour} sur les 7 derniers jours.
    labels, valeurs = [], []
    # Listes vides qui seront remplies jour par jour ci-dessous.
    for i in range(7):
        jour = debut_semaine + timedelta(days=i)
        # Calcule chaque jour, du plus ancien (i=0) au jour actuel (i=6).
        labels.append(jours_semaine[jour.weekday()])
        # Ajoute l'abréviation du jour de la semaine (Lun, Mar...) correspondant à cette date.
        valeurs.append(round(ventes_par_jour.get(jour, 0) or 0))
        # Ajoute le total des ventes de ce jour, 0 si aucune vente.
    return labels, valeurs, 'Cette semaine · par jour'
    # Renvoie les labels, les valeurs, et le sous-titre du graphique.


@view_config(
    route_name='dashboard',
    renderer='GestCom:templates/dashboard/index.jinja2'
)
# Relie cette fonction à la route "dashboard" et indique quel template HTML afficher le résultat.
def dashboard_view(request):
    """
    Page principale — affiche les KPIs en FCFA pour la période choisie
    (jour / semaine / mois). Lit les données réelles depuis MySQL.
    """
    db = request.dbsession
    # Récupère la session de base de données ouverte pour cette requête (voir main_models.py).
    aujourd_hui = aujourd_hui_cameroun()
    # Date du jour, utilisée comme référence pour tous les calculs de période.

    periode = request.params.get('periode', 'jour')
    # Lit le paramètre d'URL "?periode=..." envoyé par le navigateur ; "jour" si absent.
    if periode not in ('jour', 'semaine', 'mois'):
        # Sécurité : si une valeur invalide est passée dans l'URL...
        periode = 'jour'
        # ...on revient à la valeur par défaut plutôt que de planter.

    if periode == 'semaine':
        date_debut = aujourd_hui - timedelta(days=6)
        # Début de période = il y a 6 jours (7 jours glissants au total).
    elif periode == 'mois':
        date_debut = aujourd_hui.replace(day=1)
        # Début de période = premier jour du mois en cours.
    else:
        date_debut = aujourd_hui
        # Vue "jour" : la période commence et finit aujourd'hui.

    # ── KPI 1 : Ventes totales sur la période ──
    ventes_periode = (
        db.query(func.sum(Transaction.montant))
        # Additionne la colonne "montant" de toutes les transactions correspondantes.
        .filter(func.date(Transaction.date_vente) >= date_debut)
        .filter(func.date(Transaction.date_vente) <= aujourd_hui)
        # Ne garde que les ventes comprises dans l'intervalle [date_debut, aujourd_hui].
        .filter(Transaction.statut == 'paye')
        # Ignore les ventes encore en attente de paiement.
        .scalar() or 0.0
        # Renvoie le total (un seul nombre) ; 0.0 si aucune vente.
    )

    # ── KPI 2 : Nombre de transactions sur la période ──
    nb_transactions = (
        db.query(func.count(Transaction.id))
        # Compte le nombre de lignes de transactions correspondantes.
        .filter(func.date(Transaction.date_vente) >= date_debut)
        .filter(func.date(Transaction.date_vente) <= aujourd_hui)
        .scalar() or 0
    )

    # ── KPI 3 : Profit net réel sur la période (prix_vente - prix_achat) ──
    profit_periode = round(
        db.query(
            func.sum(
                (Produit.prix_vente - Produit.prix_achat) * Transaction.quantite
            )
            # Pour chaque vente : (prix vendu - prix acheté) × quantité vendue = bénéfice réalisé.
        )
        .select_from(Transaction)
        # Précise que la requête part de la table transactions...
        .join(Produit, Transaction.produit_id == Produit.id)
        # ...jointe à la table produits, pour connaître les prix d'achat/vente de chaque vente.
        .filter(func.date(Transaction.date_vente) >= date_debut)
        .filter(func.date(Transaction.date_vente) <= aujourd_hui)
        .filter(Transaction.statut == 'paye')
        .scalar() or 0.0
    )

    # ── KPI 4 : Alertes non lues ──
    nb_alertes_non_lues = _nb_alertes_non_lues(db)
    # Réutilise la fonction définie plus haut pour compter les alertes non lues.

    # ── Top 5 produits les plus vendus sur la période ──
    top_produits = (
        db.query(
            Produit.nom,
            func.sum(Transaction.quantite).label('total_vendu'),
            # Total des quantités vendues, nommé "total_vendu" pour y accéder dans le template.
            func.sum(Transaction.montant).label('total_fcfa'),
            # Total des montants vendus, nommé "total_fcfa".
        )
        .join(Transaction, Transaction.produit_id == Produit.id)
        .filter(func.date(Transaction.date_vente) >= date_debut)
        .filter(func.date(Transaction.date_vente) <= aujourd_hui)
        .group_by(Produit.id, Produit.nom)
        # Regroupe les ventes par produit (un total par produit).
        .order_by(func.sum(Transaction.montant).desc())
        # Trie du produit qui rapporte le plus au moins.
        .limit(5)
        # Ne garde que les 5 premiers.
        .all()
    )

    # ── 6 dernières transactions (toutes dates) ──
    dernieres_ventes = (
        db.query(Transaction)
        .order_by(Transaction.date_vente.desc())
        # Trie de la vente la plus récente à la plus ancienne.
        .limit(6)
        .all()
    )

    labels_graph, valeurs_graph, sous_titre = _graphique_periode(db, periode, aujourd_hui)
    # Appelle la fonction définie plus haut pour obtenir les données du graphique.

    return {
        # Dictionnaire transmis au template Jinja2 (dashboard/index.jinja2) : chaque clé
        # devient une variable utilisable directement dans le HTML avec {{ variable }}.
        'periode':              periode,
        'ventes_jour':          round(ventes_periode),
        'profit_jour':          profit_periode,
        'nb_transactions':      nb_transactions,
        'nb_alertes_non_lues':  nb_alertes_non_lues,
        'top_produits':         top_produits,
        'dernieres_ventes':     dernieres_ventes,
        'labels_semaine':       labels_graph,
        'ventes_semaine':       valeurs_graph,
        'chart_sous_titre':     sous_titre,
        'aujourd_hui':          aujourd_hui.strftime('%d/%m/%Y'),
        # Date du jour mise en forme "jour/mois/année" pour l'affichage.
    }


# ══════════════════════════════════════════════════════════════
# INVENTAIRE
# ══════════════════════════════════════════════════════════════
@view_config(
    route_name='inventaire',
    renderer='GestCom:templates/inventaire/list.jinja2'
)
def inventaire_view(request):
    """Liste tous les produits avec leur niveau de stock."""
    db = request.dbsession
    produits = db.query(Produit).order_by(Produit.nom).all()
    # Récupère tous les produits, triés par ordre alphabétique du nom.
    return {
        'produits':            produits,
        'nb_produits':         len(produits),
        # Nombre total de produits dans le catalogue.
        'nb_ruptures':         sum(1 for p in produits if p.est_en_rupture()),
        # Compte les produits dont le stock est sous le seuil d'alerte.
        'nb_alertes_non_lues': _nb_alertes_non_lues(db),
    }


@view_config(
    route_name='stock',
    renderer='GestCom:templates/stock/index.jinja2'
)
def stock_view(request):
    """Page Stock — niveaux, valeur totale et ruptures."""
    db = request.dbsession
    produits = db.query(Produit).order_by(Produit.nom).all()
    return {
        'produits':            produits,
        'valeur_totale':       round(sum(p.prix_achat * p.stock for p in produits)),
        # Valeur totale du stock au prix d'achat (ce que coûterait de tout racheter).
        'nb_ruptures':         sum(1 for p in produits if p.stock == 0),
        # Nombre de produits totalement épuisés (stock à zéro).
        'nb_bas':              sum(1 for p in produits if p.statut_stock() == 'bas'),
        # Nombre de produits en stock bas (mais pas encore à zéro).
        'nb_alertes_non_lues': _nb_alertes_non_lues(db),
    }


@view_config(
    route_name='stock_alerte_groupee',
    request_method='POST',
    # Cette vue n'accepte que les requêtes HTTP POST (envoi de formulaire/action, pas simple affichage).
    renderer='json'
    # La réponse est renvoyée au format JSON (pas de page HTML), lue par le JavaScript du template.
)
def stock_alerte_email(request):
    """Envoie un email d'alerte pour chaque produit actuellement sous son seuil."""
    db = request.dbsession
    produits_alerte = [p for p in db.query(Produit).all() if p.est_en_rupture()]
    # Filtre en Python (pas en SQL) tous les produits actuellement sous leur seuil.

    if not produits_alerte:
        # Aucun produit à signaler : inutile d'envoyer un email.
        return {'succes': True, 'message': 'Aucun produit en alerte actuellement.'}

    settings = request.registry.settings
    # Récupère la configuration globale de l'application (dont les identifiants SMTP).
    nb_envoyes = envoyer_alertes_groupees(
        settings, produits_alerte,
        url_inventaire=request.route_url('inventaire'),
    )
    # Envoie un email pour chaque produit en alerte, renvoie le nombre d'envois réussis.

    if nb_envoyes == 0:
        # Aucun email n'a pu être envoyé (probablement une config SMTP manquante).
        return {
            'succes': False,
            'message': "Échec de l'envoi. Vérifiez la configuration SMTP (.env).",
        }
    return {'succes': True, 'message': f"{nb_envoyes} email(s) d'alerte envoyé(s)."}


@view_config(
    route_name='rapport',
    renderer='GestCom:templates/rapport/index.jinja2'
)
def rapport_view(request):
    """Page Rapport — chiffre d'affaires, profit net et tendance mensuelle."""
    db = request.dbsession
    aujourd_hui = aujourd_hui_cameroun()
    debut_mois = aujourd_hui.replace(day=1)
    # Premier jour du mois en cours, référence pour tous les totaux "du mois".

    ca_mois = (
        db.query(func.sum(Transaction.montant))
        .filter(func.date(Transaction.date_vente) >= debut_mois)
        .filter(Transaction.statut == 'paye')
        .scalar() or 0.0
    )
    # Chiffre d'affaires (somme des ventes payées) depuis le début du mois.

    cout_vendu_mois = (
        db.query(func.sum(Produit.prix_achat * Transaction.quantite))
        # Pour chaque vente : prix d'achat × quantité = ce que ces articles ont coûté à acheter.
        .select_from(Transaction)
        .join(Produit, Transaction.produit_id == Produit.id)
        .filter(func.date(Transaction.date_vente) >= debut_mois)
        .filter(Transaction.statut == 'paye')
        .scalar() or 0.0
    )
    # Coût total (prix d'achat) des articles vendus ce mois-ci.

    nb_articles_mois = (
        db.query(func.sum(Transaction.quantite))
        .filter(func.date(Transaction.date_vente) >= debut_mois)
        .filter(Transaction.statut == 'paye')
        .scalar() or 0
    )
    # Nombre total d'articles vendus (toutes quantités additionnées) ce mois-ci.

    top_produits_mois = (
        db.query(
            Produit.nom,
            func.sum(Transaction.quantite).label('total_vendu'),
            func.sum(Transaction.montant).label('total_fcfa'),
        )
        .join(Transaction, Transaction.produit_id == Produit.id)
        .filter(func.date(Transaction.date_vente) >= debut_mois)
        .filter(Transaction.statut == 'paye')
        .group_by(Produit.id, Produit.nom)
        .order_by(func.sum(Transaction.montant).desc())
        .limit(5)
        .all()
    )
    # Les 5 produits qui ont le plus rapporté d'argent ce mois-ci.

    # ── Tendance des 6 derniers mois avec des ventes (CA + profit) ──
    lignes_mensuelles = (
        db.query(
            func.date_format(Transaction.date_vente, '%Y-%m').label('mois'),
            # Formate la date en "année-mois" (ex: "2026-08"), pour regrouper par mois.
            func.sum(Transaction.montant).label('ca'),
            # Chiffre d'affaires total de ce mois.
            func.sum((Produit.prix_vente - Produit.prix_achat) * Transaction.quantite).label('profit'),
            # Profit total de ce mois (bénéfice unitaire × quantité, additionné).
        )
        .select_from(Transaction)
        .join(Produit, Transaction.produit_id == Produit.id)
        .filter(Transaction.statut == 'paye')
        .group_by('mois')
        # Regroupe toutes les ventes par mois calendaire.
        .order_by('mois')
        # Trie du mois le plus ancien au plus récent.
        .all()
    )
    six_derniers = lignes_mensuelles[-6:]
    # Ne garde que les 6 derniers mois disponibles (pour le graphique de tendance).

    return {
        'ca_mois':             round(ca_mois),
        'profit_mois':         round(ca_mois - cout_vendu_mois),
        # Profit = chiffre d'affaires - coût des articles vendus.
        'cout_vendu_mois':     round(cout_vendu_mois),
        'nb_articles_mois':    nb_articles_mois,
        'top_produits_mois':   top_produits_mois,
        'labels_mois':         [MOIS_COURTS.get(m.mois[5:7], m.mois) for m in six_derniers],
        # Transforme "2026-08" en juste "08", puis en abréviation "Août" via MOIS_COURTS.
        'ca_mensuel':          [round(m.ca or 0) for m in six_derniers],
        'profit_mensuel':      [round(m.profit or 0) for m in six_derniers],
        'mois_courant':        f'{NOMS_MOIS[aujourd_hui.month]} {aujourd_hui.year}',
        'nb_alertes_non_lues': _nb_alertes_non_lues(db),
    }


# ══════════════════════════════════════════════════════════════
# TRANSACTIONS — liste filtrable (jour / semaine / mois)
# ══════════════════════════════════════════════════════════════
@view_config(
    route_name='transactions',
    renderer='GestCom:templates/transactions/list.jinja2'
)
def transactions_view(request):
    """
    Liste toutes les transactions de la période choisie (jour / semaine /
    mois), de la plus récente à la plus ancienne, avec les totaux associés.
    Le filtre se fait via le paramètre d'URL "?periode=jour|semaine|mois".
    """
    db = request.dbsession
    aujourd_hui = aujourd_hui_cameroun()
    # Date du jour : référence pour calculer le début de chaque période.

    periode = request.params.get('periode', 'jour')
    # Lit "?periode=..." dans l'URL ; "jour" par défaut si absent.
    if periode not in ('jour', 'semaine', 'mois'):
        # Sécurité : toute valeur inattendue retombe sur "jour".
        periode = 'jour'

    if periode == 'semaine':
        date_debut = aujourd_hui - timedelta(days=6)
        # 7 jours glissants (aujourd'hui inclus).
    elif periode == 'mois':
        date_debut = aujourd_hui.replace(day=1)
        # Depuis le 1er du mois en cours.
    else:
        date_debut = aujourd_hui
        # Vue "jour" : uniquement aujourd'hui.

    transactions = (
        db.query(Transaction)
        .filter(func.date(Transaction.date_vente) >= date_debut)
        .filter(func.date(Transaction.date_vente) <= aujourd_hui)
        # Garde les ventes comprises dans l'intervalle [date_debut, aujourd_hui].
        .order_by(Transaction.date_vente.desc())
        # De la vente la plus récente à la plus ancienne.
        .all()
    )

    payees = [t for t in transactions if t.statut == 'paye']
    # Seules les ventes réellement payées comptent dans les totaux d'argent.
    montant_total = round(sum(t.montant for t in payees))
    # Chiffre d'affaires de la période, en FCFA entiers.
    nb_articles = sum(t.quantite for t in payees)
    # Nombre total d'articles vendus sur la période.

    libelles_periode = {
        'jour':    "Aujourd'hui",
        'semaine': '7 derniers jours',
        'mois':    f'{NOMS_MOIS[aujourd_hui.month]} {aujourd_hui.year}',
    }
    # Texte lisible affiché à côté du sélecteur de période.

    return {
        'periode':             periode,
        'periode_libelle':     libelles_periode[periode],
        'transactions':        transactions,
        'nb_transactions':     len(transactions),
        'nb_en_attente':       len(transactions) - len(payees),
        # Nombre de ventes encore en attente de confirmation de paiement.
        'montant_total':       montant_total,
        'nb_articles':         nb_articles,
        'aujourd_hui':         aujourd_hui.strftime('%d/%m/%Y'),
        'nb_alertes_non_lues': _nb_alertes_non_lues(db),
    }


@view_config(route_name='recherche', renderer='json')
def recherche_view(request):
    """Recherche globale (barre de recherche de la topbar) — produits uniquement."""
    db = request.dbsession
    q = (request.params.get('q') or '').strip()
    # Récupère le texte recherché depuis l'URL (?q=...), en enlevant les espaces inutiles.
    if len(q) < 2:
        # Recherche trop courte (moins de 2 caractères) : on ne cherche pas, pour éviter
        # de renvoyer des centaines de résultats inutiles.
        return {'resultats': []}

    produits = (
        db.query(Produit)
        .filter(Produit.nom.ilike(f'%{q}%'))
        # "ilike" = recherche insensible à la casse contenant le texte recherché n'importe où.
        .order_by(Produit.nom)
        .limit(8)
        # Limite à 8 résultats pour garder un menu déroulant lisible.
        .all()
    )
    return {
        'resultats': [
            {
                'id':         p.id,
                'nom':        p.nom,
                'stock':      p.stock,
                'unite':      p.unite,
                'prix_vente': p.prix_vente,
                'url':        request.route_url('inventaire') + f'#row-produit-{p.id}',
                # Lien qui ramène vers la page Inventaire, directement sur la ligne du produit.
            }
            for p in produits
            # Transforme chaque objet Produit en dictionnaire simple, envoyable en JSON.
        ]
    }


# ══════════════════════════════════════════════════════════════
# PRODUITS — CRUD (catalogue)
# ══════════════════════════════════════════════════════════════
@view_config(
    route_name='produit_ajouter',
    request_method='POST',
    renderer='json'
)
def produit_ajouter(request):
    """Ajoute un nouveau produit dans la base de données."""
    db = request.dbsession
    try:
        prix_achat = float(request.POST.get('prix_achat', 0))
        # Lit le champ "prix_achat" du formulaire envoyé, converti en nombre décimal ; 0 si absent.
        prix_vente = float(request.POST['prix_vente'])
        # Ce champ est obligatoire : request.POST[...] lève une erreur KeyError s'il manque.
        stock      = int(request.POST.get('stock', 0))
        seuil      = int(request.POST.get('seuil', 10))
        nom        = request.POST['nom'].strip()
        # Nom obligatoire, avec suppression des espaces en début/fin.

        if not nom:
            # Sécurité supplémentaire : un nom composé uniquement d'espaces est invalide.
            return {'succes': False, 'message': 'Le nom du produit est obligatoire'}
        if prix_vente <= 0:
            return {'succes': False, 'message': 'Le prix de vente doit être supérieur à 0'}
        if prix_achat < 0 or stock < 0 or seuil < 0:
            return {'succes': False, 'message': 'Les prix et quantités ne peuvent pas être négatifs'}

        nouveau = Produit(
            nom        = nom,
            categorie  = request.POST.get('categorie', '').strip(),
            prix_achat = prix_achat,
            prix_vente = prix_vente,
            stock      = stock,
            seuil      = seuil,
            unite      = request.POST.get('unite', 'unité').strip(),
        )
        # Crée un nouvel objet Produit en mémoire avec toutes les valeurs validées.
        db.add(nouveau)
        # Prépare l'insertion de ce nouveau produit dans la base de données.
        db.flush()  # obtenir l'ID sans committer
        # Envoie la requête SQL d'insertion immédiatement (sans valider définitivement),
        # ce qui permet de récupérer l'ID auto-généré du nouveau produit.
        return {
            'succes':  True,
            'message': f'{nouveau.nom} ajouté avec succès !',
            'id':      nouveau.id,
        }
    except (KeyError, ValueError) as e:
        # KeyError : un champ obligatoire manquait. ValueError : une conversion a échoué
        # (ex: texte non numérique dans le champ prix).
        return {'succes': False, 'message': f'Erreur : {e}'}


@view_config(
    route_name='produit_modifier',
    request_method='POST',
    renderer='json'
)
def produit_modifier(request):
    """Modifie un produit existant."""
    db = request.dbsession
    try:
        pid = int(request.matchdict['id'])
        # Récupère l'identifiant du produit depuis l'URL (le {id} de la route).
    except ValueError:
        return {'succes': False, 'message': 'Identifiant de produit invalide'}

    p = db.query(Produit).filter(Produit.id == pid).first()
    # Cherche le produit correspondant à cet identifiant ; None si non trouvé.

    if not p:
        return {'succes': False, 'message': 'Produit introuvable'}

    # Valider toutes les valeurs avant de toucher à l'objet suivi par la
    # session : si une conversion échoue à mi-chemin, on ne veut pas
    # committer une mise à jour partielle du produit.
    try:
        nom        = request.POST.get('nom', p.nom).strip()
        # Si le formulaire n'envoie pas ce champ, on garde la valeur actuelle du produit (p.nom).
        categorie  = request.POST.get('categorie', p.categorie).strip()
        prix_achat = float(request.POST.get('prix_achat', p.prix_achat))
        prix_vente = float(request.POST.get('prix_vente', p.prix_vente))
        stock      = int(request.POST.get('stock', p.stock))
        seuil      = int(request.POST.get('seuil', p.seuil))
        unite      = request.POST.get('unite', p.unite).strip()
    except ValueError as e:
        return {'succes': False, 'message': f'Erreur : {e}'}

    if not nom:
        return {'succes': False, 'message': 'Le nom du produit est obligatoire'}
    if prix_vente <= 0:
        return {'succes': False, 'message': 'Le prix de vente doit être supérieur à 0'}
    if prix_achat < 0 or stock < 0 or seuil < 0:
        return {'succes': False, 'message': 'Les prix et quantités ne peuvent pas être négatifs'}

    p.nom, p.categorie   = nom, categorie
    # Ce n'est qu'à partir d'ici que l'objet "p" suivi par la base est réellement modifié.
    p.prix_achat         = prix_achat
    p.prix_vente         = prix_vente
    p.stock, p.seuil     = stock, seuil
    p.unite              = unite

    return {'succes': True, 'message': f'{p.nom} mis à jour !'}
    # Pas besoin d'appeler explicitement un "commit" : pyramid_tm s'en charge automatiquement
    # à la fin de la requête si aucune erreur ne survient.


@view_config(
    route_name='produit_supprimer',
    request_method='POST',
    renderer='json'
)
def produit_supprimer(request):
    """Supprime un produit (et ses transactions associées)."""
    db = request.dbsession
    try:
        pid = int(request.matchdict['id'])
    except ValueError:
        return {'succes': False, 'message': 'Identifiant de produit invalide'}

    p = db.query(Produit).filter(Produit.id == pid).first()

    if not p:
        return {'succes': False, 'message': 'Produit introuvable'}

    nom = p.nom
    # On garde le nom en mémoire avant suppression, pour l'utiliser dans le message de confirmation.

    # Détacher les alertes liées avant suppression pour éviter une
    # erreur de contrainte de clé étrangère (les transactions, elles,
    # sont supprimées automatiquement via le cascade du modèle).
    db.query(Alerte).filter(Alerte.produit_id == pid).update(
        {'produit_id': None}
    )
    # Met à jour toutes les alertes qui pointaient vers ce produit : elles ne pointent
    # plus vers rien (produit_id = None), plutôt que de bloquer la suppression.

    db.delete(p)
    # Supprime réellement le produit (ce qui supprime aussi ses transactions via le cascade).
    return {'succes': True, 'message': f'{nom} supprimé.'}


# ══════════════════════════════════════════════════════════════
# CAISSE — Enregistrement des ventes
# ══════════════════════════════════════════════════════════════
@view_config(
    route_name='caisse',
    renderer='GestCom:templates/caisse/index.jinja2'
)
def caisse_view(request):
    """Page caisse — affiche les produits disponibles pour la vente."""
    db       = request.dbsession
    produits = db.query(Produit).filter(Produit.stock > 0).order_by(Produit.nom).all()
    # Ne montre en caisse que les produits qui ont encore du stock disponible (stock > 0).
    return {
        'produits':            produits,
        'nb_alertes_non_lues': _nb_alertes_non_lues(db),
    }


def _finaliser_transaction(db, request, transaction):
    """
    Finalise une transaction en attente : décrémente le stock, marque la
    vente comme payée, et crée une alerte + email si le stock devient
    critique. Utilisée aussi bien pour le cash (finalisation immédiate)
    que pour mobile money (finalisation à la confirmation du paiement).
    """
    produit = transaction.produit
    # Récupère l'objet Produit lié à cette transaction (grâce à la relation SQLAlchemy).
    produit.stock      -= transaction.quantite
    # Diminue le stock du produit de la quantité vendue.
    transaction.statut  = 'paye'
    # Marque officiellement la vente comme payée.

    alerte_creee = False
    # Indicateur pour signaler au front-end si une alerte a été déclenchée par cette vente.
    if produit.est_en_rupture():
        # Vérifie si, après cette vente, le stock est tombé sous le seuil critique.
        type_al = 'rupture' if produit.stock == 0 else 'seuil_bas'
        # Distingue rupture totale (stock à 0) de simple stock bas.
        alerte  = Alerte(
            produit_id  = produit.id,
            message     = (
                f"Stock critique : {produit.nom} "
                f"({produit.stock} {produit.unite} restants)"
            ),
            type_alerte = type_al,
        )
        db.add(alerte)
        # Enregistre une nouvelle ligne dans la table alertes.
        alerte_creee = True

        # Envoyer email SMTP en arrière-plan (sans bloquer la réponse)
        settings        = request.registry.settings
        produit_nom     = produit.nom
        stock_actuel    = produit.stock
        seuil           = produit.seuil
        url_inventaire  = request.route_url('inventaire')
        # On copie ces valeurs dans des variables simples avant de lancer le thread, car
        # l'objet "produit" (lié à la session de base de données) et "request" ne doivent
        # pas être utilisés depuis un autre thread une fois la requête HTTP terminée.

        def envoyer_email():
            envoyer_alerte_stock(
                settings,
                produit_nom     = produit_nom,
                stock_actuel    = stock_actuel,
                seuil           = seuil,
                type_alerte     = type_al,
                url_inventaire  = url_inventaire,
            )
        # Fonction interne qui sera exécutée dans un thread séparé.

        threading.Thread(target=envoyer_email, daemon=True).start()
        # Lance l'envoi d'email en arrière-plan : le client (navigateur) n'a pas à attendre
        # que l'email parte pour recevoir la confirmation de vente. daemon=True permet au
        # programme de s'arrêter même si ce thread est encore en cours.

    return {
        'montant':       transaction.montant,
        'produit_nom':   produit.nom,
        'stock_restant': produit.stock,
        'alerte':        alerte_creee,
    }


@view_config(
    route_name='vente_enregistrer',
    request_method='POST',
    renderer='json'
)
def vente_enregistrer(request):
    """
    Enregistre une vente cash en caisse (finalisation immédiate).
    Met à jour le stock automatiquement et crée une alerte si nécessaire.
    """
    db = request.dbsession

    try:
        produit_id    = int(request.POST['produit_id'])
        quantite      = int(request.POST['quantite'])
        mode_paiement = request.POST.get('mode_paiement', 'cash')
    except (KeyError, ValueError):
        return {'succes': False, 'message': 'Données manquantes ou invalides'}

    if quantite <= 0:
        # Une vente de 0 ou de quantité négative n'a pas de sens.
        return {'succes': False, 'message': 'Quantité invalide'}

    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        return {'succes': False, 'message': 'Produit introuvable'}
    if produit.stock < quantite:
        # Empêche de vendre plus que ce qui est réellement disponible en stock.
        return {
            'succes':  False,
            'message': f'Stock insuffisant. Disponible : {produit.stock} {produit.unite}',
        }

    montant = round(produit.prix_vente * quantite)
    # Calcule le montant total de la vente : prix unitaire × quantité, arrondi en FCFA entiers.
    vente = Transaction(
        produit_id    = produit_id,
        quantite      = quantite,
        montant       = montant,
        mode_paiement = mode_paiement,
        statut        = 'en_attente',
        # Créée d'abord "en_attente" : elle sera immédiatement finalisée ci-dessous
        # (pour le cash, contrairement au mobile money qui attend une confirmation).
    )
    db.add(vente)
    db.flush()
    # Insère la transaction pour qu'elle obtienne un ID et que sa relation "produit" soit utilisable.

    resultat = _finaliser_transaction(db, request, vente)
    # Décrémente le stock, marque la vente comme payée, gère les alertes.
    resultat['succes']  = True
    resultat['message'] = f"Vente enregistrée — {resultat['montant']:,} FCFA"
    # Le format ":," ajoute des séparateurs de milliers (ex: 17,500) pour la lisibilité.
    return resultat


def _initier_paiement_mobile(request, operateur):
    """
    Démarre une vente en mode mobile money (Orange/MTN) : crée une
    transaction 'en_attente' (le stock n'est PAS encore décrémenté) et
    renvoie un QR code de paiement généré côté serveur.
    """
    db = request.dbsession

    try:
        produit_id = int(request.POST['produit_id'])
        quantite   = int(request.POST['quantite'])
    except (KeyError, ValueError):
        return {'succes': False, 'message': 'Données manquantes ou invalides'}

    if quantite <= 0:
        return {'succes': False, 'message': 'Quantité invalide'}

    produit = db.query(Produit).filter(Produit.id == produit_id).first()
    if not produit:
        return {'succes': False, 'message': 'Produit introuvable'}
    if produit.stock < quantite:
        return {
            'succes':  False,
            'message': f'Stock insuffisant. Disponible : {produit.stock} {produit.unite}',
        }

    montant   = round(produit.prix_vente * quantite)
    reference = f"GC{int(datetime.now(timezone.utc).timestamp() * 1000)}"
    # Génère une référence unique de vente : "GC" + horodatage actuel en millisecondes.

    vente = Transaction(
        produit_id    = produit_id,
        quantite      = quantite,
        montant       = montant,
        mode_paiement = operateur,
        statut        = 'en_attente',
        # Reste "en_attente" ici : le stock ne sera décrémenté qu'à la confirmation du paiement.
        reference_mtn = reference,
        # Stocke la référence pour pouvoir retrouver cette transaction lors de la vérification.
    )
    db.add(vente)
    db.flush()

    settings                = request.registry.settings
    resultat_init            = initier_paiement(settings, operateur, montant, reference)
    # Démarre (ou simule) la demande de paiement auprès de l'opérateur mobile money.
    qr_base64, qr_donnees    = generer_qr_base64(montant, reference, operateur)
    # Génère l'image du QR code que le client scannera pour payer.

    return {
        'succes':      True,
        'reference':   reference,
        'montant':     montant,
        'produit_nom': produit.nom,
        'mode':        resultat_init['mode'],
        # "api" si la vraie API a été appelée, "demo" sinon.
        'qr_image':    qr_base64,
        'qr_data':     qr_donnees,
    }


def _verifier_paiement_mobile(request, operateur):
    """
    Vérifie le statut d'un paiement mobile money. En mode démo (pas de
    clés API configurées), le passage à 'payé' se fait uniquement sur
    confirmation manuelle du commerçant (?confirmer=1).
    """
    db = request.dbsession
    reference = request.matchdict['ref_id']
    # Référence de la transaction, extraite de l'URL (le {ref_id} de la route).
    forcer    = request.params.get('confirmer') == '1'
    # True si le commerçant a cliqué sur "Marquer comme payée" (paramètre ?confirmer=1 dans l'URL).

    vente = db.query(Transaction).filter(Transaction.reference_mtn == reference).first()
    if not vente:
        return {'succes': False, 'message': 'Transaction introuvable'}

    if vente.statut == 'paye':
        # Déjà finalisée lors d'un appel précédent : on renvoie directement le résultat,
        # sans refaire tout le travail de finalisation une seconde fois.
        return {'succes': True, 'statut': 'paye', 'stock_restant': vente.produit.stock}

    settings = request.registry.settings
    resultat = verifier_paiement(settings, operateur, reference)
    # Interroge le vrai statut auprès de l'opérateur (ou renvoie "en_attente" en mode démo).

    if resultat['statut'] == 'paye' or (resultat['mode'] == 'demo' and forcer):
        # Le paiement est confirmé soit par l'API réelle, soit manuellement par le commerçant.
        details = _finaliser_transaction(db, request, vente)
        return {'succes': True, 'statut': 'paye', **details}
        # "**details" fusionne le dictionnaire "details" dans la réponse renvoyée.

    return {'succes': True, 'statut': 'en_attente', 'mode': resultat['mode']}
    # Toujours en attente : le front-end continuera à interroger cette route périodiquement.


@view_config(route_name='caisse_mtn', request_method='POST', renderer='json')
def caisse_mtn_payer(request):
    return _initier_paiement_mobile(request, 'mtn')
    # Vue "fine" qui appelle simplement la fonction commune avec l'opérateur "mtn".


@view_config(route_name='caisse_mtn_verif', request_method='GET', renderer='json')
def caisse_mtn_verif(request):
    return _verifier_paiement_mobile(request, 'mtn')


@view_config(route_name='caisse_orange', request_method='POST', renderer='json')
def caisse_orange_payer(request):
    return _initier_paiement_mobile(request, 'orange')


@view_config(route_name='caisse_orange_verif', request_method='GET', renderer='json')
def caisse_orange_verif(request):
    return _verifier_paiement_mobile(request, 'orange')


# ══════════════════════════════════════════════════════════════
# ALERTES
# ══════════════════════════════════════════════════════════════
@view_config(
    route_name='alertes',
    renderer='GestCom:templates/alertes/list.jinja2'
)
def alertes_view(request):
    """Liste toutes les alertes non lues."""
    db      = request.dbsession
    alertes = (
        db.query(Alerte)
        .filter(Alerte.lue == 0)
        .order_by(Alerte.date_alerte.desc())
        # Les alertes les plus récentes apparaissent en premier.
        .all()
    )

    settings = request.registry.settings
    smtp_configure = bool(settings.get('smtp.user') and settings.get('smtp.password'))
    # True seulement si à la fois l'utilisateur ET le mot de passe SMTP sont configurés.
    smtp_dest      = settings.get('smtp.dest') or settings.get('smtp.user') or ''
    # Adresse de destination affichée à l'écran : smtp.dest en priorité, sinon smtp.user.

    return {
        'alertes':             alertes,
        'nb_alertes':          len(alertes),
        'nb_alertes_non_lues': len(alertes),
        'smtp_configure':      smtp_configure,
        'smtp_dest':           smtp_dest,
    }


@view_config(
    route_name='alerte_email_test',
    request_method='POST',
    renderer='json'
)
def alerte_email_test(request):
    """Envoie un vrai email de test via SMTP pour vérifier la configuration."""
    settings = request.registry.settings
    ok = envoyer_email_test(settings)
    # Tente d'envoyer un email de démonstration ; renvoie True/False selon le résultat.

    if ok:
        dest = settings.get('smtp.dest') or settings.get('smtp.user') or ''
        return {'succes': True, 'message': f'Email de test envoyé à {dest} !'}

    return {
        'succes': False,
        'message': (
            "Échec de l'envoi. Vérifiez SMTP_USER / SMTP_PASSWORD dans .env "
            "et que le mot de passe d'application Gmail est valide."
        ),
    }


@view_config(
    route_name='alerte_lire',
    request_method='POST',
    renderer='json'
)
def alerte_marquer_lue(request):
    """Marque une alerte comme lue."""
    db = request.dbsession
    try:
        aid = int(request.matchdict['id'])
    except ValueError:
        return {'succes': False, 'message': 'Identifiant d\'alerte invalide'}

    a = db.query(Alerte).filter(Alerte.id == aid).first()

    if not a:
        return {'succes': False, 'message': 'Alerte introuvable'}

    a.lue = 1
    # Marque l'alerte comme lue ; sera sauvegardé automatiquement à la fin de la requête.
    return {'succes': True}
