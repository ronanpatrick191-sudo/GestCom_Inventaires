# -*- coding: utf-8 -*-
# Indique à Python que ce fichier peut contenir des caractères accentués (encodage UTF-8).
"""
smtp_service.py -- Service email automatique pour GestCom
Envoie des alertes quand un produit est en rupture ou stock bas.

Configuration dans development.ini :
    smtp.host     = smtp.gmail.com
    smtp.port     = 587
    smtp.user     = ton.email@gmail.com
    smtp.password = ton_mot_de_passe_app
    smtp.dest     = gerant@boutique.cm
"""
import smtplib
# Module standard Python pour se connecter à un serveur SMTP et envoyer des emails.
from email.mime.text import MIMEText
# Permet de créer la partie "texte/HTML" du contenu d'un email.
from email.mime.multipart import MIMEMultipart
# Permet de construire un email pouvant contenir plusieurs parties (ici : juste du HTML).
from .temps import maintenant_cameroun
# Heure locale du Cameroun (UTC+1), pour dater les emails d'alerte à l'heure
# que verra le commerçant et pas celle du serveur.
# Pour insérer la date/heure actuelle dans le corps de l'email.


def envoyer_alerte_stock(settings, produit_nom, stock_actuel,
                         seuil, type_alerte='rupture', url_inventaire=None):
    """
    Envoie un email d'alerte au gerant.

    Args:
        settings        : dictionnaire de config Pyramid (depuis development.ini)
        produit_nom     : nom du produit en alerte
        stock_actuel    : quantite restante
        seuil           : seuil minimum configure
        type_alerte     : 'rupture' ou 'seuil_bas'
        url_inventaire  : URL absolue de la page Inventaire (request.route_url('inventaire')),
                          pour que le lien du bouton fonctionne aussi en production.
    """
    host     = settings.get('smtp.host',     'smtp.gmail.com')
    # Adresse du serveur SMTP ; "smtp.gmail.com" si non défini dans la config.
    port     = int(settings.get('smtp.port', 587))
    # Port de connexion SMTP, converti en nombre entier (587 par défaut).
    user     = settings.get('smtp.user',     '')
    # Adresse email de l'expéditeur (le compte Gmail qui envoie l'alerte).
    password = settings.get('smtp.password', '')
    # Mot de passe d'application associé à ce compte Gmail.
    dest     = settings.get('smtp.dest',     user)
    # Adresse du destinataire ; si non définie, l'email se renvoie à lui-même (user).

    if not user or not password:
        # Si l'identifiant ou le mot de passe manque, impossible d'envoyer un email.
        print('[SMTP] Configuration manquante — email non envoye')
        return False
        # On arrête ici et on signale l'échec à l'appelant.

    # ── Construire le message ────────────────────────────────
    if type_alerte == 'rupture':
        # Cas le plus grave : le produit n'a plus aucun stock.
        sujet  = f'[GestCom] RUPTURE DE STOCK : {produit_nom}'
        niveau = 'RUPTURE'
        couleur = '#E24B4A'
        # Rouge : couleur d'alerte forte pour une rupture totale.
    else:
        # Cas moins grave : le stock est bas mais pas encore épuisé.
        sujet  = f'[GestCom] Stock bas : {produit_nom}'
        niveau = 'STOCK BAS'
        couleur = '#EF9F27'
        # Orange : couleur d'avertissement pour un stock bas.

    maintenant = maintenant_cameroun().strftime('%d/%m/%Y a %H:%M')
    # Date et heure actuelles au Cameroun, mises en forme pour l'email.

    # Ci-dessous : le contenu HTML complet de l'email (mise en page + style CSS en ligne).
    # Les valeurs entre {accolades} (couleur, niveau, produit_nom, etc.) sont injectées
    # automatiquement grâce au f-string (le "f" devant les triples guillemets).
    corps_html = f"""
    <html><body style="font-family:Arial,sans-serif;max-width:500px;margin:0 auto">
      <!-- Bandeau coloré en haut de l'email, avec le niveau d'alerte -->
      <div style="background:{couleur};padding:16px 20px;border-radius:8px 8px 0 0">
        <h2 style="color:#fff;margin:0;font-size:16px">{niveau} — GestCom</h2>
      </div>
      <!-- Corps principal de l'email -->
      <div style="background:#f9f9f9;padding:20px;border:1px solid #e0e0e0;
                  border-top:none;border-radius:0 0 8px 8px">
        <p style="font-size:14px;color:#333">Bonjour,</p>
        <p style="font-size:14px;color:#333">
          Une alerte a ete detectee dans votre boutique GestCom :
        </p>
        <!-- Tableau récapitulatif : produit / stock actuel / seuil / date -->
        <table style="width:100%;border-collapse:collapse;margin:16px 0">
          <tr style="background:#fff;border:1px solid #e0e0e0">
            <td style="padding:10px 14px;color:#666;font-size:13px">Produit</td>
            <td style="padding:10px 14px;font-weight:bold;font-size:13px">
              {produit_nom}
            </td>
          </tr>
          <tr style="background:#f5f5f5;border:1px solid #e0e0e0">
            <td style="padding:10px 14px;color:#666;font-size:13px">Stock actuel</td>
            <td style="padding:10px 14px;font-weight:bold;color:{couleur};
                       font-size:13px">
              {stock_actuel} unites
            </td>
          </tr>
          <tr style="background:#fff;border:1px solid #e0e0e0">
            <td style="padding:10px 14px;color:#666;font-size:13px">
              Seuil minimum
            </td>
            <td style="padding:10px 14px;font-size:13px">{seuil} unites</td>
          </tr>
          <tr style="background:#f5f5f5;border:1px solid #e0e0e0">
            <td style="padding:10px 14px;color:#666;font-size:13px">Date</td>
            <td style="padding:10px 14px;font-size:13px">{maintenant}</td>
          </tr>
        </table>
        <p style="font-size:13px;color:#666">
          Pensez a reapprovisionner votre stock rapidement pour eviter
          les ruptures de vente.
        </p>
        <!-- Bouton/lien qui ramène directement vers la page Inventaire de l'app -->
        <div style="background:#1D9E75;padding:10px 18px;border-radius:6px;
                    display:inline-block;margin-top:8px">
          <a href="{url_inventaire or 'http://localhost:6543/inventaire'}"
             style="color:#fff;text-decoration:none;font-size:13px;font-weight:bold">
            Voir l'inventaire →
          </a>
        </div>
        <p style="font-size:11px;color:#999;margin-top:20px">
          GestCom — Systeme de gestion commerciale
        </p>
      </div>
    </body></html>
    """

    # ── Envoyer via SMTP ─────────────────────────────────────
    try:
        msg = MIMEMultipart('alternative')
        # Crée l'enveloppe de l'email (type "alternative" = une seule version, ici HTML).
        msg['Subject'] = sujet
        # Définit l'objet (titre) de l'email.
        msg['From']    = user
        # Définit l'expéditeur.
        msg['To']      = dest
        # Définit le destinataire.
        msg.attach(MIMEText(corps_html, 'html', 'utf-8'))
        # Attache le contenu HTML construit plus haut comme corps du message.

        with smtplib.SMTP(host, port) as srv:
            # Ouvre une connexion au serveur SMTP ; se ferme automatiquement à la fin du bloc "with".
            srv.ehlo()
            # Se présente au serveur SMTP (étape standard du protocole).
            srv.starttls()
            # Passe en connexion chiffrée (sécurisée) avant d'envoyer les identifiants.
            srv.login(user, password)
            # Se connecte avec l'adresse email et le mot de passe d'application.
            srv.sendmail(user, dest, msg.as_string())
            # Envoie réellement l'email au destinataire.

        print(f'[SMTP] Email envoye : {sujet} -> {dest}')
        # Confirmation dans les logs du serveur (utile pour vérifier que ça fonctionne).
        return True
        # Signale à l'appelant que l'envoi a réussi.

    except smtplib.SMTPAuthenticationError:
        # Erreur spécifique : mauvais identifiant/mot de passe.
        print('[SMTP] Erreur authentification — verifiez user/password dans .ini')
        return False
    except Exception as e:
        # Toute autre erreur (réseau, serveur injoignable, etc.).
        print(f'[SMTP] Erreur envoi email : {e}')
        return False


def envoyer_alertes_groupees(settings, produits_en_alerte, url_inventaire=None):
    """
    Envoie un email d'alerte pour chaque produit actuellement sous son
    seuil (utilise par le bouton "Envoyer alerte email" de la page Stock).
    Retourne le nombre d'emails envoyes avec succes.
    """
    nb_envoyes = 0
    # Compteur du nombre d'emails effectivement envoyés avec succès.
    for produit in produits_en_alerte:
        # Parcourt chaque produit passé en argument (liste des produits en alerte).
        type_alerte = 'rupture' if produit.stock == 0 else 'seuil_bas'
        # Détermine le type d'alerte selon que le stock soit à zéro ou juste bas.
        ok = envoyer_alerte_stock(
            settings,
            produit_nom     = produit.nom,
            stock_actuel    = produit.stock,
            seuil           = produit.seuil,
            type_alerte     = type_alerte,
            url_inventaire  = url_inventaire,
        )
        # Envoie un email individuel pour ce produit, en réutilisant la fonction ci-dessus.
        if ok:
            # Si l'envoi a réussi...
            nb_envoyes += 1
            # ...on incrémente le compteur.
    return nb_envoyes
    # Renvoie le nombre total d'emails envoyés avec succès.


def envoyer_email_test(settings):
    """Envoie un email de test pour verifier la configuration SMTP."""
    return envoyer_alerte_stock(
        settings,
        produit_nom  = 'Produit de test',
        stock_actuel = 0,
        seuil        = 10,
        type_alerte  = 'rupture'
    )
    # Simule une alerte de rupture avec des données factices, juste pour tester
    # que la configuration SMTP (host/user/password) fonctionne correctement.
