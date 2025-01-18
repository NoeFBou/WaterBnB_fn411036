import json
import csv
import os
import atexit
import datetime
from datetime import datetime
from flask import request, redirect, url_for
from flask import jsonify
from flask import Flask
from flask import session
from flask import render_template
from datetime import datetime, timedelta

from flask_mqtt import Mqtt
from flask_pymongo import PyMongo
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from flask_apscheduler import APScheduler

# -----------------------------------------------------------------------------
# Paramètres d’accès MongoDB Atlas (Render va injecter la variable d’env)
password = os.environ.get("mongoDBpass") 

ADMIN = False  # Pour autoriser le script à insérer la liste des users en base

uri = f"mongodb+srv://noe:{password}@waterbnb.ti26c.mongodb.net/?retryWrites=true&w=majority&appName=WaterBnB"

# Create a new client and connect
client = MongoClient(uri, server_api=ServerApi('1'))

dbname = 'WaterBnB'
db = client[dbname]

# -----------------------------------------------------------------------------
# Vérification de la collection "users"
collname_users = 'users'
if collname_users not in db.list_collection_names():
    print(f"Collection {collname_users} inexistante ! Elle sera créée si ADMIN=True")

userscollection = db[collname_users]

# Pour initialiser ta liste d’utilisateurs depuis un CSV par ex.
if ADMIN:
    userscollection.delete_many({})  # vidage
    excel = csv.reader(open("usersM1_2025.csv"))  # list of authorized users
    for l in excel:
        ls = (l[0].split(';'))
        if userscollection.find_one({"name": ls[0]}) is None:
            userscollection.insert_one({"name": ls[0], "num": ls[1]})

# -----------------------------------------------------------------------------
# Vérification/Création de la collection "pools"
collname_pools = 'pools'
if collname_pools not in db.list_collection_names():
    print(f"Collection {collname_pools} inexistante ! On la crée par défaut.")
poolscollection = db[collname_pools]


# -----------------------------------------------------------------------------
# Collection "usage" pour stocker l’historique des occupations
collname_usage = 'usage'
if collname_usage not in db.list_collection_names():
    print(f"Collection {collname_usage} inexistante ! On la crée par défaut.")
usagecollection = db[collname_usage]

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Initialisation :  Flask service
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = 'BAD_SECRET_KEY'  # Pour la session

# MQTT config
app.config['MQTT_BROKER_URL'] = "test.mosquitto.org"
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_TLS_ENABLED'] = False

mqtt_client = Mqtt(app)
topicname = "uca/iot/piscine"

# ====================
#   CONFIG APSCHEDULER
# ====================
class Config:
    SCHEDULER_API_ENABLED = True

app.config.from_object(Config())
collname_telemetry = 'telemetry'
telemetry_collection = db[collname_telemetry]
scheduler = APScheduler()
scheduler.init_app(app)
def release_expired_pools():
    """
    Parcourir les piscines occupées et les locations "en cours".
    Si l'heure actuelle dépasse l'heure de fin prévue => on libère la piscine.
    """
    print("[Scheduler] Vérification des locations expirées...")
    now = datetime.now()

    # 1) Trouver toutes les locations dont end=None (ou un champ similaire)
    #    et qui ont un end_time < now
    ongoing_usages = usagecollection.find({"end": None})  # ex. "end" pas encore renseigné
    for usage in ongoing_usages:
        end_time = usage.get("end_time", None)  # on suppose qu'on a stocké "end_time"
        if end_time and end_time <= now:
            # => la location est expirée, on met à jour "end" pour dire que c'est terminé
            usage_id = usage["_id"]
            pool_id = usage["pool_id"]

            usagecollection.update_one(
                {"_id": usage_id},
                {
                    "$set": {
                        "end": end_time  # ou "end": now, selon ce que vous préférez
                    }
                }
            )
            # 2) Mettre à jour la piscine pour la libérer
            poolscollection.update_one(
                {"pool_id": pool_id},
                {
                    "$set": {
                        "occupied": False,
                        "start_occupied_time": None,
                        "occupied_time": 0,
                        "user_name": None
                    }
                }
            )
            ''' 
            # Eventuellement, publier un message MQTT (LED bleue ou éteinte, etc.)
            mqtt_client.publish(
                topicname,
                json.dumps({"info": {"ident": pool_id},
                            "status": {"led": "off", "occupied": False}})
            )'''

            print(f"[Scheduler] Libération auto: Piscine {pool_id} libérée.")

# On planifie la tâche toutes les minutes (configurable)
scheduler.add_job(
    id='release_expired_pools_job',
    func=release_expired_pools,
    trigger='interval',
    seconds=60
)

scheduler.start()
# Pour terminer proprement le scheduler à l'extinction de l'app
atexit.register(lambda: scheduler.shutdown())

# -----------------------------------------------------------------------------
@app.route('/')
def hello_world():
    # Page d’accueil minimale
    return render_template('index.html')  

# -----------------------------------------------------------------------------
def compute_rental_price(duration_minutes, hotspot, avg_temp, avg_light):
    """
    Exemple de fonction pour calculer le prix de location.
    On l'affiche aussi sur la page (voir template).

    Hypothèse de formule:
    --------------------------------------------
    prix = durée_heures * ( (10 + delta_hotspot)
            + (0.1 * avg_temp)
            + (0.05 * avg_light) )
    --------------------------------------------
    où delta_hotspot = 5 si hotspot=True sinon 0.
    """
    delta_hotspot = 5 if hotspot else 0
    duree_heures = duration_minutes / 60.0
    prix = duree_heures * ((10 + delta_hotspot) + 0.1 * avg_temp + 0.05 * avg_light)
    # Arrondissons éventuellement pour l'affichage
    return round(prix, 2)


@app.route("/open", methods=['GET', 'POST'])
def openthedoor():
    """
    Exemple d'accès:
      GET /open?idu=toto&idswp=P_123
    """
    if request.method == 'GET':
        # Récupération des paramètres
        idu = request.args.get('idu')  # nom d'utilisateur
        idswp = request.args.get('idswp')  # ID de la piscine

        session['idu'] = idu
        session['idswp'] = idswp
        print(f"[OPEN - GET] Reçu demande d'accès: user={idu}, pool={idswp}")

        # Vérifier si la piscine existe
        pool_doc = poolscollection.find_one({"pool_id": idswp})
        if not pool_doc:
            # Piscine inexistante
            return render_template("open.html",
                                   scenario="pool_not_found",
                                   idu=idu,
                                   idswp=idswp)

        # La piscine existe, on récupère ses données
        pool_available = (pool_doc.get("occupied", True) == False)
        pool_hotspot = pool_doc.get("hotspot", False)
        pool_owner = pool_doc.get("user_name", "Unknown")
        pool_occupied_time = pool_doc.get("occupied_time", 0)  # temps d'occupation (en minutes?)
        pool_start_occupied_time = pool_doc.get("start_occupied_time", None)  # date de début
        pool_average_temperature = pool_doc.get("average_temperature", 0)
        pool_average_light = pool_doc.get("average_light", 0)
        pool_min_temperature = pool_doc.get("min_temperature", 0)
        pool_max_temperature = pool_doc.get("max_temperature", 0)
        pool_min_light = pool_doc.get("min_light", 0)
        pool_max_light = pool_doc.get("max_light", 0)


        # Vérifier si l'utilisateur existe
        user_doc = userscollection.find_one({"name": idu})
        if not user_doc:
            # Utilisateur inconnu
            return render_template("open.html",
                                   scenario="user_not_found",
                                   idu=idu,
                                   idswp=idswp,
                                   pool_doc=pool_doc)

        # Cas où tout est correct : user existe et piscine existe
        # Vérifions la disponibilité
        if not pool_available:
            # Piscine déjà occupée => calculer le temps restant
            # On suppose que `pool_occupied_time` est le temps d'occupation prévu (en minutes)
            # et que `pool_start_occupied_time` est un datetime stocké dans MongoDB
            if pool_start_occupied_time is not None:
                # Calcul du temps écoulé
                start_time = pool_start_occupied_time
                now = datetime.now()
                elapsed = (now - start_time).total_seconds() / 60.0  # en minutes
                time_left = pool_occupied_time - elapsed
                if time_left < 0:
                    time_left = 0  # La piscine devrait être libérée,
                    # mais on reste cohérent avec l'existant
            else:
                time_left = pool_occupied_time  # On ne connaît pas le start -> on affiche le total ?

            # Afficher un message indiquant que la piscine est déjà prise
            # et un compte à rebours pour time_left (en minutes)
            return render_template("open.html",
                                   scenario="pool_busy",
                                   idu=idu,
                                   idswp=idswp,
                                   user_doc=user_doc,
                                   pool_doc=pool_doc,
                                   time_left=time_left)
        else:
            # Piscine libre
            # On affiche un formulaire pour saisir la durée d'occupation souhaitée
            # On n'occupe pas encore la piscine tant que l'utilisateur n'a pas validé
            return render_template("open.html",
                                   scenario="pool_free",
                                   idu=idu,
                                   idswp=idswp,
                                   user_doc=user_doc,
                                   pool_doc=pool_doc,
                                    pool_owner=pool_owner,
                                   hotspot=pool_hotspot,
                                   avg_temp=pool_average_temperature,
                                   avg_light=pool_average_light,
                                   min_temp=pool_min_temperature,
                                   max_temp=pool_max_temperature,
                                   min_light=pool_min_light,
                                   max_light=pool_max_light)

    else:
        # POST => traitement soit de la création d'utilisateur, soit de la location
        action = request.form.get('action')
        idu = request.form.get('idu')
        idswp = request.form.get('idswp')

        if action == "create_user":
            # Créer l'utilisateur dans la DB
            new_user = {
                "name": idu,
                "rentals": []  # pour tracer les locations
            }
            userscollection.insert_one(new_user)
            print(f"[OPEN - POST] Utilisateur {idu} créé en base.")

            # On peut ensuite rediriger (ou réafficher) la même page,
            # pour que l'utilisateur voie que maintenant il existe
            return redirect(url_for("openthedoor", idu=idu, idswp=idswp))

        elif action == "rent_pool":
            # L'utilisateur a rempli le formulaire pour occuper la piscine
            duration_str = request.form.get("duration")  # durée en minutes
            duration_minutes = int(duration_str) if duration_str else 0

            # Récupérer les infos du user et de la piscine pour calculer le prix
            user_doc = userscollection.find_one({"name": idu})
            pool_doc = poolscollection.find_one({"pool_id": idswp})
            if not user_doc or not pool_doc:
                # Normalement ça ne devrait pas arriver,
                # mais gérons la possibilité
                return render_template("open.html",
                                       scenario="error",
                                       message="Utilisateur ou piscine introuvable en base.")

            pool_hotspot = pool_doc.get("hotspot", False)
            pool_avg_temp = pool_doc.get("average_temperature", 0)
            pool_avg_light = pool_doc.get("average_light", 0)

            # Calcul du prix
            price = compute_rental_price(duration_minutes,
                                         pool_hotspot,
                                         pool_avg_temp,
                                         pool_avg_light)

            # Avant de "confirmer", on peut soit afficher le prix et redemander confirmation,
            # soit considérer qu'à ce stade l'utilisateur valide déjà.
            # Supposons qu'on valide directement.
            # => on met à jour la piscine en "occupied"
            # => on enregistre l'occupation dans usagecollection
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=duration_minutes)

            # On met à jour la piscine
            poolscollection.update_one(
                {"pool_id": idswp},
                {
                    "$set": {
                        "occupied": True,
                        "occupied_time": duration_minutes,
                        "start_occupied_time": start_time,
                    }
                }
            )

            # Insérer dans usagecollection
            usage_doc = {
                "user": idu,
                "pool_id": idswp,
                "start": start_time,
                "end": None,  # on complètera à la libération
                "end_time": end_time,
                "duration_minutes": duration_minutes,
                "price": price
            }
            usagecollection.insert_one(usage_doc)

            # Mettre à jour la doc user pour tracer la location
            # On ajoute un objet "rental" dans le champ "rentals"
            userscollection.update_one(
                {"name": idu},
                {
                    "$push": {
                        "rentals": {
                            "pool_id": idswp,
                            "start": start_time,
                            "duration_minutes": duration_minutes,
                            "price": price
                        }
                    }
                }
            )

            # Optionnel: Publier un message MQTT => LED verte, par exemple
           # mqtt_client.publish(
        #        topicname,
          #      json.dumps({"info": {"ident": idswp},
             #               "status": {"led": "green", "occupied": True}})
        #    )

            print(f"[OPEN - POST] Occupation enregistrée. Prix={price}.")

            # On affiche un template final avec le prix
            return render_template("open.html",
                                   scenario="rental_confirmed",
                                   idu=idu,
                                   idswp=idswp,
                                   duration_minutes=duration_minutes,
                                   price=price,
                                   # Pour éventuellement réafficher la formule
                                   formula="prix = durée_heures * ((10 + delta_hotspot) + 0.1*Temp + 0.05*Light)",
                                   user_doc=user_doc,
                                   pool_doc=pool_doc)

        else:
            # Action inconnue
            return render_template("open.html",
                                   scenario="error",
                                   message="Action de formulaire inconnue.")

# -----------------------------------------------------------------------------
@app.route("/users")
def lists_users():
    """
    Liste des utilisateurs déclarés
    Exemple : curl https://ton-appli.onrender.com/users
    """
    todos = userscollection.find()
    return jsonify([todo['name'] for todo in todos])

# -----------------------------------------------------------------------------
@app.route('/publish', methods=['POST'])
def publish_message():
    """
    mosquitto_sub -h test.mosquitto.org -t gillou
    mosquitto_pub -h test.mosquitto.org -t gillou -m tutu
    curl -X POST -H Content-Type:application/json -d "{\"topic\":\"gillou\",\"msg\":\"hello\"}"  https://waterbnbf.onrender.com/publish
    """
    content_type = request.headers.get('Content-Type')
    print("\n Content type = {}".format(content_type))
    request_data = request.get_json()
    print("\n topic = {}".format(request_data['topic']))

    publish_result = mqtt_client.publish(request_data['topic'], request_data['msg'])
    return jsonify({'code': publish_result[0]})

# -----------------------------------------------------------------------------
# Exemples d’agrégations pour renvoyer des stats
@app.route('/stats', methods=['GET'])
def get_stats():
    """
    Route qui renvoie quelques statistiques basées sur la collection usage.
    Ex : nombre d’occupations par piscine, temps moyen d’occupation, etc.
    """
    # Exemple simple : compter le nombre total d’occupations par piscine
    pipeline = [
        {"$group": {"_id": "$pool_id", "count": {"$sum": 1}}}
    ]
    results = list(usagecollection.aggregate(pipeline))
    
    # On peut aussi calculer la durée moyenne en s’appuyant sur (end - start)
    # si tu stockes la fin en datetime
    # pipeline2 = [
    #     {"$match": {"end": {"$ne": None}}},  # occupation terminée
    #     {"$project": {
    #         "pool_id": 1,
    #         "duration": {"$divide": [{"$subtract": ["$end", "$start"]}, 1000 * 60]}  # en minutes
    #     }},
    #     {"$group": {"_id": "$pool_id", "avgDurationMinutes": {"$avg": "$duration"}}}
    # ]
    # durations = list(usagecollection.aggregate(pipeline2))

    return jsonify({
        "occupations_count_by_pool": results,
        # "average_occupation_duration": durations
    })

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# MQTT callbacks
@mqtt_client.on_connect()
def handle_connect(client, userdata, flags, rc):
    if rc == 0:
        print('[MQTT] Connected successfully')
        mqtt_client.subscribe(topicname)
    else:
        print('[MQTT] Bad connection. Code:', rc)

@mqtt_client.on_message()
def handle_mqtt_message(client, userdata, msg):
    """
    Décode les messages MQTT venant des ESP32.
    """
    decoded_message = msg.payload.decode("utf-8")
    #print(decoded_message)
    try:
        dic = json.loads(decoded_message)
    except Exception as e:
        print(f"[MQTT] Erreur JSON: {e}")
        return

    pool_id = dic.get("info", {}).get("ident", "")
    status = dic.get("piscine", {})
    #occupied = False;#status.get("occupied", False)
    hotspot = dic.get("piscine", {}).get("hotspot", False)
    temperature = dic.get("status", {}).get("temperature", 0)
    light = dic.get("status", {}).get("light", 0)

    now = datetime.now()

    telemetry_doc = {
        "pool_id": pool_id,
        "timestamp": now,
        "temperature": temperature,
        "light": light,
        "hotspot": hotspot
    }
    telemetry_collection.insert_one(telemetry_doc)
    # Récupérer la piscine en base
    pool_doc = poolscollection.find_one({"pool_id": pool_id})
    if not pool_doc:
        print(f"[MQTT] Piscine {pool_id} inconnue dans la base.")
        poolscollection.insert_one({
            "pool_id": pool_id,
            "occupied": False,#occupied,
            "user_name": dic.get("info", {}).get("user", "Unknown"),
            "occupied_time": 0,
            "hotspot": hotspot,
            "start_occupied_time": None,
            "temperature_data": [temperature],
            "average_temperature": temperature,
            "min_temperature": temperature,
            "max_temperature": temperature,
            "light_data": [light],
            "average_light": light,
            "min_light": light,
            "max_light": light
        })
        print(f"[MQTT] Piscine {pool_id} ajoutée dans la base.")
        return
    else:
        #print(f"[MQTT] Piscine {pool_id} trouvée dans la base.")
        temperature_data = pool_doc.get("temperature_data", [])
        temperature_data.append(temperature)
        light_data = pool_doc.get("light_data", [])
        light_data.append(light)

        # Limiter la taille des données de température et luminosité (exemple : 100 dernières)
        if len(temperature_data) > 100:
            temperature_data.pop(0)
        if len(light_data) > 100:
            light_data.pop(0)

        # Recalculer les statistiques
        average_temperature = sum(temperature_data) / len(temperature_data)
        average_light = sum(light_data) / len(light_data)
        min_temperature = min(temperature_data)
        max_temperature = max(temperature_data)
        min_light = min(light_data)
        max_light = max(light_data)

        poolscollection.update_one(
            {"pool_id": pool_id},
            {
                "$set": {
                    "hotspot": hotspot,
                    "temperature_data": temperature_data,
                    "average_temperature": average_temperature,
                    "min_temperature": min_temperature,
                    "max_temperature": max_temperature,
                    "light_data": light_data,
                    "average_light": average_light,
                    "min_light": min_light,
                    "max_light": max_light
                }
            }
        )

    # Mettre à jour les informations si la piscine devient occupée
    ''' 
    if occupied and not pool_doc.get("occupied"):
        start_time = datetime.now()
        poolscollection.update_one(
            {"pool_id": pool_id},
            {
                "$set": {
                    "occupied": True,
                    "start_occupied_time": start_time
                }
            }
        )
        print(f"[MQTT] Piscine {pool_id} marquée comme occupée à {start_time}.")
    elif not occupied and pool_doc.get("occupied"):
        end_time = datetime.now()
        duration = (end_time - pool_doc.get("start_occupied_time")).total_seconds() if pool_doc.get(
            "start_occupied_time") else 0
        poolscollection.update_one(
            {"pool_id": pool_id},
            {
                "$set": {
                    "occupied": False,
                    "occupied_time": pool_doc.get("occupied_time", 0) + duration,
                    "start_occupied_time": None
                }
            }
        )
        print(f"[MQTT] Piscine {pool_id} marquée comme non occupée. Durée occupée ajoutée : {duration} secondes.")
'''
# %%%%%%%%%%%%%  main driver
if __name__ == '__main__':
    # Lancement du serveur Flask
    # run() method of Flask class runs the application
    # on the local development server.
    app.run(debug=False)  # host='127.0.0.1', port=5000)
