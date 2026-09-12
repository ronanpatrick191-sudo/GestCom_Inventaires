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
│   ├── securite.py        ← protection d'accès niveau A (mot de passe unique)
│   ├── temps.py           ← heure locale du Cameroun (WAT, UTC+1) pour toute l'app
│   ├── smtp_service.py    ← emails d'alerte stock (SMTP Gmail)
│   ├── mobile_money_service.py ← QR + paiements Orange Money / MTN MoMo (mode démo v1)
│   ├── templates/
│   │   ├── base.jinja2    ← layout commun avec sidebar
│   │   ├── dashboard/index.jinja2
│   │   ├── inventaire/list.jinja2  (page "Produits")
│   │   ├── stock/index.jinja2
│   │   ├── rapport/index.jinja2
│   │   ├── transactions/list.jinja2
│   │   ├── caisse/index.jinja2
│   │   └── alertes/list.jinja2
│   ├── static/            ← vide pour l'instant : CSS géré dans base.jinja2 + Bootstrap CDN
│   └── config/
│       ├── development.ini
│       └── production.ini
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
| transactions           | /transactions (?periode=jour/semaine/mois) | GET |
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
- [x] Transactions — historique filtrable jour/semaine/mois (route `transactions`)
- [x] Protection d'accès niveau A — mot de passe unique (`securite.py`)
- [ ] Export PDF/Excel (catalogue, rapport) — pas encore commencé

## Paiements mobiles — état réel
**Décision du 29/08/2026 : Orange Money et MTN MoMo restent en mode démo
pour tout le v1**, par choix assumé (pas de contrat marchand ni sandbox
pour l'instant — ni le coût ni le délai ne collent avec la livraison du
31/08/2026). `mobile_money_service.py` ne fait plus aucun appel réseau vers
Orange/MTN : le QR est généré côté serveur, et le commerçant confirme
manuellement la réception du paiement (bouton "Marquer comme payée" en
caisse) — exactement comme pour une vente cash. Les variables
`ORANGE_MONEY_API_KEY` / `MTN_MOMO_API_KEY` etc. dans `.env.example`
restent présentes mais ne sont plus lues.

Pour activer les vraies API plus tard (sandbox ou production), il faudra :
souscrire aux portails développeur Orange (`developer.orange.com`) et MTN
(`momodeveloper.mtn.com`), obtenir les identifiants (voir liens dans la
conversation avec Claude du 29/08/2026), puis remplacer le contenu de
`initier_paiement()` / `verifier_paiement()` dans `mobile_money_service.py`
par de vrais appels OAuth2 — la signature des deux fonctions ne changera
pas, donc `views.py` n'aura pas besoin d'être modifié.

## Fonctions v2 (après livraison — ne pas coder maintenant)
- Prévisions IA avec Pandas
- Multi-utilisateurs avec rôles
- Comptabilité avancée / P&L
- Application mobile PWA