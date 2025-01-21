/* 
 * Fichier : routes.h
 * Auteur : Noé Florence 
*/


#ifndef ROUTES_H
#define ROUTES_H

#include "ESPAsyncWebServer.h"

// Prototypes des fonctions pour les routes HTTP
void setup_http_routes(AsyncWebServer* server);
String processor(const String& var);
String getStatusJson(const String& params);
String setConfiguration(const String& param, const String& value);

#endif // ROUTES_H
