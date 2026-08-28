# GestCom_Inventaires — Contexte pour Claude Code

## Identité du projet
Application de gestion commerciale et d'inventaires destinée aux commerçants au Cameroun et en Belgique.
Version actuelle : v1 (livraison avant le 31 août 2026).

## Stack technique
- **Backend** : Python 3.12 + Pyramid Framework
- **Base de données** : SQLAlchemy ORM + MySQL/MariaDB
- **Templates** : Jinja2
- **Frontend** : Bootstrap 5 + Chart.js
- **Paiements** : QR Code + Orange Money + MTN MoMo
- **Emails** : SMTP Gmail (alertes stock automatiques)
- **Devise** : FCFA (franc CFA) — toujours afficher en entiers

## Structure des fichiers
```
GestCom_Inventaires/
├── GestCom/
│   ├── __init__.py        ← routes + config Pyramid
│   ├── main_models.py     ← connexion SQLAlchemy + MySQL
│   ├── models.py          ← Produit, Transaction, Alerte
│   ├── views.py           ← TOUTES les vues (un seul fichier)
│   ├── smtp_service.py    ← emails d'alerte stock (SMTP Gmail)
│   ├── mobile_money_service.py ← QR + paiements Orange Money / MTN MoMo
│   ├── templates/
│   │   ├── base.jinja2    ← layout commun avec sidebar
│   │   ├── dashboard/index.jinja2
│   │   ├── inventaire/list.jinja2  (page "Produits")
│   │   ├── stock/index.jinja2
│   │   ├── rapport/index.jinja2
│   │   ├── caisse/index.jinja2
│   │   └── alertes/list.jinja2
│   ├── static/
│   │   ├── css/app.css
│   │   └── img/
│   └── config/
│       └── development.ini
├── scripts/
│   └── init_db.py         ← initialisation données de test
├── pyproject.toml
└── CLAUDE.md              ← ce fichier
```

## Conventions importantes
- Noms de variables et fonctions en **français**
- Montants TOUJOURS en FCFA entiers avec `round()`
- Un seul fichier `views.py` — pas de sous-dossiers pour les vues
- Modèles dans un seul fichier `models.py`
- Couleur principale : `#1D9E75` (vert GestCom)
- Classes Bootstrap 5 pour le CSS, pas de CSS custom complexe

## Routes définies
| Route                  | URL                               | Méthode |
|------------------------|------------------------------------|---------|
| home                   | /                                  | GET     |
| dashboard              | /dashboard (?periode=jour/semaine/mois) | GET |
| inventaire             | /inventaire (page "Produits")     | GET     |
| produit_ajouter        | /inventaire/ajouter               | POST    |
| produit_modifier       | /inventaire/modifier/{id}         | POST    |
| produit_supprimer      | /inventaire/supprimer/{id}        | POST    |
| stock                  | /stock                            | GET     |
| stock_alerte_groupee   | /stock/alerte-email               | POST    |
| rapport                | /rapport                          | GET     |
| recherche              | /recherche (?q=...)               | GET     |
| caisse                 | /caisse                           | GET     |
| vente_enregistrer      | /caisse/vendre                    | POST    |
| caisse_mtn             | /caisse/mtn/payer                 | POST    |
| caisse_mtn_verif       | /caisse/mtn/verifier/{ref_id}     | GET     |
| caisse_orange          | /caisse/orange/payer              | POST    |
| caisse_orange_verif    | /caisse/orange/verifier/{ref_id}  | GET     |
| alertes                | /alertes                          | GET     |
| alerte_lire            | /alertes/lire/{id}                | POST    |
| alerte_email_test      | /alertes/test-email               | POST    |

## Tables MySQL
- `produits` : id, nom, categorie, prix_achat, prix_vente, stock, seuil, unite, date_ajout
- `transactions` : id, produit_id (FK), quantite, montant, mode_paiement, statut, reference_mtn, date_vente
- `alertes` : id, produit_id (FK), message, type_alerte, lue, date_alerte

## Commandes utiles
```bash
# Installer les dépendances
pip install -e .

# Initialiser la base de données (une seule fois)
python scripts/init_db.py

# Lancer le serveur de développement
pserve GestCom/config/development.ini --reload

# URL de l'app
http://localhost:6543/dashboard
```

## Fonctions v1 (à livrer avant le 31 août 2026)
- [x] Dashboard avec KPIs FCFA réels depuis MySQL (filtre Jour/Semaine/Mois)
- [x] Produits — catalogue + CRUD (route `inventaire`)
- [x] Stock — niveaux, valeur totale, ruptures, alerte email groupée
- [x] Rapport financier — CA/profit mensuel, tendance 6 mois
- [x] Caisse — enregistrer une vente (stock auto mis à jour)
- [x] QR Code paiement MTN / Orange Money (généré côté serveur)
- [x] Email SMTP alerte rupture de stock
- [x] Recherche globale (topbar)
- [ ] Export PDF/Excel (catalogue, rapport) — pas encore commencé

## Paiements mobiles — état réel
Le flux Orange Money / MTN MoMo (`mobile_money_service.py`) est câblé pour
appeler les vraies API si `ORANGE_MONEY_API_KEY`/`MTN_MOMO_API_KEY` sont
définies dans `.env` (voir `.env.example`). **Aucun identifiant marchand
n'est encore obtenu** → tant qu'ils ne le sont pas, la caisse fonctionne en
mode démo (QR généré, confirmation manuelle du paiement par le commerçant).
À tester en conditions réelles dès que les accès Orange/MTN seront en main.

## Fonctions v2 (après livraison — ne pas coder maintenant)
- Prévisions IA avec Pandas
- Multi-utilisateurs avec rôles
- Comptabilité avancée / P&L
- Application mobile PWA