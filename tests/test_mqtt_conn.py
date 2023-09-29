import paho.mqtt.client as mqtt
import json


def on_connect(client, userdata, flags, rc):
    # The callback for when the client receives a CONNACK response from the server.
    print("Connected to MQTT broker with result code " + str(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe('#')


def on_message(client, userdata, msg):
    msg_payload = json.loads(msg.payload)
    print("Msg topic:{} Raw payload:{}".format(msg.topic, msg_payload))


mqttc = mqtt.Client()
mqttc.on_connect = on_connect
mqttc.on_message = on_message

mqttc.connect('dev.aretas.ca', 18833, 60)

mqttc.loop_forever()
