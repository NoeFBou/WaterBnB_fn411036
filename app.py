import json
import csv
import os
import datetime

from flask import request
from flask import jsonify
from flask import Flask
from flask import session
from flask import render_template

from flask_mqtt import Mqtt
from flask_pymongo import PyMongo
from pymongo import MongoClient
from pymongo.server_api import ServerApi

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
    excel = csv.reader(open("usersM1_2024.csv"))  # list of authorized users
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

# Exemple d’insertion si vide :
if ADMIN:
    poolscollection.delete_many({})
    # on insère quelques piscines fictives
    data_pools = [
        {"pool_id": "P_123", "occupied": False, "name": "Piscine 123"},
        {"pool_id": "P_456", "occupied": False, "name": "Piscine 456"}
    ]
    poolscollection.insert_many(data_pools)

# -----------------------------------------------------------------------------
# Collection "usage" pour stocker l’historique des occupations
collname_usage = 'usage'
if collname_usage not in db.list_collection_names():
    print(f"Collection {collname_usage} inexistante ! On la crée par défaut.")
usagecollection = db[collname_usage]

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Initialisation :  Flask service
app = Flask(__name__)
app.secret_key = 'BAD_SECRET_KEY'  # Pour la session

# MQTT config
app.config['MQTT_BROKER_URL'] = "test.mosquitto.org"
app.config['MQTT_BROKER_PORT'] = 1883
app.config['MQTT_TLS_ENABLED'] = False

mqtt_client = Mqtt(app)
topicname = "uca/iot/piscine"

# -----------------------------------------------------------------------------
@app.route('/')
def hello_world():
    # Page d’accueil minimale
    return render_template('index.html')  

# -----------------------------------------------------------------------------
@app.route("/open", methods=['GET'])
def openthedoor():
    """
    Exemple de requête :
    curl -X GET "https://ton-appli.onrender.com/open?idu=toto&idswp=P_123"
    """
    idu = request.args.get('idu')     # nom d'utilisateur
    idswp = request.args.get('idswp') # ID de la piscine
    
    session['idu'] = idu
    session['idswp'] = idswp
    print(f"\n[OPEN] Reçu une demande d'accès pour user={idu}, pool={idswp}")

    # Vérifier si l'utilisateur existe
    user_doc = userscollection.find_one({"name": idu})
    user_exists = (user_doc is not None)

    # Récupérer la piscine
    pool_doc = poolscollection.find_one({"pool_id": idswp})
    if not pool_doc:
        # Piscine non trouvée
        return jsonify({'idu': idu, 'idswp': idswp, "granted": "NO - pool unknown"}), 200
    
    # Vérifier disponibilité
    pool_available = (pool_doc.get("occupied", True) == False)

    if user_exists and pool_available:
        # Mettre à jour la piscine en base => occupée
        poolscollection.update_one(
            {"pool_id": idswp},
            {"$set": {"occupied": True}}
        )
        
        # Insérer un doc dans usage => début d’occupation
        start_time = datetime.datetime.now()
        usagecollection.insert_one({
            "user": idu,
            "pool_id": idswp,
            "start": start_time,
            "end": None  # on complètera à la libération
        })

        granted = "YES"
        # (Optionnel) Publier un message MQTT => LED verte
        # On peut coder la couleur dans le champ 'msg'
        publish_result = mqtt_client.publish(
            topicname,
            json.dumps({"info": {"ident": idswp},
                        "status": {"led": "green", "occupied": True}})
        )
        
    elif user_exists and not pool_available:
        granted = "NO - already occupied"
        # (Optionnel) LED jaune
        mqtt_client.publish(
            topicname,
            json.dumps({"info": {"ident": idswp},
                        "status": {"led": "yellow", "occupied": True}})
        )
    else:
        granted = "NO - user unknown"
        # (Optionnel) LED rouge
        mqtt_client.publish(
            topicname,
            json.dumps({"info": {"ident": idswp},
                        "status": {"led": "red", "occupied": False}})
        )

    return jsonify({'idu': idu, 'idswp': idswp, "granted": granted}), 200

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
    Permet de publier un message MQTT depuis une requête HTTP POST
    Exemple :
    curl -X POST -H Content-Type:application/json \
         -d "{\"topic\":\"gillou\",\"msg\":\"hello\"}"  https://ton-appli.onrender.com/publish
    """
    content_type = request.headers.get('Content-Type')
    request_data = request.get_json()
    
    topic = request_data.get('topic')
    msg = request_data.get('msg', '')
    
    publish_result = mqtt_client.publish(topic, msg)
    return jsonify({'code': publish_result[0]}), 200

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
    Exemple de payload attendu :
    {
      "info": {"ident":"P_123"},
      "status": {"occupied": false}
    }
    Quand occupied=False => on considère la piscine libérée => on termine l’occupation en base
    Quand occupied=True  => on considère la piscine occupée => on ouvre (si ce n’est pas déjà fait)
    """
    decoded_message = msg.payload.decode("utf-8")
    try:
        dic = json.loads(decoded_message)
    except Exception as e:
        print(f"[MQTT] Erreur JSON: {e}")
        return
    
    pool_id = dic.get("info", {}).get("ident", "")
    status = dic.get("status", {})
    occupied = status.get("occupied", False)

    # Récupérer la piscine en base
    pool_doc = poolscollection.find_one({"pool_id": pool_id})
    if not pool_doc:
        print(f"[MQTT] Piscine {pool_id} inconnue dans la base.")
        return
    
    if occupied:
        # La piscine devient occupée => on peut, si besoin, faire un insert usage
        # Sauf si c’est déjà occupé
        if not pool_doc.get("occupied", False):
            poolscollection.update_one({"pool_id": pool_id}, {"$set": {"occupied": True}})
            usagecollection.insert_one({
                "user": "Inconnu_MQTT",  # si tu ne sais pas encore qui
                "pool_id": pool_id,
                "start": datetime.datetime.now(),
                "end": None
            })
    else:
        # La piscine redevient libre => on met fin à l’occupation la plus récente
        poolscollection.update_one({"pool_id": pool_id}, {"$set": {"occupied": False}})
        
        # Retrouver le doc usage sans 'end' pour cette piscine
        last_usage = usagecollection.find_one(
            {"pool_id": pool_id, "end": None},
            sort=[("start", -1)]
        )
        if last_usage:
            usage_id = last_usage["_id"]
            usagecollection.update_one(
                {"_id": usage_id},
                {"$set": {"end": datetime.datetime.now()}}
            )
    
    print(f"[MQTT] Mise à jour de la piscine {pool_id} => occupied={occupied}")

# %%%%%%%%%%%%%  main driver
if __name__ == '__main__':
    # Lancement du serveur Flask
    # run() method of Flask class runs the application
    # on the local development server.
    app.run(debug=False)  # host='127.0.0.1', port=5000)
