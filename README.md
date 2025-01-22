# README – Projet WaterBnB / Piscine connectée

Bonjour,

Mon application s'organise de la façon suivante :

- **Côté serveur** : une application Flask + MongoDB gérant l’état des piscines et l’historique de location.
- **Côté ESP32** : un code Arduino/PlatformIO qui envoie des mesures (température, luminosité, etc.) et reçoit des informations du serveur via MQTT.
- **Côté Node-Red** : un dashboard qui permet de réserver une piscine.

La communication entre l’ESP32 et le serveur se fait par **MQTT** :

1. L’ESP **publie** régulièrement des messages sur le topic général `uca/iot/piscine`, contenant ses mesures.
2. Le serveur **répond** sur un **topic spécifique** `uca/iot/piscine/<pool_id>/state` dès qu’il y a un changement d’état (piscine occupée/libre) ou une tentative d’accès alors qu’elle est occupée.
3. L’ESP souscrit à ces deux topics pour **mettre à jour** la couleur de son ruban LED :
   - **Vert** si la piscine est libre,
   - **Jaune** si la piscine est occupée,
   - **Rouge** pendant 30 secondes après une tentative de réservation alors que la piscine était déjà occupée.

**Attention** : Il y a une grosse latence au niveau des réponses envoyées de Render vers l’ESP (au moins 1 minute :( ...). Le backend fonctionne bien mieux en local que sur Render.


liens Github du projet : https://github.com/NoeFBou/WaterBnB_fn411036
liens du dashboard MongoDB : https://charts.mongodb.com/charts-project-0-cfqbhtu/public/dashboards/0f3a95b0-e295-4398-acdd-8b0b9cb9d55e
liens de render pour faire des tests :https://waterbnb-fn411036.onrender.com/open?idswp=P_22106244&idu=florence 

## Table des matières

1. [Architecture du projet](#architecture-du-projet)
2. [Pré-requis](#pré-requis)
3. [Configuration du serveur](#configuration-du-serveur)
4. [Lancement du serveur Flask](#lancement-du-serveur-flask)
5. [Fonctionnalités principales](#fonctionnalités-principales)
6. [Notes et améliorations possibles](#notes-et-améliorations-possibles)
7. [Licence](#licence)

---

## 1. Architecture du projet

Du côté de l'ESP, par rapport au dernier rendu, j'ai modifié les fichiers `regul.ino`, `sensors.ino` et `mqtt.ino`.
Pour le dashboard sur node-red, j'ai juste rajouté la map avec la possibilité de réserver une piscine avec un liens vers mon render.
```
ProjetPiscine/
├── static/                (contient les assets images, CSS de la page web)
├── app.py                 (Application Flask)
├── requirements.txt       (Librairies Python nécessaires)
├── templates/             (templates HTML de la page web)
├── flow node-red.json     (dashboard node-red)
└── adhoc/
    ├── regul/
    │   ├── regul.ino          (Code principal Arduino/PlatformIO)
    │   ├── sensors.ino        (Gestion capteurs/actionneurs)
    │   ├── mqtt_utils.ino     (Fonctions utilitaires MQTT)
    │   ├── wifi_utils.ino     (Fonctions utilitaires WiFi)
    │   ├── routes.ino         (Gestion des routes)
    │   ├── utils.ino          (Fonctions utilitaires)
    │   └── les autres fichiers .h
    └── data/                  (Contient les anciens fichiers SPIFF que je n'ai pas modifiés)
        ├── index.html
        ├── assets/
        ├── js/
        └── css/
```

- **À la racine/** contient le code Python :
  - Flask + MongoDB + MQTT (utilise la bibliothèque `flask_mqtt`).
  - Permet de gérer : l’historique des utilisateurs, la location des piscines, la publication sur MQTT du nouvel état de la piscine (`occupied` ou non).

- **adhoc/** contient le code Arduino/PlatformIO :
  - Connexion au WiFi
  - Publication régulière des données (température, luminosité, etc.) sur le topic `uca/iot/piscine`
  - Souscription au topic `uca/iot/piscine/<pool_id>/state` pour changer la couleur du ruban LED.

---

## 2. Pré-requis

- **Python 3.7+** (pour le backend)
- **Arduino IDE** (pour la partie ESP32).

---

## 3. Configuration du serveur

### Variables d’environnement
- `mongoDBpass` : mot de passe pour se connecter au cluster MongoDB  
  (mongoDBpass=kbkqq3942RSWYGX)

### Installation des librairies
```bash
pip install -r requirements.txt
```

---

## 4. Lancement du serveur Flask

Depuis le dossier, lancez :

```bash
python app.py
```

Par défaut, le serveur tournera sur `http://127.0.0.1:5000`. Les **routes** principales sont :

- `GET /open?idu=<user>&idswp=<pool_id>` : Test d’accès à la piscine, renvoie un template.
- `POST /open` : Valider une location, etc.

### Scheduler
- Un scheduler (via `flask_apscheduler`) se lance automatiquement et vérifie toutes les 60 secondes s’il y a des locations expirées pour libérer les piscines.

### MongoDB
- Les collections utilisées : `users`, `pools`, `usage`, `telemetry`. Elles sont créées automatiquement au besoin.

---

## 5. Fonctionnalités principales

- **Gestion d’utilisateurs** :
  - Si un utilisateur tente de réserver une piscine en ouvrant le lien avec la route `/open` avec un identifiant utilisateur qui n'est pas renseigné dans la base de données, l'utilisateur a la possibilité d’ajouter son nom d'utilisateur via un bouton sur la page web. Il peut alors recharger la page pour effectuer la réservation (si la piscine existe dans la base).
  
- **Gestion de piscines** :
  - Si un utilisateur tente de réserver une piscine qui n'est pas dans la base de données, une page d'erreur s'affiche.
  - Si l'utilisateur et la piscine sont présents dans la base, une page de réservation s'affiche avec les informations de la piscine et l'utilisateur a la possibilité de renseigner la durée souhaitée pour la réservation dans le formulaire. Un prix fictif est affiché, calculé en fonction des caractéristiques de la piscine. L'utilisateur peut valider sa réservation en cliquant sur le bouton du formulaire. Une page de récapitulatif de la réservation s'affiche alors.
  - Si l'utilisateur et la piscine sont présents dans la base mais que la piscine est déjà réservée, la page affiche un timer indiquant dans combien de temps la piscine sera de nouveau disponible.
  - Un liens tester une reservation https://waterbnb-fn411036.onrender.com/open?idswp=P_22411036&idu=florence
- **Historique** :
  - Les réservations sont stockées dans la collection `usage` de la base de données.
  - Les informations des piscines sont stockées en continu dans la base de données via MQTT. Si une piscine n'est pas encore présente, elle est ajoutée.
  
- **Statistiques** des piscines et des locations :
  - Le dashboard MongoDB avec les statistiques peut être accessible via la page web par n'importe qui en cliquant sur le bouton "Statistiques" ou via ce lien :
    [Dashboard MongoDB](https://charts.mongodb.com/charts-project-0-cfqbhtu/public/dashboards/0f3a95b0-e295-4398-acdd-8b0b9cb9d55e)

- **Tâche planifiée** (APS-Scheduler) pour libérer les piscines dont la location est expirée => publication MQTT `occupied=False`.
  
- **ESP32** :
  - Lit la température (DallasTemperature) et la luminosité (analogique).
  - Publie via MQTT (`uca/iot/piscine`) le JSON complet (identifiant de la piscine, utilisateur, etc.).
  - Souscrit également à `uca/iot/piscine/<pool_id>/state` :
    - **Vert** si `occupied == false`.
    - **Jaune** si `occupied == true`.
    - **Rouge** pendant 30 secondes si une tentative d’accès infructueuse est signalée.

---

## 6. Notes et améliorations possibles

- Ajouter une **authentification** plus robuste pour les requêtes Flask (JWT, sessions sécurisées, etc.).
- Gérer des **topics plus granulaires** pour séparer la télémetrie (`<pool_id>/telemetry`) de l’état (`<pool_id>/state`).
- Implémenter un **OTA** (Over-The-Air update) plus abouti sur l’ESP32.
- Sur l’ESP, faire une gestion plus fine de l’état (par exemple, baser le passage en rouge sur un timer interne sans bloquer la loop, etc.).

---

## Licence

MIT

---