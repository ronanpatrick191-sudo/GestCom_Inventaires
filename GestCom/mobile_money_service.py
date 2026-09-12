# -*- coding: utf-8 -*-
# Indique à Python que ce fichier peut contenir des caractères accentués (encodage UTF-8).
"""
mobile_money_service.py -- Paiements mobiles pour GestCom (Orange Money / MTN MoMo)

Genere le QR code de paiement cote serveur. Pour le v1, Orange Money et MTN
MoMo restent en MODE DEMO de facon deliberee (decision du 29/08/2026, voir
CLAUDE.md "Paiements mobiles - etat reel") : le client scanne le QR, mais
c'est le commercant qui confirme manuellement la reception du paiement,
exactement comme pour une vente cash. Aucun appel reseau vers Orange/MTN
n'est fait.

L'integration des vraies API (OAuth2, requetes reelles, webhooks) est
volontairement reportee : elle necessite des identifiants marchand
(sandbox ou production) qui ne sont pas encore obtenus. Le jour ou cette
decision change, ces deux fonctions seront remplacees par de vrais appels
`requests` vers les API Orange Money Web Payment / MTN MoMo Collection —
la signature (parametres, valeurs de retour) est deja prevue pour ca et
n'aura pas besoin de changer cote views.py.
"""
import base64
# Permet de convertir les données binaires du QR code en texte, pour les insérer dans du HTML.
from io import BytesIO
# Fournit un "fichier en mémoire" (sans rien écrire sur le disque) pour stocker l'image du QR code.

import qrcode
# Bibliothèque qui génère des QR codes à partir d'un texte.

NOMS_OPERATEURS = {
    'orange': 'Orange Money',
    'mtn':    'MTN MoMo',
}
# Dictionnaire associant le code interne de l'opérateur à son nom complet affichable.

URI_SCHEMES = {
    'orange': 'orangemoney',
    'mtn':    'momo',
}
# Dictionnaire associant chaque opérateur au préfixe utilisé dans l'URL du QR code de paiement.


def generer_qr_base64(montant, reference, operateur):
    """
    Genere un QR code de paiement en PNG, encode en base64, pret a etre
    injecte directement dans un <img src="data:image/png;base64,...">.
    """
    scheme = URI_SCHEMES.get(operateur, operateur)
    # Récupère le préfixe d'URL correspondant à l'opérateur (ex: "orangemoney").
    data = (
        f'{scheme}://pay?amount={int(montant)}'
        f'&currency=XAF&ref={reference}&merchant=GestCom'
    )
    # Construit le texte encodé dans le QR code : montant, devise (XAF = FCFA), référence, marchand.

    img = qrcode.make(data, box_size=6, border=2)
    # Génère l'image du QR code à partir du texte "data" ci-dessus.
    buffer = BytesIO()
    # Crée un espace mémoire temporaire pour stocker l'image (sans fichier sur le disque).
    img.save(buffer, format='PNG')
    # Enregistre l'image du QR code dans ce buffer, au format PNG.
    encode = base64.b64encode(buffer.getvalue()).decode('ascii')
    # Convertit les octets de l'image en texte base64, utilisable directement dans du HTML.

    return f'data:image/png;base64,{encode}', data
    # Renvoie : 1) l'image prête à afficher dans un <img>, 2) le texte brut encodé (pour debug/log).


def initier_paiement(settings, operateur, montant, reference):
    """
    Demarre une demande de paiement mobile money.

    Toujours en mode demo pour le v1 (voir docstring du module) : la vente
    continue normalement, mais c'est le commercant qui confirmera la
    reception du paiement via le bouton "Marquer comme payee" en caisse.
    `settings` est conserve dans la signature pour que cette fonction
    puisse etre remplacee par un vrai appel API plus tard sans toucher a
    views.py, mais n'est pas utilise tant que la decision ne change pas.
    """
    return {'mode': 'demo', 'succes': True}


def verifier_paiement(settings, operateur, reference):
    """
    Interroge le statut d'un paiement mobile money.

    Toujours en mode demo pour le v1 : renvoie systematiquement
    'en_attente', jusqu'a ce que le commercant confirme manuellement via
    ?confirmer=1 (voir _verifier_paiement_mobile dans views.py).
    """
    return {'statut': 'en_attente', 'mode': 'demo'}
