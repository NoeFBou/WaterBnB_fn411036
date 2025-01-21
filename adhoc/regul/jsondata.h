/* 
 * Fichier : jsondata.h
 * Auteur : Noé Florence 
 * Description : struture qui represente le json envoyer au dashboard
*/


#ifndef JSONDATA_H
#define JSONDATA_H

#include <Arduino.h>
#include "config.h"
/*
struct LocalData{
  JsonData jsonData;
  
};*/

struct JsonData {
  int luminosity;
  float temperature;
  float highThreshold = LIMITHEATHIGH;
  float lowThreshold = LIMITHEATLOW;
  int lightThreshold = LIMITLIGHT;
  bool coolerState;
  bool heaterState;
  bool regulationState;
  bool fireDetected;
  int fanSpeed;
  float fanSpeedObj;

  // Informations de localisation
  const double latitude = 43.563966;
  const double longitude = 7.08021;
  char room[50] = "td6";
  char address[200] = "Les lucioles";

  // Informations réseau
  String WiFiSSID;
  String MAC;
  String IP;

  // Informations d'identification
  String identification;
  long currentTime;
  String loc;
  String user;

  // Informations pour l'envoi de données à un serveur cible
  String target_ip;
  int target_port;
  int target_sp;
  bool hotspot;
  bool occupied;
};

extern JsonData jsonData;

#endif // JSONDATA_H
