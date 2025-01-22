# README – Projet WaterBnB / Piscine connectée

Bonjour 
Mon application s'organise de la facon suivante : 
- **Côté serveur** : une application Flask + MongoDB gérant l’état des piscines et l’historique de location.  
- **Côté ESP32** : un code Arduino/PlatformIO qui envoie des mesures (température, luminosité, etc.) et reçoit des informations du serveur via MQTT.

La communication entre l’ESP32 et le serveur se fait par **MQTT** :  
1. L’ESP **publie** régulièrement des messages sur le topic général `uca/iot/piscine`, contenant ses mesures.  
2. Le serveur **répond** sur un **topic spécifique** `uca/iot/piscine/<pool_id>/state` dès qu’il y a un changement d’état (piscine occupée/libre) ou une tentative d’accès alors qu’elle est occupée.  
3. L’ESP souscrit à ces deux topics pour **mettre à jour** la couleur de son ruban LED :  
   - **Vert** si la piscine est libre,  
   - **Jaune** si la piscine est occupée,  
   - **Rouge** pendant 30 secondes après une tentative de réservation alors que la piscine était déjà occupée.  

**Attention** Il y a une grosse latence au niveau des reponses envoyés de render vers l'esp (au moins 1 minute :( ...).Le backend marche bie nmieux en local que sur render,


## Table des matières

1. [Architecture du projet](#architecture-du-projet)  
2. [Pré-requis](#pré-requis)  
3. [Configuration du serveur](#configuration-du-serveur)  
4. [Lancement du serveur Flask](#lancement-du-serveur-flask)  
5. [Fonctionnalités principales](#fonctionnalités-principales)  
6. [Notes et améliorations possibles](#notes-et-améliorations-possibles)  

---

## 1. Architecture du projet

Du coté de l'esp, par rapport au derniers rendu, j'ai modifiés le fichier regul.ino, sensors.ino et mqtt.ino.

```
ProjetPiscine/
├── static/                (contient les assets images, css de la page web)
├── app.py                 (Application Flask)
├── requirements.txt       (Librairies Python nécessaires)
├── static/                (templates HTML de la page web)
└── adhoc/
    ├── regul/
    │   ├── regul.ino          (Code principal Arduino/PlatformIO)
    │   ├── sensors.ino        (Gestion capteurs/actionneurs)
    │   ├── mqtt_utils.ino     (Fonctions utilitaires MQTT)
    │   ├── wifi_utils.ino     (Fonctions utilitaires WiFi)
	│   ├── routes.ino         (Gestion des routes)
    │   ├── utils.ino     	   (Fonctions utilitaires)
    │   └── les autres fichiers .h
    └── data/				   (Contient les anciens fichiers SPIFF que je n'ai pas modifiés)
        ├── index.html
        ├── assets/
		├── js/
        └── css/
```

- **A la racine/** contient le code Python :  
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
- Un scheduler (via `flask_apscheduler`) se lance automatiquement et vérifie toutes les 60s s’il y a des locations expirées pour libérer les piscines.  

### MongoDB
- Les collections utilisées : `users`, `pools`, `usage`, `telemetry`. Elles sont créées automatiquement au besoin.  

---

## 5. Fonctionnalités principales

- **Gestion d’utilisateurs** en base (`users` collection).  
  - Si un utilisateur tente de reserver une piscine en ouvrant le liens avec la route /open... avec un d'utilisateur qui n'est pas renseigné dans la base de donnée, l'utilisateur à la possibilité de d'ajouter son nom d'utilisateur via un bouton sur la page web. Il peut alors recharger la page pour effectuer la reservation(si la piscine existe dans la base)
- **Gestion de piscines** (`pools` collection) :  
  - Si  un utilisateur tente de reserver une piscine qui n'est pas dans la base de donnée, une page d'erreur s'affiche
  - Si l'utilisateur
- **Historique** de location (`usage` collection) :  
  - Document qui stocke `user`, `pool_id`, `start`, `end`, `price`, etc.  
- **Tâche planifiée** (APS-Scheduler) pour libérer les piscines dont la location est expirée => publication MQTT `occupied=False`.  
- **ESP32** :  
  - Lit la température (DallasTemperature) et la luminosité (analogique).  
  - Publie via MQTT (`"uca/iot/piscine"`) un JSON complet (identifiant de la piscine, user, etc.).  
  - Souscrit également à `"uca/iot/piscine/<pool_id>/state"` :  
    - **Vert** si `occupied == false`.  
    - **Jaune** si `occupied == true`.  
    - **Rouge** 30 s si un `info` signale un accès infructueux.  

---

## 6. Notes et améliorations possibles

- Ajouter une **authentification** plus robuste pour les requêtes Flask (JWT, sessions sécurisées, etc.).  
- Gérer des **topics plus granulaires** pour séparer la télémetrie (`<pool_id>/telemetry`) de l’état (`<pool_id>/state`).  
- Implémenter un **OTA** (Over-The-Air update) plus abouti sur l’ESP32.  
- Sur l’ESP, faire une gestion plus fine de l’état (ex. baser le passage en rouge sur un timer interne sans bloquer la loop, etc.).  

---

## Licence

MIT

---


