import json
import csv

from flask import request
from flask import jsonify
from flask import Flask
from flask import session
from flask import render_template

from flask_mqtt import Mqtt
from flask_pymongo import PyMongo
from pymongo import MongoClient

ADMIN = True  # Faut être ADMIN/mongo pour écrire dans la base
uri = "mongodb+srv://noe:Lgngh4i4r6cluHHp@waterbnb.ti26c.mongodb.net/?retryWrites=true&w=majority&appName=WaterBnB"
# Create a new client and connect to the server
client = MongoClient(uri, server_api=ServerApi('1'))
# -----------------------------------------------------------------------------
# Looking for "WaterBnB" database in the cluster
dbname = 'WaterBnB'
dbnames = client.list_database_names()
if dbname in dbnames:
    print(f"{dbname} is there!")
else:
    print("YOU HAVE to CREATE the db !\n")

db = client.WaterBnB

# -----------------------------------------------------------------------------
# Looking for "users" collection in the WaterBnB database
collname = 'users'
collnames = db.list_collection_names()
if collname in collnames:
    print(f"{collname} is there!")
else:
    print(f"YOU HAVE to CREATE the {collname} collection !\n")

userscollection = db.users

# -----------------------------------------------------------------------------
# import authorized users .. if not already in ?
if ADMIN:
    userscollection.delete_many({})  # empty collection
    excel = csv.reader(open("usersM1_2024.csv"))  # list of authorized users
    for l in excel:  # import in mongodb
        ls = (l[0].split(';'))
        # print(ls)
        if userscollection.find_one({"name": ls[0]}) == None:
            userscollection.insert_one({"name": ls[0], "num": ls[1]})

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Initialisation :  Flask service
app = Flask(__name__)

# Notion de session ! .. to share between routes !
# https://flask-session.readthedocs.io/en/latest/quickstart.html
# https://testdriven.io/blog/flask-sessions/
# https://www.fullstackpython.com/flask-globals-session-examples.html
# https://stackoverflow.com/questions/49664010/using-variables-across-flask-routes
app.secret_key = 'BAD_SECRET_KEY'

# Global variable to store pool statuses
pool_status = {}  # Dictionary to store the status of pools

# -----------------------------------------------------------------------------
@app.route('/')
def hello_world():
    return render_template('index.html')  # 'Hello, World!'

# Test with =>  curl https://waterbnbf.onrender.com/

# -----------------------------------------------------------------------------

# https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/X-Forwarded-For
# If a request goes through multiple proxies, the IP addresses of each successive proxy is listed.
# voir aussi le parsing !

@app.route("/open", methods=['GET', 'POST'])
# @app.route('/open') # ou en GET seulement
def openthedoor():
    idu = request.args.get('idu')  # idu : clientid of the service
    idswp = request.args.get('idswp')  # idswp : id of the swimming pool
    session['idu'] = idu
    session['idswp'] = idswp
    print("\n Peer = {}".format(idu))

    # ip addresses of the machine asking for opening
    ip_addr = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)

    # Check if user is in the users collection
    if userscollection.find_one({"name": idu}) != None:
        user_exists = True
    else:
        user_exists = False

    # Check if pool exists and is not already occupied
    # Check if idswp is in pool_status
    pool_info = pool_status.get(idswp, None)
    if pool_info is not None:
        if not pool_info.get("occupied", True):  # if not occupied
            pool_available = True
        else:
            pool_available = False
    else:
        # Pool info not available
        pool_available = False

    if user_exists and pool_available:
        granted = "YES"
    else:
        granted = "NO"

    return jsonify({'idu': session['idu'], 'idswp': session['idswp'], "granted": granted}), 200

# Test with => curl -X GET https://waterbnbf.onrender.com/open?idu=toto&idswp=P_123456

@app.route("/users")
def lists_users():  # Liste des utilisateurs déclarés
    """
    curl https://waterbnbf.onrender.com/users
    """
    todos = userscollection.find()
    return jsonify([todo['name'] for todo in todos])

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

# %%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
# Initialisation MQTT
app.config['MQTT_BROKER_URL'] = "test.mosquitto.org"
app.config['MQTT_BROKER_PORT'] = 1883
# app.config['MQTT_USERNAME'] = ''  # Set this item when you need to verify username and password
# app.config['MQTT_PASSWORD'] = ''  # Set this item when you need to verify username and password
# app.config['MQTT_KEEPALIVE'] = 5  # Set KeepAlive time in seconds
app.config['MQTT_TLS_ENABLED'] = False  # If your broker supports TLS, set it True

topicname = "uca/iot/piscine"
mqtt_client = Mqtt(app)

@mqtt_client.on_connect()
def handle_connect(client, userdata, flags, rc):
    if rc == 0:
        print('Connected successfully')
        mqtt_client.subscribe(topicname)  # subscribe topic
    else:
        print('Bad connection. Code:', rc)

@mqtt_client.on_message()
def handle_mqtt_message(client, userdata, msg):
    global pool_status
    if (msg.topic == topicname):
        decoded_message = str(msg.payload.decode("utf-8"))
        dic = json.loads(decoded_message)  # from string to dict
        print("\n Dictionnary received = {}".format(dic))

        # Extract pool identifier and status
        pool_id = dic["info"]["ident"]  # The pool identifier
        # For status, let's suppose there is a field 'occupied' in dic['status']
        occupied = dic["status"].get("occupied", False)  # default to False if not present

        # Update pool status
        pool_status[pool_id] = {
            "occupied": occupied,
            # You can store other status info if needed
        }

# %%%%%%%%%%%%%  main driver function
if __name__ == '__main__':

    # run() method of Flask class runs the application
    # on the local development server.
    app.run(debug=False)  # host='127.0.0.1', port=5000)
