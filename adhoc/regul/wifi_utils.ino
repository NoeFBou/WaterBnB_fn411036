/* 
 * Fichier : wifi_utils.ino
 * Auteur : Noé Florence 
 * Description : Configuration de la connection au wifi et fonction utilitaire pour les requetes http
 */
 
#include <WiFi.h> 
#include <HTTPClient.h>

#include "wifi_utils.h"
#include "jsondata.h"
#include "utils.h"

/*--------------------------------------------------------------------------*/

// Fonction pour envoyer une requête POST au serveur cible
void sendPostRequest() {
  interval = jsonData.target_sp * 1000; // Conversion de l'intervalle en millisecondes
  const int httpPort = jsonData.target_port;
  // Création de l'URL pour la requête
  String path = "/esp";
  String url = "http://"+String(jsonData.target_ip.c_str()) +":" +String(jsonData.target_port) + path+"?mac"+jsonData.MAC;
  String payload = convertToJson();

  // Vérifie si l'intervalle est écoulé
  //printValue(); debug
  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= interval) { 
    String ret = httpPOSTRequesttest(url.c_str(), payload);
      Serial.println(ret);
    } else {
      Serial.println("Erreur de connexion WiFi");
    }
  
}

// Fonction pour effectuer une requête HTTP POST
String httpPOSTRequesttest(const char* UrlServer, String payload) {

  String response = "{}";
  HTTPClient http; // Entité du protocole HTTP => client

  Serial.printf("URL demandée : %s\n", UrlServer);

  // Configuration du serveur cible et de l'URL
  http.begin(UrlServer);

  // Ajout de l'en-tête pour spécifier le type de contenu
  http.addHeader("Content-Type", "application/json");

  // Connexion et envoi de la requête HTTP POST avec le payload
  int httpResponseCode = http.POST(payload);

  // Récupération de la réponse
  if (httpResponseCode > 0) {
    Serial.printf("Code de réponse HTTP : %d\n", httpResponseCode);
    response = http.getString();
  } else {
    Serial.printf("Code d'erreur sur la requête HTTP POST : %d\n", httpResponseCode);
  }

  // Fin de la connexion et libération des ressources
  http.end();

  return response;
}

// Fonction pour traduire le type d'encryption du WiFi
String translateEncryptionType(wifi_auth_mode_t encryptionType) {
  
  switch (encryptionType) {
    case (WIFI_AUTH_OPEN):
      return "Open";
    case (WIFI_AUTH_WEP):
      return "WEP";
    case (WIFI_AUTH_WPA_PSK):
      return "WPA_PSK";
    case (WIFI_AUTH_WPA2_PSK):
      return "WPA2_PSK";
    case (WIFI_AUTH_WPA_WPA2_PSK):
      return "WPA_WPA2_PSK";
    case (WIFI_AUTH_WPA2_ENTERPRISE):
      return "WPA2_ENTERPRISE";
  }
}
/*--------------------------------------------------------------------------*/

// Fonction pour afficher l'état du WiFi
void wifi_printstatus(int C){
  /* print the status of the connected wifi  in two ways ! */

  if (C){
    // Use Pure C =>  array of chars
    Serial.printf("WiFi Status : \n");
    Serial.printf("\tIP address : %s\n", WiFi.localIP().toString().c_str());
    Serial.printf("\tMAC address : %s\n", WiFi.macAddress().c_str());
    Serial.printf("\tSSID : %s\n", WiFi.SSID());
    Serial.printf("\tReceived Signal Strength Indication : %ld dBm\n",WiFi.RSSI());
    Serial.printf("\tReceived Signal Strength Indication : %ld %\n",constrain(2 * (WiFi.RSSI() + 100), 0, 100));
    Serial.printf("\tBSSID : %s\n", WiFi.BSSIDstr().c_str());
    Serial.printf("\tEncryption type : %s\n", translateEncryptionType(WiFi.encryptionType(0)));
    jsonData.MAC = WiFi.macAddress().c_str();
    jsonData.WiFiSSID = WiFi.SSID();
    jsonData.IP = WiFi.localIP().toString().c_str();
  }
  else {
    // Use of C++ =>  String !
    String s = "WiFi Status : \n";
    //s += "\t#" + String() + "\n";
    s += "\tIP address : " + WiFi.localIP().toString() + "\n"; 
    s += "\tMAC address : " + String(WiFi.macAddress()) + "\n";
    s += "\tSSID : " + String(WiFi.SSID()) + "\n";
    s += "\tReceived Sig Strength Indication : " + String(WiFi.RSSI()) + " dBm\n";
    s += "\tReceived Sig Strength Indication : " + String(constrain(2 * (WiFi.RSSI() + 100), 0, 100)) + " %\n";
    s += "\tBSSID : " + String(WiFi.BSSIDstr()) + "\n";
    s += "\tEncryption type : " + translateEncryptionType(WiFi.encryptionType(0))+ "\n";
    Serial.print(s);

    jsonData.MAC = WiFi.macAddress().c_str();
    jsonData.WiFiSSID = WiFi.SSID();
    jsonData.IP = WiFi.localIP().toString().c_str();
  }
}
/*--------------------------------------------------------------------------*/
// Fonction pour se connecter au WiFi avec plusieurs SSID possibles
void wifi_connect_multi(String hostname){
  int nbtry = 0; // Nb of try to connect
  WiFiMulti wm; // Creates an instance of the WiFiMulti class
  
  // Ajout des SSID et mots de passe possibles
  wm.addAP("Boux3", "12345678");
  wm.addAP("71258", "testnoenoe");
  wm.addAP("maBox", "nonolerobot");

  wm.addAP("HUAWEI-6EC2", "FGY9MLBL");
  wm.addAP("HUAWEI-553A", "QTM06RTT");
  wm.addAP("GMAP", "vijx47050");
  wm.addAP("Livebox-B870","MYCNcZqnvsWsiy7s52");
  
  WiFi.mode(WIFI_OFF);   
  WiFi.mode(WIFI_STA); // Configuration du WiFi en mode station
  WiFi.disconnect(true); // Déconnexion de tout AP précédent

  // Définition du nom d'hôte
  WiFi.setHostname(hostname.c_str());

  // Tentatives de connexion jusqu'à la réussite ou le maximum autorisé
  while(wm.run() != WL_CONNECTED && (nbtry < WiFiMaxTry)) {
    Serial.printf("\nAttempting %d to connect AP", nbtry);  
    delay(SaveDisconnectTime);
    Serial.print(".");
    nbtry++;
  }
  
  if(wm.run() == WL_CONNECTED) {
    Serial.printf("\nwifiMulti connected on %s !", WiFi.SSID());
  }
  else
    ESP.restart();
}
