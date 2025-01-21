/* 
 * Fichier : routes.ino
 * Auteur : Noé Florence 
 * Description : Configuration des routes HTTP pour le serveur web asynchrone
 */


#include "ESPAsyncWebServer.h"
#include "routes.h"
#include "SPIFFS.h"
#include "jsondata.h"

/*===================================================*/
// Fonction de traitement pour les placeholders dans les pages HTML
String processor(const String& var){
  if (var == "TEMPERATURE") {
    return String(jsonData.temperature).c_str();
  } else if (var == "LIGHT") {
    return String(jsonData.luminosity).c_str();
  } else if (var == "WHERE") {
    return String(jsonData.address).c_str();
  } else if (var == "SSID") {
    return String(jsonData.WiFiSSID).c_str();
  } else if (var == "MAC") {
    return String(jsonData.MAC).c_str();
  } else if (var == "IP") {
    return String(jsonData.IP).c_str();
  } else if (var == "COOLER") {
    return String(jsonData.coolerState).c_str();
  } else if (var == "HEATER") {
    return String(jsonData.heaterState).c_str();
  } else if (var == "LT") {
    return String(jsonData.lowThreshold).c_str();
  } else if (var == "HT") {
    return String(jsonData.highThreshold).c_str();
  } else if (var == "UPTIME") {
    return String(jsonData.currentTime).c_str();
  } else if (var == "IDENTIFICATIONNAME") {
    return String(jsonData.identification).c_str();
  } else if (var == "USERNAME") {
    return String(jsonData.user).c_str();
  } else if (var == "ROOM") {
    return String(jsonData.room).c_str();
  } else if (var == "LOCATION") {
    return String(jsonData.address).c_str();
  } else if (var == "REGULATION") {
    return (jsonData.regulationState) ? "active" : "desactive";
  } else if (var == "Fire") {
    return (jsonData.fireDetected) ? "Detected" : "not Detected";
  } else if (var == "FAN") {
    return String(jsonData.fanSpeed).c_str();
  } else if (var == "PRT_IP") {
    return String(jsonData.target_ip).c_str();
  } else if (var == "PRT_PORT") {
    return String(jsonData.target_port).c_str();
  } else if (var == "PRT_T") {
    return String(jsonData.target_sp).c_str();
  } else {
    return String();
  }
}

/*===================================================*/
// Configuration des routes HTTP du serveur web
void setup_http_routes(AsyncWebServer* server) {
  /* 
   * Configuration du serveur web asynchrone et des routes HTTP 
   */

  // Route pour la page d'accueil
  server->on("/", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/index.html", String(), false, processor); 
  });

  // Route pour la page index.html
  server->on("/index.html", HTTP_GET, [](AsyncWebServerRequest *request) {
    request->send(SPIFFS, "/index.html", String(), false, processor); 
  });

  // Routes pour les fichiers statiques (CSS, JS, images)
  //separer de l index pour pas appliquer processor sur les fichiers js, css
  server->serveStatic("/css", SPIFFS, "/css");
  server->serveStatic("/js", SPIFFS, "/js");
  server->serveStatic("/assets", SPIFFS, "/assets");

  // Route pour obtenir les valeurs des capteurs en JSON
  server->on("/value", HTTP_GET, [](AsyncWebServerRequest *request) {
    String params = "";
    for (int i = 0; i < request->args(); i++) {
      if (i > 0) params += "&";
      params += request->argName(i);
    }

    if (params == "") {
      request->send(404, "application/json", "{\"error\":\"Aucun paramètre spécifié\"}");
    } else {
      String response = getStatusJson(params);
      request->send(200, "application/json", response);
    }
  });

  // Route pour modifier la configuration via des paramètres
  server->on("/set", HTTP_GET, [](AsyncWebServerRequest *request) {
    String resultJson = "{";
    bool paramFound = false;
    
    for (int i = 0; i < request->args(); i++) {
      String param = request->argName(i);
      String value = request->arg(i);
      String result = setConfiguration(param, value);

      if (result != "404") {
        if (paramFound) resultJson += ", ";
        resultJson += "\"" + param + "\":\"" + result + "\"";
        paramFound = true;
      }
    }
    
    resultJson += "}";

    if (paramFound) {
      request->send(200, "application/json", resultJson);
    } else {
      request->send(404, "application/json", "{\"error\":\"Aucun paramètre valide spécifié\"}");
    }
  });
  
  // Route pour recevoir les informations de la cible pour les rapports périodiques
  server->on("/target", HTTP_POST, [](AsyncWebServerRequest *request){
    Serial.println("Receive Request for a periodic report !"); 
    if (request->hasArg("ip") && request->hasArg("port") && request->hasArg("sp")) {
      jsonData.target_ip = request->arg("ip");
      jsonData.target_port = atoi(request->arg("port").c_str());
      jsonData.target_sp = atoi(request->arg("sp").c_str());
    }
    request->send(SPIFFS, "/index.html", String(), false, processor);//renvoie le spiffs
  });
  
  // Route par défaut pour les requêtes non trouvées (404)
  server->onNotFound([](AsyncWebServerRequest *request){
    request->send(404);
  });
}

// Fonction pour obtenir les valeurs des statuts en JSON
String getStatusJson(const String& params) {
  StaticJsonDocument<512> json;

  // Ajouter des champs au JSON en fonction des paramètres demandés
  if (params.indexOf("temperature") != -1) json["temperature"] = jsonData.temperature;
  if (params.indexOf("light") != -1) json["light"] = jsonData.luminosity;
  if (params.indexOf("highThreshold") != -1) json["highThreshold"] = jsonData.highThreshold;
  if (params.indexOf("lowThreshold") != -1) json["lowThreshold"] = jsonData.lowThreshold;
  if (params.indexOf("regulation") != -1) json["regulationState"] = jsonData.regulationState;
  if (params.indexOf("cooler") != -1) json["coolerState"] = jsonData.coolerState;
  if (params.indexOf("heat") != -1) json["heaterState"] = jsonData.heaterState;
  if (params.indexOf("fire") != -1) json["fire"] = jsonData.fireDetected;
  if (params.indexOf("fanSpeed") != -1) json["fanSpeed"] = jsonData.fanSpeed;
  if (params.indexOf("latitude") != -1) json["latitude"] = jsonData.latitude;
  if (params.indexOf("longitude") != -1) json["longitude"] = jsonData.longitude;
  if (params.indexOf("room") != -1) json["room"] = jsonData.room;
  if (params.indexOf("address") != -1) json["address"] = jsonData.address;
  if (params.indexOf("WiFiSSID") != -1) json["WiFiSSID"] = jsonData.WiFiSSID;
  if (params.indexOf("MAC") != -1) json["MAC"] = jsonData.MAC;
  if (params.indexOf("IP") != -1) json["IP"] = jsonData.IP;
  if (params.indexOf("identification") != -1) json["identification"] = jsonData.identification;
  if (params.indexOf("targetIP") != -1) json["target_ip"] = jsonData.target_ip;
  if (params.indexOf("targetPort") != -1) json["target_port"] = jsonData.target_port;
  if (params.indexOf("targetSp") != -1) json["target_sp"] = jsonData.target_sp;
  if (params.indexOf("esptime") != -1) json["esptime"] = jsonData.currentTime;
  if (params.indexOf("loc") != -1) json["loc"] = jsonData.loc;
  if (params.indexOf("user") != -1) json["user"] = jsonData.user;
  if (params.indexOf("lightThreshold") != -1) json["lightThreshold"] = jsonData.lightThreshold;

  String jsonResponse;
  serializeJson(json, jsonResponse); // Sérialisation du JSON en chaîne de caractères

  return jsonResponse;  // Retourne la chaîne JSON
}


// Fonction pour mettre à jour la configuration en fonction des paramètres reçus dans la requete set
String setConfiguration(const String& param, const String& value) {
  if (param == "cool" || param == "coolerState") {
    bool val;
    if (parseBool(value, val)) {
      jsonData.coolerState = val;
      return "Cooler " + String(val ? "activé" : "désactivé");
    } else {
      return "Valeur invalide pour 'cool': Attendu 'on' ou 'off'";
    }
  } else if (param == "heat" || param == "heaterState") {
    bool val;
    if (parseBool(value, val)) {
      jsonData.heaterState = val;
      return "Heater " + String(val ? "activé" : "désactivé");
    } else {
      return "Valeur invalide pour 'heat': Attendu 'on' ou 'off'";
    }
  } else if (param == "regulation" || param == "regulationState") {
    bool val;
    if (parseBool(value, val)) {
      jsonData.regulationState = val;
      return "Régulation " + String(val ? "activée" : "désactivée");
    } else {
      return "Valeur invalide pour 'regulation': Attendu 'on' ou 'off'";
    }
  } else if (param == "fire" || param == "fireDetected") {
    bool val;
    if (parseBool(value, val)) {
      jsonData.fireDetected = val;
      return "FireDetected " + String(val ? "activé" : "désactivé");
    } else {
      return "Valeur invalide pour 'fire': Attendu 'on' ou 'off'";
    }
  } else if (param == "luminosity") {
    if (isValidInteger(value)) {
      jsonData.luminosity = value.toInt();
      return "Luminosity défini à " + value;
    } else {
      return "Valeur invalide pour 'luminosity': Attendu un entier";
    }
  } else if (param == "lightThreshold") {
    if (isValidInteger(value)) {
      jsonData.lightThreshold = value.toInt();
      return "Light Threshold défini à " + value;
    } else {
      return "Valeur invalide pour 'lightThreshold': Attendu un entier";
    }    
  } else if (param == "temperature") {
    if (isValidFloat(value)) {
      jsonData.temperature = value.toFloat();
      return "Temperature définie à " + value;
    } else {
      return "Valeur invalide pour 'temperature': Attendu un flottant";
    }
  } else if (param == "highThreshold") {
    if (isValidFloat(value)) {
      jsonData.highThreshold = value.toFloat();
      return "High Threshold défini à " + value;
    } else {
      return "Valeur invalide pour 'highThreshold': Attendu un flottant";
    }
  } else if (param == "lowThreshold") {
    if (isValidFloat(value)) {
      jsonData.lowThreshold = value.toFloat();
      return "Low Threshold défini à " + value;
    } else {
      return "Valeur invalide pour 'lowThreshold': Attendu un flottant";
    }
  } else if (param == "fanSpeed") {
    if (isValidFloat(value) && value.toFloat() >= 0) {
      Serial.print(value.toFloat());
      jsonData.fanSpeedObj = value.toFloat();
      return "FanSpeed défini à " + value;
    } else {
      return "Valeur invalide pour 'fanSpeed': Attendu un entier positif";
    }
  } else if (param == "WiFiSSID") {
    jsonData.WiFiSSID = value;
    return "WiFiSSID défini à " + value;
  } else if (param == "MAC") {
    jsonData.MAC = value;
    return "MAC défini à " + value;
  } else if (param == "IP") {
    jsonData.IP = value;
    return "IP défini à " + value;
  } else if (param == "identification") {
    jsonData.identification = value;
    return "Identification définie à " + value;
  } else if (param == "target_ip") {
    jsonData.target_ip = value;
    return "Target IP défini à " + value;
  } else if (param == "target_port") {
    if (isValidInteger(value)) {
      jsonData.target_port = value.toInt();
      return "Target Port défini à " + value;
    } else {
      return "Valeur invalide pour 'target_port': Attendu un entier";
    }
  } else if (param == "target_sp") {
    if (isValidInteger(value)) {
      jsonData.target_sp = value.toInt();
      return "Target SP défini à " + value;
    } else {
      return "Valeur invalide pour 'target_sp': Attendu un entier";
    }
  } else {
    return "404"; // Retourne "404" si le paramètre n'est pas trouvé
  }
}
