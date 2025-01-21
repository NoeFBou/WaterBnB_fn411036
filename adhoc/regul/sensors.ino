/* 
 * Fichier : sensors.ino
 * Auteur : Noé Florence 
 * Dascription : fonction pour controler les capteurs et les actionneurs 
 */

 
#include "config.h"
#include "jsondata.h"

// Fonction d'initialisation des capteurs et actionneurs
void initSensor(){
  tempSensor.begin(); // Initialisation du capteur de température
  stripLed.begin();   // Initialisation du ruban LED
  stripLed.show();

  // Initialisation des capteurs et actionneurs
  pinMode(CLIMPIN, OUTPUT);
  pinMode(HEATERPIN, OUTPUT);
  pinMode(FIRELEDPIN, OUTPUT);
  
  // Configuration du ventilateur
  ledcAttachChannel(FAN_PIN, FAN_PWM_FREQ, FAN_PWM_RESOLUTION, FAN_PWM_CHANNEL);

  // Allumer le ruban LED en vert au démarrage
  setAllPixelLedStrip(0, 255, 0);
}


// Fonction pour définir la couleur de tout le ruban LED
void setAllPixelLedStrip(int r, int g, int b) {
  for (int i = 0; i < NUMLEDS; i++) {
    stripLed.setPixelColor(i, stripLed.Color(r, g, b));
  }
  stripLed.show();
}

// Fonction pour lire les valeurs des capteurs et les enregistrer
void readSensors() {
  tempSensor.requestTemperaturesByIndex(0);
  jsonData.temperature = tempSensor.getTempCByIndex(0);
  jsonData.fanSpeed = ledcRead(FAN_PIN);
  jsonData.luminosity = analogRead(LIGHTSENSORPIN);
}

// Fonction pour mettre à jour l'état en fonction des mesures
void updateState() {
  
  // Contrôle de la température
  if (jsonData.temperature >  jsonData.highThreshold) { //si au dessus de la limite haute
    jsonData.heaterState =true;
    jsonData.coolerState =false;
    float fanSpeed = (jsonData.temperature - jsonData.highThreshold)/ tempSeuil; //vitesse progressive de ventilateur
    
    jsonData.fanSpeedObj = fanSpeed;
    
    
  } else if (jsonData.temperature < jsonData.lowThreshold) { //si au dessus de la limite basse
    jsonData.heaterState =false;
    jsonData.coolerState =true;
    jsonData.fanSpeedObj=0;

  } else { //si entre les deux
    jsonData.heaterState =false;
    jsonData.coolerState =false;
    jsonData.fanSpeedObj=0;
  }

  if (jsonData.luminosity > jsonData.lightThreshold) { //detection incendie
    jsonData.fireDetected = true;
    jsonData.fanSpeedObj=0; //on eteint le ventilateur
  } else {
    jsonData.fireDetected = false;
  }
}

// Fonction pour contrôler les actionneurs en fonction de l'état
void controlActuators(){
  fanControl(jsonData.fanSpeedObj);
  
  if (jsonData.heaterState){
    climControl(HIGH); //activation de la clim
  }
  else{
    climControl(LOW); //desactivation de la clim
  }
  
  if (jsonData.coolerState){
    heaterControl(HIGH); //activation du chauffage
  }
  else{
    heaterControl(LOW);//desactivation du chauffage
  } 
    
  if (jsonData.fireDetected){
    fireLed(HIGH); //led pour la detection de l incendie
  }
  else{
    fireLed(LOW);
  }
}

// Fonctions pour contrôler le chauffage
void heaterControl(int val){
  digitalWrite(HEATERPIN, val);
}

// Fonctions pour contrôler la clim
void climControl(int val){
    digitalWrite(CLIMPIN, val);
}

// Fonctions pour contrôler le ventilateur
void fanControl(float val){
  float fanSpeed = constrain(val, 0.0, 1.0);
  uint8_t fanPWMValue = (uint8_t)(fanSpeed * 255);
  ledcWrite(FAN_PIN, fanPWMValue);
}

// Fonctions pour contrôler la led incendie
void fireLed(int val){
  digitalWrite(FIRELEDPIN, val);
}

void handleLedColor() {
  // Priorité au rouge si on est encore dans la fenêtre des 30s
  if (millis() < redUntilTime) {
    setAllPixelLedStrip(255, 0, 0);
    return; 
  }

  if (jsonData.occupied) {
    setAllPixelLedStrip(255, 255, 0);
  } else {
    setAllPixelLedStrip(0, 255, 0);
  }
}
