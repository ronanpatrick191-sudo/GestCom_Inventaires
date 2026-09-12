# Déploiement de GestCom sur PythonAnywhere

Checklist complète, dans l'ordre. Chaque commande est à copier-coller telle quelle
(en remplaçant `TONNOM` par ton nom d'utilisateur PythonAnywhere).

## 1. Créer le compte et passer au plan Developer (10 $/mois)

1. https://www.pythonanywhere.com/ → **Pricing & signup** → **Create a Beginner account** (gratuit au départ).
2. Renseigne username / email / mot de passe → confirme l'email reçu.
3. Connecte-toi, puis **Account** (en haut à droite) → onglet **"Upgrade/Downgrade"**.
4. Choisis **Developer — 10 $/mois**, renseigne une carte bancaire, confirme.
5. Vérifie sur le **Dashboard** qu'un onglet **Databases** est apparu (absent en gratuit).

## 2. Vérifier que Python 3.12 est disponible

**Account** → onglet **"System Image"** → vérifie que `3.12` apparaît dans la liste.
(Si seule une version antérieure est proposée, préviens-moi avant de continuer — le
projet exige Python ≥ 3.12.)

## 3. Créer la base de données MySQL

1. Onglet **Databases**.
2. Définis un **mot de passe MySQL** (différent du mot de passe du compte) → note-le.
3. Section **"Create a database"** → tape `gestcom_db` → **Create**.
4. PythonAnywhere l'appelle en réalité **`TONNOM$gestcom_db`** (le `$` est obligatoire,
   c'est leur convention pour isoler les bases par compte).
5. Note l'**hôte MySQL** affiché sur cette page : `TONNOM.mysql.pythonanywhere-services.com`.

## 4. Récupérer le code

Dashboard → **New console** → **Bash**, puis :

```bash
git clone https://github.com/ronanpatrick191-sudo/GestCom_Inventaires.git
```

## 5. Créer l'environnement virtuel et installer les dépendances

Toujours dans la console Bash :

```bash
mkvirtualenv --python=python3.12 gestcom-venv
cd ~/GestCom_Inventaires
pip install -e .
```

`mkvirtualenv` active automatiquement l'environnement après création (le prompt
affiche `(gestcom-venv)`). Si tu rouvres une console plus tard : `workon gestcom-venv`.

## 6. Créer le fichier `.env` sur le serveur

**Ce fichier n'existe que sur le serveur — il n'est jamais dans Git.**

```bash
nano ~/GestCom_Inventaires/.env
```

Colle (en remplaçant les valeurs) :

```
DATABASE_URL=mysql+pymysql://TONNOM:MOTDEPASSE_MYSQL@TONNOM.mysql.pythonanywhere-services.com/TONNOM$gestcom_db

ACCES_UTILISATEUR=gestcom
ACCES_MOTDEPASSE=CHANGE_MOI_LONG_ET_ALEATOIRE

SMTP_USER=ton.email@gmail.com
SMTP_PASSWORD=ton_mot_de_passe_application_gmail
SMTP_DEST=gerant@boutique.cm
```

Génère un mot de passe d'accès solide avant de le coller :

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(24))"
```

`Ctrl+O` puis `Entrée` pour enregistrer, `Ctrl+X` pour quitter nano.

## 7. Créer la Web App (configuration manuelle)

1. Onglet **Web** → **Add a new web app** → garde le domaine `TONNOM.pythonanywhere.com` → **Next**.
2. Choisis **Manual configuration** (PAS "Django" ni "Flask") → sélectionne **Python 3.12** → **Next**.
3. Sur la page de configuration de l'app :
   - **Virtualenv** : renseigne `/home/TONNOM/.virtualenvs/gestcom-venv`
   - **Code → Source code** : `/home/TONNOM/GestCom_Inventaires`
   - **Code → WSGI configuration file** : clique le lien, **supprime tout le contenu**,
     colle le contenu de [`deploy/wsgi_pythonanywhere.py`](wsgi_pythonanywhere.py)
     (en remplaçant `TONNOM`) → **Save**.
4. Retour onglet **Web** → bouton vert **Reload TONNOM.pythonanywhere.com**.

## 8. Vérifier

Ouvre `https://TONNOM.pythonanywhere.com/dashboard` :

- Le navigateur doit demander un identifiant/mot de passe (protection niveau A,
  voir `GestCom/securite.py`) → utilise `ACCES_UTILISATEUR` / `ACCES_MOTDEPASSE`.
- Le tableau de bord doit s'afficher ensuite.

**En cas d'erreur** : onglet **Web** → section **Log files** → **Error log**
(la plupart des soucis de démarrage y sont expliqués clairement).

Les tables MySQL (`produits`, `transactions`, `alertes`) sont créées **automatiquement**
au premier démarrage par `main_models.py` (`Base.metadata.create_all`) — aucune
commande à lancer pour ça.

> ⚠️ **Ne lance PAS `scripts/init_db.py` sur cette base** : il insère des données
> de démonstration (produits/ventes fictifs). À réserver à une base de test séparée.

## 9. Mises à jour futures

Après chaque `git push` depuis ta machine :

```bash
cd ~/GestCom_Inventaires
git pull
workon gestcom-venv
pip install -e .          # seulement si de nouvelles dépendances ont été ajoutées
```

Puis onglet **Web** → **Reload TONNOM.pythonanywhere.com**.

## 10. Plus tard : nom de domaine personnalisé

Quand tu auras acheté un domaine : onglet **Web** → **Add a new web app** n'est pas
nécessaire, utilise plutôt la section **"Add a new domain"** en bas de la config de
l'app existante. PythonAnywhere fournit alors un enregistrement DNS **CNAME** à créer
chez ton registrar, et gère lui-même le certificat HTTPS. On le fera ensemble le
moment venu.
