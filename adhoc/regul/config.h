/* 
 * Fichier : config.h
 * Auteur : Noé Florence 
*/


#ifndef CONFIG_H
#define CONFIG_H

#include <Arduino.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Adafruit_NeoPixel.h>
#include <ArduinoJson.h>

/* ---- Définition des limites ---- */
#define LIMITHEATHIGH 25.0
#define LIMITHEATLOW 24.0
#define LIMITLIGHT 400

/* ---- Définition des broches ---- */
#define LIGHTSENSORPIN A5
#define HEATSENSORPIN 23
#define PINSTRIP 13
#define NUMLEDS 15
#define FIRELEDPIN 2
#define HEATERPIN 21
#define CLIMPIN 19

// Configuration du ventilateur (PWM)
#define FAN_PWM_CHANNEL 0
#define FAN_PWM_FREQ 5000
#define FAN_PWM_RESOLUTION 8
#define FAN_PIN 27

// Configuration des informations de l utilisateur
#define IDENTIFICATION "P_22411036"
#define LOCATION "biot"
#define USER "noe";

#define USE_SERIAL Serial

/* ---- Déclarations externes ---- */
extern OneWire oneWire;
extern DallasTemperature tempSensor;
extern Adafruit_NeoPixel stripLed;

extern unsigned long loop_period;
extern float tempSeuil;

#endif // CONFIG_H
