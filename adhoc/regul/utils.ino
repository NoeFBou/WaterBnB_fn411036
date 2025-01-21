/* 
 * Fichier : utils.ino
 * Auteur : Noé Florence 
 * Dascription : fonctions utilitaires pour les autres fichiers
 */

 
#include "config.h"
#include "jsondata.h"

#define EARTH_RADIUS_KM 6371.0

float deg2rad(float deg) {
  return deg * (M_PI / 180);
}

float calculateDistance(float lat1, float lon1, float lat2, float lon2) {
  // Haversine formula
  float dLat = deg2rad(lat2 - lat1);
  float dLon = deg2rad(lon2 - lon1);

  float a = sin(dLat/2) * sin(dLat/2) +cos(deg2rad(lat1)) * cos(deg2rad(lat2)) * sin(dLon/2) * sin(dLon/2);

  float c = 2 * atan2(sqrt(a), sqrt(1 - a));

  float distance = EARTH_RADIUS_KM * c;
  return distance;
}

// Fonction pour afficher les valeurs actuelles sous forme JSON
void printValue() {
  String jsonOutput = convertToJson();
  Serial.println(jsonOutput);
}

// Fonction pour initialiser les données JSON par défaut
void initJson(){
  // Initialisation des variables
  
  jsonData.luminosity = 0;
  jsonData.temperature = 0.00;
  jsonData.coolerState = false;
  jsonData.heaterState = false;
  jsonData.regulationState = true;
  jsonData.fireDetected = false;
  jsonData.fanSpeed = 0;

  
  jsonData.identification = IDENTIFICATION;
  jsonData.loc = LOCATION;
  jsonData.user = USER;

  jsonData.WiFiSSID = "";
  jsonData.MAC = "";
  jsonData.IP = "";
  jsonData.target_ip = -1;
  jsonData.target_port = -1;
  jsonData.target_sp = -1;
  
}

// Fonction pour convertir les données en format JSON
String convertToJson() {
  StaticJsonDocument<512> doc;

  // Ajout des données de statut
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
  doc["net"]["uptime"] = jsonData.currentTime;

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
  String output;
  serializeJson(doc, output); // Sérialisation du document JSON

  return output;
}

// Fonctions d'aide pour la validation des types

//fonction pour verifier si un integer est valide
bool isValidInteger(const String& str) {
  if (str.length() == 0) return false;
  char* endptr = nullptr;
  long val = strtol(str.c_str(), &endptr, 10);
  return (*endptr == '\0');
}

//fonction pour verifier si un float est valide
bool isValidFloat(const String& str) {
  if (str.length() == 0) return false;
  char* endptr = nullptr;
  strtof(str.c_str(), &endptr);
  return (*endptr == '\0');
}

//fonction pour verifier si un boolean est valide
bool parseBool(const String& str, bool& result) {
  String s = str;
  s.toLowerCase();
  if (s == "on" || s == "true" || s == "1") {
    result = true;
    return true;
  } else if (s == "off" || s == "false" || s == "0") {
    result = false;
    return true;
  }
  return false;
}
