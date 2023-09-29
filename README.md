# AretasChirpstackBridge
An MQTT Chirpstack bridge to bring LoRaWAN sensor data into the Aretas API

We monitor the Chirpstack MQTT broker for gateway and application messages

Currently, we don't do anything with gateway messages 

We parse application/APPLICATION_ID/device/DEVICE_ID/event/up topic messages to extract the sensor data.

Chirpstack supports the concept of "CODECS", which are essentially payload decoder Javascript functions that
decode the device payload and inject a more "friendly" object into the payload.

Chirpstack has a rich message payload:
```
{
    'deduplicationId': '28dc14db-2a38-4cc7-ab52-edd123f4a471a', 
    'time': '2023-09-26T06:07:01.408431+00:00', 
    'deviceInfo': {
        'tenantId': '52f14cd4-4562-4fbd-2224-4025e1d49242', 
        'tenantName': 'ChirpStack', 
        'applicationId': '33332f95-9d22-4216-bdfc-ae5020ebee07', 
        'applicationName': 'Test Application (Level)', 
        'deviceProfileId': '698efe4a-c2e0-2328-9e62-fae2168b5969', 
        'deviceProfileName': 'Test Device Profile', 
        'deviceName': 'LDDS75-8-1', 
        'devEui': 'd092812784829ced', 
        'deviceClassEnabled': 'CLASS_A', 
        'tags': {}
    }, 
    'devAddr': '020e0031', 
    'adr': True, 
    'dr': 3, 
    'fCnt': 40, 
    'fPort': 2, 
    'confirmed': False, 
    'data': 'DR4AAAAAAAE=', 
    'object': {
        'temp_c_internal': '0.00', 
        'interrupt_flag': 0.0, 
        'sensor_flag': 1.0, 
        'battery': 3.358, 
        'distance': '0 mm'
    }, 
    'rxInfo': [
        {
            'gatewayId': 'd59285fdfe2406df', 
            'uplinkId': 32144, 
            'time': '2023-09-26T06:07:01.408431+00:00', 
            'rssi': -95, 
            'snr': 12.0, 
            'channel': 6, 
            'rfChain': 1, 
            'location': {
                'latitude': 55.328534305413086, 
                'longitude': -125.5557999610901
            }, 'context': '78iwe12==f', 
            'metadata': {
                'region_common_name': 'US915', 
                'region_config_id': 'us915_0'
            }, 'crcStatus': 'CRC_OK'
        }], 
    'txInfo': {
        'frequency': 903500000, 
        'modulation': {
            'lora': {
                'bandwidth': 125000, 
                'spreadingFactor': 7, 
                'codeRate': 'CR_4_5'
            }
        }
    }
}
```

The main fields we are concerned about are:
- object field (contains the CODEC decoded sensor data)
- time (to be decoded to a unix epoch timestamp)
- devEUI for device identification
- RSSI for signal strength / link quality

Once the messages are decoded and turned into an AretasSensorMessage object, we inject each sensormessage into a
thread shared queue. The queue is then emptied by a message harvester and API messages are sent to the REST API. 

API REST stuff, access control, etc. is handled by the AretasPythonAPI module (added as a git submodule)

## CODECS and type mapping
Ideally, we would just create CODECs in Chirpstack to map the various types to the correct sensor metadata types
used in the Aretas API. However, it's nice to have CODECs available in a human readable format on the MQTT topics 
for easier viewing / debugging / etc. 

So have your CODEC emit a JSON object like:
``{
"temperature":24.5,
"distance":500.0
...
}``

Then, in the AretasChirpstackBridge config file (config.cfg) edit the line

```sensor_type_mapping=battery:45,temp_c_internal:241,distance:220,rssi:134```

And include your type names and the Aretas type ints.

## Config & Running

The config.cfg file is pretty self-explanatory, just fill it out :)

To run just run ```python3 backend_daemon.py```

There should be very little output to stdout, but you'll find 
a fairly verbose log file in the local directory called AretasChirpstackBridge.log

For increase verbosity, set log level to debug.