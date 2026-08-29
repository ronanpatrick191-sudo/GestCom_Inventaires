"""
securite.py — Protection d'accès de niveau A (mot de passe unique)

Tant que GestCom n'a pas de vrais comptes utilisateurs (prévu en v2), toute
l'application est protégée derrière UN seul identifiant / mot de passe,
partagé par les personnes autorisées (toi l'administrateur, le client, les
gérants de boutique).

Mécanisme : authentification HTTP « Basic ».
  - le navigateur affiche sa fenêtre de connexion native ;
  - l'identifiant et le mot de passe attendus viennent de .env
    (ACCES_UTILISATEUR / ACCES_MOTDEPASSE), jamais du code ni du .ini versionné ;
  - fonctionne à l'identique en local, sur PythonAnywhere et sur un VPS,
    sans aucune configuration serveur externe.

Si ACCES_MOTDEPASSE n'est pas défini, la protection est DÉSACTIVÉE et un
avertissement est écrit dans les logs à chaque démarrage. En production,
cette variable DOIT être définie.

Limites assumées de ce niveau A : pas de déconnexion, pas de comptes
distincts, pas de rôles. Ça viendra avec la vraie gestion multi-utilisateurs
(v2). Le but ici est seulement d'empêcher un inconnu d'ouvrir l'application.
"""
import base64
import binascii
import hmac
import logging

from pyramid.httpexceptions import HTTPUnauthorized

journal = logging.getLogger("GestCom")

# Préfixe des fichiers statiques (CSS, images) : laissés passer sans mot de
# passe, sinon la page d'erreur elle-même s'afficherait sans style.
PREFIXE_STATIQUE = "/static/"

# En-tête renvoyé au navigateur pour qu'il ouvre sa fenêtre de connexion.
EN_TETE_DEMANDE = 'Basic realm="GestCom", charset="UTF-8"'


def _identifiants_valides(request, utilisateur_attendu, motdepasse_attendu):
    """Vrai si l'en-tête Authorization contient le bon couple identifiant/mot de passe."""
    en_tete = request.headers.get("Authorization", "")
    # Format attendu : "Basic <base64(identifiant:motdepasse)>"
    if not en_tete.startswith("Basic "):
        return False
    try:
        decode = base64.b64decode(en_tete[6:].strip()).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        # base64 invalide, ou octets qui ne sont pas de l'UTF-8 : accès refusé.
        return False
    utilisateur, separateur, motdepasse = decode.partition(":")
    if not separateur:
        # Pas de ":" → en-tête mal formé.
        return False
    # hmac.compare_digest : comparaison à durée constante (ne fuit pas
    # d'information via le temps de réponse).
    ok_utilisateur = hmac.compare_digest(utilisateur, utilisateur_attendu)
    ok_motdepasse = hmac.compare_digest(motdepasse, motdepasse_attendu)
    return ok_utilisateur and ok_motdepasse


def tween_protection_acces(handler, registry):
    """
    Tween Pyramid : s'exécute avant chaque vue et bloque l'accès si le
    mot de passe unique n'est pas fourni (ou est incorrect).
    """
    reglages = registry.settings
    utilisateur_attendu = reglages.get("acces.utilisateur") or ""
    motdepasse_attendu = reglages.get("acces.motdepasse") or ""

    if not motdepasse_attendu:
        journal.warning(
            "SECURITE : ACCES_MOTDEPASSE non defini — l'application est "
            "ACCESSIBLE SANS MOT DE PASSE. A corriger avant toute mise en ligne."
        )

        def tween_desactive(request):
            return handler(request)

        return tween_desactive

    def tween(request):
        # Les fichiers statiques ne sont pas protégés.
        if request.path.startswith(PREFIXE_STATIQUE):
            return handler(request)
        if _identifiants_valides(request, utilisateur_attendu, motdepasse_attendu):
            return handler(request)
        # Identifiants absents ou incorrects → 401 + demande d'authentification.
        reponse = HTTPUnauthorized(headers={"WWW-Authenticate": EN_TETE_DEMANDE})
        reponse.content_type = "text/plain; charset=utf-8"
        reponse.text = "Acces reserve — identifiants requis."
        return reponse

    return tween


def includeme(config):
    """Appelé par Pyramid via config.include('.securite') dans __init__.py."""
    config.add_tween("GestCom.securite.tween_protection_acces")
