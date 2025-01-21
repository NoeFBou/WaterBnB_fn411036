/* 
 * Fichier : regul.ino
 * Auteur : Noé Florence 
*/


// Inclusion des fichiers d'en-tête nécessaires
#include "config.h"
#include "jsondata.h"
#include "sensors.h"
#include "utils.h"
#include <ArduinoOTA.h>
#include <WiFi.h>
#include "ESPAsyncWebServer.h"
#include "wifi_utils.h"
#include "OneWire.h"
#include "DallasTemperature.h"
#include "SPIFFS.h"
#include "routes.h"
#include "mqtt_utils.h"
#include <vector>

// Configuration du capteur de température OneWire
OneWire oneWire(HEATSENSORPIN);
DallasTemperature tempSensor(&oneWire);

// Configuration du ruban LED NeoPixel
Adafruit_NeoPixel stripLed(NUMLEDS, PINSTRIP, NEO_GRB + NEO_KHZ800);

// Variables globales pour le timing et les seuils
unsigned long loop_period = 10000;
float tempSeuil = 2.0;
unsigned long interval = 0;
unsigned long previousMillis = 0;

// Création du serveur web asynchrone sur le port 80
AsyncWebServer server(80);

// Instance pour les données JSON partagées
JsonData jsonData;

String esppluschaud="";


//temp
bool hotspot = false;
bool occupied = false;
//const char* mqtt_server = "192.168.177.37";//
const char* mqtt_server ="test.mosquitto.org";
const char* mqtt_topic = "uca/iot/piscine";
String deviceId;

struct DeviceData {
  String id;
  float temperature;
  float latitude;
  float longitude;
  unsigned long lastUpdateTime;
};

std::vector<DeviceData> devicesData;

WiFiClient espClient; 
PubSubClient mqttclient(espClient);

/* Function Prototypes */
void publishData();
void mqtt_callback(char* topic, byte* payload, unsigned int length);
void updateHotspotStatus();



void setup() {
  USE_SERIAL.begin(9600); // Initialisation de la communication série
  while (!USE_SERIAL);

  initSensor(); // Initialisation des capteurs (fonction dans sensor)
  initJson(); // Initialisation des données JSON (fonction dans utils)

  wifi_connect_multi(jsonData.identification); // Connexion WiFi avec multi-SSID              
  
  // Vérification de l'état de la connexion WiFi
  if (WiFi.status() == WL_CONNECTED){
    USE_SERIAL.print("\nWiFi connected : yes ! \n"); 
    wifi_printstatus(0);  //fpnction dans wifi_utils
  } 
  else {
    USE_SERIAL.print("\nWiFi connected : no ! \n"); 
    //  ESP.restart();
  }

  // Initialisation du système de fichiers SPIFFS
  SPIFFS.begin(true);

  // Configuration des routes HTTP du serveur web
  setup_http_routes(&server); //fc dans routes
  
  // Démarrage du serveur web
  server.begin();
  

  //temp
  deviceId = WiFi.macAddress();

  // Set up MQTT client
  mqttclient.setServer(mqtt_server, 1883);
  mqttclient.setCallback(mqtt_callback);
  mqttclient.setBufferSize(2048);
  jsonData.hotspot=true;
  
}

void loop() {
  mqtt_reconnect(mqttclient); //temp

  jsonData.currentTime=millis(); // Mise à jour du temps actuel
  readSensors(); // Lecture des capteurs
  
  if (jsonData.regulationState){
    updateState(); // Mise à jour de l'état en fonction des mesures si la regulation est active (fonction dans sensors)
  }
  controlActuators(); // Contrôle des actionneurs (chauffage, climatisation, etc.) (fonction dans sensors)

  //printValue(); pour debug

  // Envoi des données périodique si les paramètres de cible sont définis
  if (jsonData.target_ip != "" && jsonData.target_port != -1 && jsonData.target_sp > 0){
    sendPostRequest(); //fonction pour envoyer les données périodiques au dashboard (fonction dans wifi_utils)
  }

  //temp
  publishData();

  mqttclient.loop();
  handleLedColor();

  
  delay(loop_period); // Attente avant la prochaine boucle
}

void publishData() {
  // Create JSON document
  
  StaticJsonDocument<2048> doc;
  doc["status"]["temperature"] = jsonData.temperature;
  doc["status"]["light"] = jsonData.luminosity;
  doc["status"]["regul"] = jsonData.regulationState ? "RUNNING" : "HALT";
  doc["status"]["fire"] = jsonData.fireDetected;
  doc["status"]["heat"] = jsonData.heaterState ? "ON" : "OFF";
  doc["status"]["cold"] = jsonData.coolerState ? "ON" : "OFF";
  doc["status"]["fanspeed"] = jsonData.fanSpeed;

  // Ajout des informations de localisation
  doc["location"]["room"] = jsonData.room;
  doc["location"]["gps"]["lat"] = jsonData.latitude;
  doc["location"]["gps"]["lon"] = jsonData.longitude;
  doc["location"]["address"] = jsonData.address;

  // Ajout des seuils de régulation
  doc["regul"]["lt"] = jsonData.lowThreshold;
  doc["regul"]["ht"] = jsonData.highThreshold;
  
  // Ajout des informations d'identification
  doc["info"]["ident"] = jsonData.identification;
  doc["info"]["user"] = jsonData.user;
  doc["info"]["loc"] = jsonData.loc;
  doc["net"]["uptime"] = String(jsonData.currentTime);

  // Ajout des informations réseau
  doc["net"]["ssid"] = jsonData.WiFiSSID;
  doc["net"]["mac"] = jsonData.MAC;
  doc["net"]["ip"] = jsonData.IP;
  
  // Ajout des informations pour les rapports
  doc["reporthost"]["target_ip"] = jsonData.target_ip;
  doc["reporthost"]["target_port"] = jsonData.target_port;
  doc["reporthost"]["sp"] = jsonData.target_sp;

  doc["piscine"]["hotspot"] = jsonData.hotspot;
  doc["piscine"]["occuped"] = jsonData.occupied;

  // Serialize JSON to string
  char payload[2048];
  serializeJson(doc, payload);
/*
  String payload = convertToJson();
  // Publish payload
  int payloadsize = payload.length()+1;
  char payloadChar[payloadsize];
  payload.toCharArray(payloadChar, payloadsize);*/
  //Serial.println(payloadChar);

  mqttclient.publish(mqtt_topic, payload);
}

void mqtt_callback(char* topic, byte* payload, unsigned int length) {
  // Handle incoming messages
  // Parse JSON and update devices data
  StaticJsonDocument<512> doc;
  DeserializationError error = deserializeJson(doc, payload, length);

  if (error) {
    Serial.print("deserializeJson() failed: ");
    Serial.println(error.c_str());
    return;
  }

  String topicStr = String(topic);
  String expectedTopic = "uca/iot/piscine/" + jsonData.identification + "/state";

  if (topicStr == expectedTopic) {
    bool isOccupied = doc["occupied"] | false;
    String infoMsg = doc["info"] | "";

    jsonData.occupied = isOccupied;

    if (infoMsg.indexOf("a tenté") >= 0) {
      redUntilTime = millis() + 30000UL;
      Serial.println("[MQTT] Tentative d'accès alors que la piscine est occupée => LED Rouge 30s");
    }
    
    handleLedColor();
  }
  
  else {
    String id = doc["info"]["ident"].as<String>();
  
    // Ignore our own messages
    if (id == jsonData.identification) {
      return;
    }
    DeviceData device;
    device.id = id;
    float tempe = doc["status"]["temperature"].as<float>();
    float lat = doc["location"]["gps"]["lat"].as<float>();
    float lon = doc["location"]["gps"]["lon"].as<float>();
    device.lastUpdateTime = millis();
    float distance = calculateDistance(jsonData.latitude, jsonData.longitude, lat, lon);
  
    if (distance <= 10.0){
      if( tempe >= jsonData.temperature) {
        jsonData.hotspot=false;
      }
      else{
        jsonData.hotspot=true;
      }
    }
  }
}
