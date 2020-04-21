from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from queue import Empty
from time import time
from survey.model import *
from survey.discover import *
from survey.connector import start_connector

from logging import getLogger

log = getLogger(__name__)

RETRY_DELAY = 60.0
NO_MAC = '__-__-__-__-__-__'


def process_reports(db_session, report_queue, connect_queue):
    if report_queue.empty():
        return True

    while True:
        try:
            adv_report = report_queue.get_nowait()
        except Empty:
            db_session.commit()
            return True

        device = db_session.query(Random).get(adv_report.addr)
        q_time = time()

        if not device:
            device = Random(mac_address=adv_report.addr)
            db_session.add(device)
            connect_queue.put(adv_report.addr)
            device.queued = q_time
            log.info("Discovered", extra={'mac': adv_report.addr})
        elif not device.device_id and q_time - device.queued > RETRY_DELAY:
            log.info("Scheduled connect retry", extra={'mac': adv_report.addr})
            connect_queue.put(adv_report.addr)
            device.queued = q_time

        device.signal.append(Signal(time=adv_report.time, rssi=adv_report.rssi,
                                    reported=adv_report[EIR_TX_Power_Level].level if
                                    EIR_TX_Power_Level in adv_report else None))


def process_connections(db_session, status_queue):
    while True:
        try:
            r = status_queue.get_nowait()
        except Empty:
            db_session.commit()
            return True

        device = db_session.query(Random).get(r.addr)
        device.attempts += 1

        if r.connected_time:
            device.connected = r.connected_time
            device.connect_time = (r.connect_ended - r.connect_started) * 1000

        if r.services_retrieved:
            for uuid, num_char in r.services_retrieved:
                service = db_session.query(Service).get(uuid)
                if not service:
                    service = Service(uuid=uuid, characteristics=num_char)
                    db_session.add(service)
                if not service.characteristics:
                    service.characteristics = num_char

                device.services.append(service)

        if r.device_id:
            device.device_id = r.device_id

        if r.public:
            device.public = r.public

        if r.inquiry_ended:
            device.inquiry_time = (r.inquiry_ended - r.connect_ended) * 1000


def init_alchemy(db_url):
    db_engine = create_engine(db_url)
    Base.metadata.create_all(db_engine)
    return sessionmaker(bind=db_engine)()


if __name__ == "__main__":
    import logging
    import atexit

    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)-8ls %(levelname)-8s %(mac)-17s %(message)s',
                        datefmt='%H:%M:%S')

    db = init_alchemy('sqlite:///survey.db')
    ble = ble_socket()
    results = Queue()

    start_discovery(ble)
    listener, reports = start_listener(ble)
    connector, missing = start_connector(results)

    atexit.register(stop_discovery, ble)

    while True:
        try:
            obj = results.get(timeout=2.0)
            results.put(obj)
            process_connections(db, results)
        except Empty:
            process_reports(db, reports, missing)
            if not connector.is_alive() or not listener.is_alive():
                log.error("Bluetooth threads have died. Exiting.", extra={'mac': NO_MAC})
                atexit.unregister(stop_discovery)
                db.close()
                from sys import exit
                exit(8)
                break

    # GLib.io_add_watch(results._reader.fileno(), GLib.IO_IN, process_connections, db, results)
    # GLib.timeout_add(2000, process_reports, db, reports, missing)
    # GLib.MainLoop().run()
