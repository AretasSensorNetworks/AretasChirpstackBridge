from threading import Event
from queue import Queue
import configparser
import logging
from logging.handlers import RotatingFileHandler
from message_harvester import MessageHarvester
from mqtt_subscriber import MQTTChirpstackSubscriber

# An example of using logging.basicConfig rather than logging.fileHandler()
logging.basicConfig(level=logging.DEBUG,
                    handlers=[
                        RotatingFileHandler("AretasChirpstackBridge.log", maxBytes=50000000, backupCount=5)
                    ],
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    import signal

    # read in the global app config
    config = configparser.ConfigParser()
    config.read('config.cfg')

    # this is a shared event handler among all the threads
    thread_sig_event = Event()


    def signal_handler(sig, frame):
        import sys
        print('You pressed Ctrl+C!')
        thread_sig_event.set()
        sys.exit(0)


    # define the signal handler for SIGINT
    signal.signal(signal.SIGINT, signal_handler)

    # this is the shared message queue for the serial port and message harvester threads
    mq_payload_queue: Queue = Queue()

    logger.info("MQTTT topic monitor thread starting:")
    mqtt_subscriber_thread = MQTTChirpstackSubscriber(mq_payload_queue,
                                                      thread_sig_event)
    mqtt_subscriber_thread.start()
    logger.info("MQTT topic monitor thread started.")

    logger.info("Message harvester thread starting:")
    message_harvester_thread = MessageHarvester(mq_payload_queue,
                                                thread_sig_event)
    message_harvester_thread.start()
    logger.info("Message harvester thread started.")

    # Test setting the termination event
    # print("Setting thread_sig_event")
    # thread_sig_event.set()

    mqtt_subscriber_thread.join()
    message_harvester_thread.join()
