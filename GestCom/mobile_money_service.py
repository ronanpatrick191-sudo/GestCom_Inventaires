# -*- coding: utf-8 -*-
# Indique à Python que ce fichier peut contenir des caractères accentués (encodage UTF-8).
"""
mobile_money_service.py -- Paiements mobiles pour GestCom (Orange Money / MTN MoMo)

Genere le QR code de paiement cote serveur (plus de dependance a un service
tiers comme qrserver.com). Si des cles API marchand sont configurees dans
.env (voir .env.example), les vraies API Orange Money / MTN MoMo sont
appelees. Tant qu'elles ne le sont pas, le module reste en "mode demo" :
le commercant confirme manuellement la reception du paiement.

Configuration dans development.ini / .env :
    orange_money.api_key       = ORANGE_MONEY_API_KEY
    orange_money.merchant_id   = ORANGE_MONEY_MERCHANT_ID
    mtn_momo.api_key           = MTN_MOMO_API_KEY
    mtn_momo.subscription_key  = MTN_MOMO_SUBSCRIPTION_KEY
"""
import base64
# Permet de convertir les données binaires du QR code en texte, pour les insérer dans du HTML.
from io import BytesIO
# Fournit un "fichier en mémoire" (sans rien écrire sur le disque) pour stocker l'image du QR code.

import qrcode
# Bibliothèque qui génère des QR codes à partir d'un texte.
import requests
# Bibliothèque pour envoyer des requêtes HTTP aux vraies API Orange Money / MTN MoMo.

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


def _cles_configurees(settings, operateur):
    # Fonction "privée" (préfixe _) : vérifie si les clés API du marchand sont bien renseignées.
    if operateur == 'orange':
        # Pour Orange, il faut à la fois la clé API et l'identifiant marchand.
        return bool(settings.get('orange_money.api_key') and settings.get('orange_money.merchant_id'))
    if operateur == 'mtn':
        # Pour MTN, il faut à la fois la clé API et la clé d'abonnement.
        return bool(settings.get('mtn_momo.api_key') and settings.get('mtn_momo.subscription_key'))
    return False
    # Opérateur inconnu : on considère qu'aucune clé n'est configurée.


def initier_paiement(settings, operateur, montant, reference):
    """
    Demarre une demande de paiement mobile money.

    Si l'API du marchand n'est pas configuree, retourne le mode demo :
    le commercant devra confirmer manuellement la reception du paiement
    (bouton "Marquer comme payee" cote caisse).
    """
    if not _cles_configurees(settings, operateur):
        # Aucun identifiant marchand disponible : on ne peut pas appeler la vraie API.
        return {'mode': 'demo', 'succes': True}
        # On renvoie un succès "simulé" : la vente continue, mais en mode démo.

    # ── Integration reelle (necessite des identifiants marchand valides) ──
    # Les endpoints exacts (sandbox/production) dependent du contrat
    # commercant signe avec Orange/MTN ; a completer une fois les acces
    # obtenus. En attendant, toute erreur reseau retombe proprement en
    # mode demo pour ne jamais bloquer une vente en caisse.
    try:
        if operateur == 'orange':
            # Appel de l'API réelle Orange Money pour lancer un paiement web.
            reponse = requests.post(
                'https://api.orange.com/orange-money-webpay/cm/v1/webpayment',
                headers={'Authorization': f"Bearer {settings['orange_money.api_key']}"},
                # En-tête d'authentification avec la clé API du marchand.
                json={
                    'merchant_key': settings['orange_money.merchant_id'],
                    'amount':       int(montant),
                    'currency':     'XAF',
                    'reference':    reference,
                },
                # Corps de la requête : identifiant marchand, montant, devise, référence de vente.
                timeout=10,
                # Abandonne l'appel si le serveur ne répond pas en 10 secondes.
            )
        else:
            # Appel de l'API réelle MTN MoMo (environnement de test "sandbox").
            reponse = requests.post(
                'https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay',
                headers={
                    'Authorization':           f"Bearer {settings['mtn_momo.api_key']}",
                    'Ocp-Apim-Subscription-Key': settings['mtn_momo.subscription_key'],
                    'X-Reference-Id':          reference,
                },
                # En-têtes requis par l'API MTN : clé API, clé d'abonnement, référence unique.
                json={
                    'amount':   str(int(montant)),
                    'currency': 'XAF',
                    'externalId': reference,
                },
                # Corps de la requête : montant (en texte), devise, identifiant externe de la vente.
                timeout=10,
            )
        reponse.raise_for_status()
        # Déclenche une erreur si le serveur a répondu avec un code d'erreur HTTP (4xx/5xx).
        return {'mode': 'api', 'succes': True}
        # Le paiement a bien été initié via la vraie API.
    except requests.RequestException as e:
        # Toute erreur réseau (serveur injoignable, timeout, erreur HTTP...) est interceptée ici.
        print(f'[MobileMoney] Erreur initiation {operateur} : {e} — repli en mode demo')
        return {'mode': 'demo', 'succes': True}
        # On bascule en mode démo plutôt que de bloquer la vente en caisse.


def verifier_paiement(settings, operateur, reference):
    """
    Interroge le statut d'un paiement mobile money aupres de l'operateur.
    En mode demo (pas de cles API), retourne toujours 'en_attente' : c'est
    au commercant de confirmer manuellement via le bouton dedie.
    """
    if not _cles_configurees(settings, operateur):
        # Sans clés API, impossible d'interroger le vrai statut du paiement.
        return {'statut': 'en_attente', 'mode': 'demo'}

    try:
        if operateur == 'orange':
            # Interroge l'API Orange Money pour connaître le statut de la transaction.
            reponse = requests.get(
                f'https://api.orange.com/orange-money-webpay/cm/v1/transactionstatus/{reference}',
                headers={'Authorization': f"Bearer {settings['orange_money.api_key']}"},
                timeout=10,
            )
        else:
            # Interroge l'API MTN MoMo pour connaître le statut de la transaction.
            reponse = requests.get(
                f'https://sandbox.momodeveloper.mtn.com/collection/v1_0/requesttopay/{reference}',
                headers={
                    'Authorization':           f"Bearer {settings['mtn_momo.api_key']}",
                    'Ocp-Apim-Subscription-Key': settings['mtn_momo.subscription_key'],
                },
                timeout=10,
            )
        reponse.raise_for_status()
        # Vérifie que la requête HTTP s'est bien passée (sinon lève une exception).
        statut_brut = reponse.json().get('status', '').upper()
        # Récupère le champ "status" de la réponse JSON et le met en majuscules.
        statut = 'paye' if statut_brut in ('SUCCESSFUL', 'SUCCESS') else 'en_attente'
        # Traduit le statut brut de l'opérateur en statut interne simple ("paye"/"en_attente").
        return {'statut': statut, 'mode': 'api'}
    except requests.RequestException as e:
        # En cas d'erreur réseau, on ne peut pas confirmer le paiement pour l'instant.
        print(f'[MobileMoney] Erreur verification {operateur} : {e}')
        return {'statut': 'en_attente', 'mode': 'demo'}
