#include "mqtt_utils.h"
#include <WiFi.h>
#include <Arduino.h>

extern const char* mqtt_server;
extern const char* mqtt_topic;

void mqtt_reconnect(PubSubClient& client) {
  // Loop until we're reconnected
  while (!client.connected()) {
    Serial.print("Attempting MQTT connection...");
    // Create a client ID
    String clientId = "ESP32Client-";
    clientId += WiFi.macAddress();  

    // Attempt to connect
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      // Subscribe to the topic
      client.subscribe(mqtt_topic);

      String stateTopic = "uca/iot/piscine/" + jsonData.identification + "/state";
      client.subscribe(stateTopic.c_str());
      Serial.print("Subscribed to: ");
      Serial.println(stateTopic);
    
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" try again in 5 seconds");
      // Wait 5 seconds before retrying
      delay(5000);
    }
  }
}
