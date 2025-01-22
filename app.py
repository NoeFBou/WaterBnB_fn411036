import json
import csv
import os
import atexit
import datetime
from datetime import datetime, timedelta
from flask import request, redirect, url_for, jsonify, Flask, session, render_template
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
topicname = "uca/iot/piscine" # Topic MQTT pour les messages des ESP32


# ====================
#   CONFIG APSCHEDULER
# ====================
class Config:
    SCHEDULER_API_ENABLED = True


app.config.from_object(Config())
collname_telemetry = 'telemetry' # Collection pour les données des ESP32
telemetry_collection = db[collname_telemetry]
scheduler = APScheduler() # Initialisation de l'instance APScheduler pour le scheduler Flask
scheduler.init_app(app)

# -----------------------------------------------------------------------------
# Fonctions pour le scheduler APScheduler (libération des piscines)
# -----------------------------------------------------------------------------
def release_expired_pools():
    """
    Parcourir les piscines occupées et les locations "en cours".
    Si l'heure actuelle dépasse l'heure de fin prévue => on libère la piscine.
    """
    print("[Scheduler] Vérification des locations expirées...")
    now = datetime.now()
    ongoing_usages = usagecollection.find({"end": None})  # ex. "end" pas encore renseigné

    for usage in ongoing_usages:
        end_time = usage.get("end_time", None)
        if end_time and end_time <= now:
            # => la location est expirée, on met à jour "end" pour dire que c'est terminé
            usage_id = usage["_id"]
            pool_id = usage["pool_id"]

            usagecollection.update_one(
                {"_id": usage_id},
                {
                    "$set": {
                        "end": end_time
                    }
                }
            )
            set_pool_occupied(pool_id, False)  # on appelle la fonction ci-dessous

            print(f"[Scheduler] Libération auto: Piscine {pool_id} libérée.")

# Lancer le scheduler
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
# Fonctions utilitaires pour gérer l'occupation des piscines
# -----------------------------------------------------------------------------
def set_pool_occupied(pool_id, occupied, start_time=None, duration_minutes=0):
    """
    Met à jour le champ 'occupied' d'une piscine et publie un message MQTT
    sur un topic distinct si le statut change.
    - pool_id : identifiant de la piscine
    - occupied : booléen
    - start_time : datetime
    - duration_minutes : int (pour la durée d'occupation prévue)
    """
    pool_doc = poolscollection.find_one({"pool_id": pool_id})
    if not pool_doc:
        print(f"[set_pool_occupied] Piscine {pool_id} introuvable.")
        return

    # On regarde l'état actuel
    current_occupied = pool_doc.get("occupied", False)

    # Si l'état ne change pas, on ne publie pas
    if current_occupied == occupied:
        print(f"[set_pool_occupied] Piscine {pool_id} déjà dans l'état {occupied}. Pas de pub MQTT.")
        return

    # Sinon on met à jour l'état en base
    update_fields = {"occupied": occupied}
    if occupied:
        # Occupée => on stocke start_occupied_time + durée
        update_fields["start_occupied_time"] = start_time
        update_fields["occupied_time"] = duration_minutes
    else:
        # Libérée => on réinitialise
        update_fields["start_occupied_time"] = None
        update_fields["occupied_time"] = 0

    poolscollection.update_one(
        {"pool_id": pool_id},
        {"$set": update_fields}
    )

    # Publication MQTT sur un topic spécifique
    topic_state = f"uca/iot/piscine/{pool_id}/state"
    message = {
        "pool_id": pool_id,
        "occupied": occupied,
        "timestamp": datetime.now().isoformat()
    }
    mqtt_client.publish(topic_state, json.dumps(message))
    print(f"[MQTT] Publié sur {topic_state} => {message}")


# -----------------------------------------------------------------------------
@app.route('/')
def hello_world():
    return render_template("open.html",
                           scenario="error",
                           message="Unknown form action.")


# -----------------------------------------------------------------------------
# Fonction pour calculer le prix de location
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
    return round(prix, 2)


# -----------------------------------------------------------------------------
# Route principale
# -----------------------------------------------------------------------------
@app.route("/open", methods=['GET', 'POST'])
def openthedoor():
    """
    Exemple d'accès:
      GET /open?idswp=P_22106244&idu=florence
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

        # Récupérer les infos de la piscine
        pool_available = (pool_doc.get("occupied", True) == False)
        pool_hotspot = pool_doc.get("hotspot", False)
        pool_owner = pool_doc.get("user_name", "Unknown")
        pool_occupied_time = pool_doc.get("occupied_time", 0)
        pool_start_occupied_time = pool_doc.get("start_occupied_time", None)
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
        # Vérifier si la piscine est occupée
        if not pool_available:
            # Piscine déjà occupée => calculer le temps restant
            if pool_start_occupied_time is not None:
                start_time = pool_start_occupied_time
                now = datetime.now()
                elapsed = (now - start_time).total_seconds() / 60.0
                time_left = pool_occupied_time - elapsed
                if time_left < 0:
                    time_left = 0
            else:
                time_left = pool_occupied_time
            topic_state = f"uca/iot/piscine/{idswp}/state"
            message_busy = {
                "pool_id": idswp,
                "occupied": True,
                "timestamp": datetime.now().isoformat(),
                "info": f"L'utilisateur {idu} a tenté d'accéder à une piscine déjà occupée."
            }
            mqtt_client.publish(topic_state, json.dumps(message_busy))
            print(f"[MQTT] Piscine occupée: Message publié sur {topic_state} => {message_busy}")

            return render_template("open.html",
                                   scenario="pool_busy",
                                   idu=idu,
                                   idswp=idswp,
                                   user_doc=user_doc,
                                   pool_doc=pool_doc,
                                   time_left=time_left)
        else:
            # Piscine libre => Formulaire pour saisir la durée
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
                "rentals": []
            }
            userscollection.insert_one(new_user)
            print(f"[OPEN - POST] Utilisateur {idu} créé en base.")
            return redirect(url_for("openthedoor", idu=idu, idswp=idswp))

        # Location d'une piscine
        elif action == "rent_pool":
            duration_str = request.form.get("duration")
            duration_minutes = int(duration_str) if duration_str else 0

            user_doc = userscollection.find_one({"name": idu})
            pool_doc = poolscollection.find_one({"pool_id": idswp})
            if not user_doc or not pool_doc:
                return render_template("open.html",
                                       scenario="error",
                                       message="Pool not found in database.")

            pool_hotspot = pool_doc.get("hotspot", False)
            pool_avg_temp = pool_doc.get("average_temperature", 0)
            pool_avg_light = pool_doc.get("average_light", 0)
            price = compute_rental_price(duration_minutes,
                                         pool_hotspot,
                                         pool_avg_temp,
                                         pool_avg_light)

            # Validation => on met à jour la piscine en "occupied"
            start_time = datetime.now()
            end_time = start_time + timedelta(minutes=duration_minutes)

            # On utilise la fonction set_pool_occupied
            set_pool_occupied(idswp, True, start_time=start_time, duration_minutes=duration_minutes)

            # Insérer dans usagecollection
            usage_doc = {
                "user": idu,
                "pool_id": idswp,
                "start": start_time,
                "end": None,
                "end_time": end_time,
                "duration_minutes": duration_minutes,
                "price": price
            }
            usagecollection.insert_one(usage_doc)

            # Mettre à jour le doc user pour tracer la location
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

            print(f"[OPEN - POST] Occupation enregistrée. Prix={price}.")

            # Retourner la page de confirmation
            return render_template("open.html",
                                   scenario="rental_confirmed",
                                   idu=idu,
                                   idswp=idswp,
                                   duration_minutes=duration_minutes,
                                   price=price,
                                   formula="price = durée_heures * ((10+delta_hotspot) + 0.1*Temp + 0.05*Light)",
                                   user_doc=user_doc,
                                   pool_doc=pool_doc)
        # Action inconnue
        else:
            return render_template("open.html",
                                   scenario="error",
                                   message="Unknown form action.")


# -----------------------------------------------------------------------------
@app.route("/users")
def lists_users():
    """
    Liste des utilisateurs déclarés
    """
    todos = userscollection.find()
    return jsonify([todo['name'] for todo in todos])


# -----------------------------------------------------------------------------
@app.route('/publish', methods=['POST'])
def publish_message():
    """
    Publication manuelle sur un topic
    """
    request_data = request.get_json()
    topic = request_data['topic']
    msg = request_data['msg']
    publish_result = mqtt_client.publish(topic, msg)
    return jsonify({'code': publish_result[0]})


# -----------------------------------------------------------------------------
@app.route('/stats', methods=['GET'])
def get_stats():
    """
    Route qui renvoie quelques stats basées sur la collection usage.
    """
    pipeline = [
        {"$group": {"_id": "$pool_id", "count": {"$sum": 1}}}
    ]
    results = list(usagecollection.aggregate(pipeline))

    return jsonify({
        "occupations_count_by_pool": results
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

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# MQTT callbacks
@mqtt_client.on_message()
def handle_mqtt_message(client, userdata, msg):
    """
    Décode les messages MQTT venant des ESP32.
    """
    decoded_message = msg.payload.decode("utf-8")
    try:
        dic = json.loads(decoded_message)
    except Exception as e:
        print(f"[MQTT] Erreur JSON: {e}")
        return
    print(f"[MQTT] Message reçu: {dic}")

    pool_id = dic.get("info", {}).get("ident", "")
    temperature = dic.get("status", {}).get("temperature", 0)
    light = dic.get("status", {}).get("light", 0)
    hotspot = dic.get("piscine", {}).get("hotspot", False)

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
        print(f"[MQTT] Piscine {pool_id} inconnue dans la base. On l'ajoute.")
        poolscollection.insert_one({
            "pool_id": pool_id,
            "occupied": False,
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
        return
    else:
        # On met à jour les listes temp/luminosité + stats
        temperature_data = pool_doc.get("temperature_data", [])
        light_data = pool_doc.get("light_data", [])
        temperature_data.append(temperature)
        light_data.append(light)

        if len(temperature_data) > 100:
            temperature_data.pop(0)
        if len(light_data) > 100:
            light_data.pop(0)

        avg_temp = sum(temperature_data) / len(temperature_data)
        avg_light = sum(light_data) / len(light_data)

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
                    "average_temperature": avg_temp,
                    "min_temperature": min_temperature,
                    "max_temperature": max_temperature,
                    "light_data": light_data,
                    "average_light": avg_light,
                    "min_light": min_light,
                    "max_light": max_light
                }
            }
        )


# %%%%%%%%%%%%%  main driver
if __name__ == '__main__':
    # Lancement du serveur Flask
    app.run(debug=False)
