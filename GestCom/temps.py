# -*- coding: utf-8 -*-
"""
temps.py — Heure locale du Cameroun pour tout GestCom.

Le serveur peut tourner n'importe où (Allemagne, Belgique, hébergeur cloud…).
Si on enregistrait l'heure UTC ou l'heure du serveur, une vente faite à 10:00
au Cameroun pourrait s'afficher à 08:00 ou 09:00 sur le dashboard.

Pour éviter ça, toutes les dates/heures de l'application (ventes, alertes,
ajout de produit, filtres jour/semaine/mois) sont calculées dans le fuseau
du Cameroun, puis stockées comme datetime « naïf » (sans info de fuseau) —
exactement la forme que les colonnes de la base et les comparaisons de
`views.py` attendent déjà.
"""
from datetime import datetime, timezone, timedelta

# Le Cameroun (fuseau WAT) est en permanence à UTC+1, toute l'année :
# il n'y a jamais de passage à l'heure d'été. Un décalage fixe suffit donc,
# sans dépendre de la base de fuseaux du système (tzdata).
FUSEAU_CAMEROUN = timezone(timedelta(hours=1), 'WAT')


def maintenant_cameroun():
    """Date + heure actuelles au Cameroun, en datetime naïf (sans tzinfo)."""
    return datetime.now(FUSEAU_CAMEROUN).replace(tzinfo=None)


def aujourd_hui_cameroun():
    """Date du jour au Cameroun (objet `date`)."""
    return maintenant_cameroun().date()
