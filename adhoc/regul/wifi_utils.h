/* 
 * Fichier : wifi_utils.h
 * Auteur : Noé Florence 
 */

 
#include <WiFi.h> 
#include <WiFiMulti.h>

// Définition des constantes pour la gestion du WiFi
#define SaveDisconnectTime 1000 
#define WiFiMaxTry 10

// Prototypes des fonctions utilitaires pour le WiFi
String translateEncryptionType(wifi_auth_mode_t encryptionType);
void wifi_printstatus(int C);
//void wifi_connect_basic(String hostname, String ssid, String passwd);
//int wifi_search_neighbor();
void wifi_connect_multi(String hostname);
void sendPostRequest();
String httpPOSTRequesttest(const char* UrlServer, String payload);
