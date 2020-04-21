import gatt
from time import monotonic, time
from threading import Thread
from queue import Queue

from logging import getLogger

log = getLogger(__name__)


class QueryDevice(gatt.Device):
    def __init__(self, manager, device_status):
        super().__init__(device_status.addr, manager)
        self.device = device_status

    def connect_succeeded(self):
        super().connect_succeeded()
        self.device.connect_succeeded()
        log.info("Connected", extra={'mac': self.mac_address})

    def connect_failed(self, error):
        super().connect_failed(error)
        self.device.connect_failed()
        log.info("Connection failed: %s", str(error), extra={'mac': self.mac_address})

    def disconnect_succeeded(self):
        super().disconnect_succeeded()
        self.device.complete()

    def services_resolved(self):
        super().services_resolved()
        self.device.services_resolved(len(self.services))
        self.read_services()

        log.info("Resolved %i services", len(self.services), extra={'mac': self.mac_address})

    def read_services(self):
        for service in self.services:
            for characteristic in service.characteristics:
                if characteristic.uuid in ('64b81e3c-d60c-4f08-8396-9351b04f7591', '1000-8000-00805f9b34fb'):
                    characteristic.read_value()

    def characteristic_value_updated(self, characteristic, value):
        log.info("Retrieved %s with value %s", characteristic.uuid, value.decode("utf-8"), extra={'mac': self.mac_address})
        if characteristic.uuid == '64b81e3c-d60c-4f08-8396-9351b04f7591':
            self.device.device_id = value.decode("utf-8")
        else:
            self.device.public = value.decode("utf-8")

        if self.device.device_id and self.device.public:
            self.device.inquiry_finished()
            self.disconnect()
        else:
            self.device.push()

    def characteristic_read_value_failed(self, characteristic, error):
        log.warning("Failed to read characteristic %s: %s", characteristic.uuid, str(error), extra={'mac': self.mac_address})
        self.device.complete()


class DeviceStatus:
    def __init__(self, mac_address, result_queue):
        self.addr = mac_address
        self.public = None
        self.device_id = None
        self.notify = result_queue
        self.pending = False
        self.connect_started = None
        self.services_retrieved = None
        self.connect_ended = None
        self.inquiry_ended = None
        self.connected_time = None

    def connect_start(self):
        self.pending = True
        self.connect_started = monotonic()

    def connect_succeeded(self):
        self.connect_ended = monotonic()
        self.connected_time = time()

    def services_resolved(self, num_services):
        self.services_retrieved = num_services

    def inquiry_finished(self):
        self.inquiry_ended = monotonic()
        self.complete()

    def connect_failed(self):
        self.complete()

    def push(self):
        self.notify.put(self)

    def complete(self):
        self.pending = False
        self.push()


def start_connector(completed_queue, adapter='hci0'):
    connect_queue = Queue()

    manager = gatt.DeviceManager(adapter)
    manager.start_discovery()

    Thread(target=manager.run, daemon=True).start()

    scheduler = Thread(target=connect_scheduler, args=(connect_queue, completed_queue, manager), daemon=True)
    scheduler.start()

    return scheduler, connect_queue


def connect_scheduler(connect_queue, result_queue, manager):
    while True:
        mac = connect_queue.get()
        dev_status = DeviceStatus(mac, result_queue)

        bhd_known = {d.mac_address for d in manager.devices()}

        if mac not in bhd_known:
            log.warning("Not yet seen by bluetoothd, skipping", extra={'mac': mac})
            continue

        query = QueryDevice(manager, dev_status)
        dev_status.connect_start()
        query.connect()
