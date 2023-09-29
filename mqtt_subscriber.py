import configparser
import logging
from multiprocessing import Event
from queue import Queue
from threading import Thread
from AretasPythonAPI.utils import Utils as AretasUtils
from sensor_message_item import SensorMessageItem
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
        self.mqtt_client_id = config.get("MQTT", "mqtt_client_id")

        self.logger.info("MQTT Connection info host:{} port: {} topic: {}".format(
            self.mqtt_hostname,
            self.mqtt_port,
            self.mqtt_topic))

        self.type_maps = self.load_type_maps(config)

        self.logger.debug("Loaded type maps:{}".format(self.type_maps))

    def load_type_maps(self, config: configparser.ConfigParser) -> dict[str, int]:
        configs_serialized = config.get("API", "sensor_type_mapping")
        configs_serialized_tok = configs_serialized.split(',')

        ret = dict[str, int]()

        for type_map in configs_serialized_tok:
            type_map_tok = type_map.split(':')
            key, value = str(type_map_tok[0]), int(type_map_tok[1])
            ret[key] = value

        return ret

    def on_connect(self, client, userdata, flags, rc):
        # The callback for when the client receives a CONNACK response from the server.
        self.logger.info("Connected to MQTT broker with result code " + str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        client.subscribe(self.mqtt_topic)

    def on_disconnect(self, client, userdata, rc):
        self.logger.error("MQTT broker disconnected! Reason:{}".format(rc))

    def on_message(self, client, userdata, msg):
        """
        Determine what topic generated the message and dispatch the
        message to the appropriate decoder
        """
        msg_payload = json.loads(msg.payload)
        msg_topic_tok = msg.topic.split('/')
        self.logger.debug("Msg topic:{} Raw payload:{}".format(msg.topic, msg.payload))
        if msg_topic_tok[0] == 'gateway':
            # we don't currently support gateway messages but leave a stub here
            result = self.decode_gateway_msg(msg_payload)

        elif msg_topic_tok[0] == 'application':
            # we only support one application message right now
            if ('event' in msg_topic_tok) and (msg_topic_tok[-1] == 'up'):
                result = self.decode_sensor_payload(msg_payload)
                if result == 0:
                    self.logger.error("Decoded zero payload  items")
            else:
                self.logger.info("Unhandled application event:{}".format(msg.topic))
        else:
            self.logger.info("Unhandled topic:{}" + msg.topic)

    def decode_sensor_payload(self, msg_payload)->int:
        """Start to decode a sensor message payload"""
        # if there is no codec installed / configured, then it's quite possible
        # that the object key/value will not be present in the json payload
        if 'object' not in msg_payload.keys():
            self.logger.error(
                "No object key/value in the JSON payload, check if your CODEC is installed correctly in Chirpstack"
            )
            return -1

        payload_items = []
        device_eui = msg_payload['deviceInfo']['devEui']
        # convert the device EUI to a 48-bit int for the Aretas API
        device_mac = MQTTChirpstackSubscriber.get_truncate_48(device_eui)
        # the Chirpstack CODEC injects the decoded payload data into the "object" key/value
        data_frame = msg_payload['object']
        # get the ISO formatted date
        date_stamp = msg_payload['time']
        dt_obj = datetime.fromisoformat(date_stamp)
        # convert it to a unix epoch timestmap
        dt_timestamp = int(dt_obj.timestamp() * 1000)

        # iterate the sensortype/data entries
        for key in data_frame.keys():
            if key in self.type_maps.keys():
                sensor_type = self.type_maps[key]
                sensor_msg = SensorMessageItem(device_mac, sensor_type, float(data_frame[key]), dt_timestamp)
                payload_items.append(sensor_msg)
            else:
                self.logger.info("Unrecognized type in dataframe: {} {}".format(key, data_frame[key]))

        # enqueue the sensor messages for the message_harvester
        for item in payload_items:
            self.payload_queue.put(item)

        self.logger.info("Enqueued {} items".format(len(payload_items)))

        self.logger.debug("Received application message:{} {} {}".format(device_eui, data_frame, dt_obj))

        return len(payload_items)

    def decode_gateway_msg(self, msg_payload):
        self.logger.debug("This class does not support decoding gateway messages (nothing to do)")
        return False

    @staticmethod
    def get_truncate_48(euid_str: str):
        """
        This will parse the last 12 chars in the EUID and convert to a 48-bit integer
        """
        # parse the last 12 chars as a hexadecimal number
        return int(euid_str[-12:], 16)

    def run(self):
        """
        For now just spawn the connection and loop forever while the client does the work
        Try and exit gracefully on signal
        Later, we'll extend with connection retry logic upon disconnect or network errors
        """

        self.mqttc = mqtt.Client(client_id=self.mqtt_client_id)
        self.mqttc.on_connect = self.on_connect
        self.mqttc.on_message = self.on_message
        self.mqttc.on_disconnect = self.on_disconnect

        self.logger.info("Connecting to MQTT broker")

        # we need to use connect_async and loop_start (non blocking calls)
        # so we can enter our infinity loop
        self.mqttc.connect_async(self.mqtt_hostname, self.mqtt_port, 60)
        self.mqttc.loop_start()

        # Blocking call that processes network traffic, dispatches callbacks and
        # handles reconnecting.
        # Other loop*() functions are available that give a threaded interface and a
        # manual interface.
        # mqttc.loop_forever()

        while True:
            if self.sig_event.is_set():
                self.logger.info("Exiting {}".format(self.__class__.__name__))
                break
