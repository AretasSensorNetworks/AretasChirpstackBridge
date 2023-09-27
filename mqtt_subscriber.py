import configparser
import logging
from multiprocessing import Event
from queue import Queue
from threading import Thread
from time import time
from AretasPythonAPI.utils import Utils as AretasUtils
from sensor_message_item import SensorMessageItem
import random
import paho.mqtt.client as mqtt
import json
from datetime import datetime


class MQTTChirpstackSubscriber(Thread):
    """
    This thread monitors the MQTT queue for sensor messages
    It can be extended to support any of the topics in chirpstack but
    we only care about the sensor messages for now
    """
    def __init__(self, payload_queue: Queue, sig_event: Event):

        super(MQTTChirpstackSubscriber, self).__init__()
        self.logger = logging.getLogger(__name__)

        # read in the global app config
        config = configparser.ConfigParser()
        config.read('config.cfg')

        self.payload_queue = payload_queue

        self.sig_event = sig_event

        self.mqttc = None
        self.mqtt_hostname = config.get("MQTT", "mqtt_host")
        self.mqtt_port = config.getint("MQTT", "mqtt_port")
        self.mqtt_topic = config.get("MQTT", "mqtt_topic")

        self.logger.info("MQTT Connection info host:{} port: {} topic: {}".format(
            self.mqtt_hostname,
            self.mqtt_port,
            self.mqtt_topic))

    def on_connect(self, client, userdata, flags, rc):
        # The callback for when the client receives a CONNACK response from the server.
        print("Connected with result code " + str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe("#")

    def on_message(self, client, userdata, msg):
        """
        Determine what topic generated the message and dispatch the
        message to the appropriate decoder
        """
        msg_payload = json.loads(msg.payload)
        msg_topic_tok = msg.topic.split('/')
        self.logger.debug("Msg topic:{} Raw payload:{}".format(msg.topic, msg.payload))
        if msg_topic_tok[0] == 'gateway':
            result = self.decode_gateway_msg(msg_payload)
        elif msg_topic_tok[1] == 'application':
            pass
        else:
            self.logger.info("Unrecognized topic:{}" + msg.topic)
            pass

    def decode_sensor_payload(self, msg_payload):
        """Start to decode a sensor message payload"""
        device_eui = msg_payload['deviceInfo']['devEui']
        data_frame = msg_payload['object']
        date_stamp = msg_payload['time']
        dt_obj = datetime.fromisoformat(date_stamp)
        # enqueue the sensor messages for the message_harvester
        # self.payload_queue.put(item)
        # self.logger.info("Enqueued {} items".format(len(payload_items)))

        self.logger.debug("Received application message:{} {} {}".format(device_eui, data_frame, dt_obj))

        return True

    def decode_gateway_msg(self, msg_payload):
        self.logger.debug("This class does not support decoding gateway messages (nothing to do)")
        return False

    def run(self):
        """
        For now just spawn the connection and loop forever while the client does the work
        Try and exit gracefully on signal
        Later, we'll extend with connection retry logic upon disconnect or network errors
        """

        self.mqttc = mqtt.Client()
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_message = self.on_message

        self.mqttc.connect(self.mqtt_hostname, self.mqtt_port, 60)

        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        # Other loop*() functions are available that give a threaded interface and a
        # manual interface.
        # mqttc.loop_forever()

        while True:
            if self.sig_event.is_set():
                self.logger.info("Exiting {}".format(self.__class__.__name__))
                break

