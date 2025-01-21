#ifndef MQTT_UTILS_H
#define MQTT_UTILS_H

#include <PubSubClient.h>

extern const char* mqtt_server;
extern const char* mqtt_topic;

void mqtt_reconnect(PubSubClient& client);

#endif
