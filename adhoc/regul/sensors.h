/* 
 * Fichier : sensors.h
 * Auteur : Noé Florence 
 */

 
#ifndef SENSORS_H
#define SENSORS_H

// Prototypes des fonctions liées aux capteurs et actionneurs
void updateState();
void controlActuators();
void setAllPixelLedStrip(int r, int g, int b);
void readSensors();
void initSensor();
void heaterControl(int val);
void climControl(int val);
void fanControl(int val);
void fireLed(int val);

#endif // SENSORS_H
