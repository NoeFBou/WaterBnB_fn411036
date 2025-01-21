/* 
 * Fichier : utils.h
 * Auteur : Noé Florence 
 */

 
#ifndef UTILS_H
#define UTILS_H
#include <math.h>

// Prototypes des fonctions utilitaires
void printValue();
String convertToJson();
void initJson();
bool parseBool(const String& str, bool& result);
bool isValidInteger(const String& str);
bool isValidFloat(const String& str);
float calculateDistance(float lat1, float lon1, float lat2, float lon2);

#endif // UTILS_H
