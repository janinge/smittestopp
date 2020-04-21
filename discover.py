from typing import Any, Iterator

from scapy.layers.bluetooth import *
from itertools import chain
from uuid import UUID
from time import sleep
from queue import Queue, Empty
from threading import Thread

from logging import getLogger
log = getLogger(__name__)

SMITTE_UUID = {UUID('e45c1747-a0a4-44ab-8c06-a956df58d93a'),
               UUID('64b81e3c-d60c-4f08-8396-9351b04f7591')}


def adverts_received(adverts, result_queue):
    reports = chain.from_iterable(a[HCI_LE_Meta_Advertising_Reports].reports for a in adverts)

    for report in reports:
        if not report:
            continue

        if EIR_CompleteList128BitServiceUUIDs in report and \
                SMITTE_UUID & set(report[EIR_CompleteList128BitServiceUUIDs].svc_uuids):
            result_queue.put(report)


def start_listener(hcisocket):
    report_queue = Queue()

    thread = Thread(target=lambda queue: hcisocket.sniff(prn=lambda a: adverts_received(a, queue),
                                                         lfilter=lambda p: HCI_LE_Meta_Advertising_Reports in p),
                    daemon=True, args=(report_queue,))
    thread.start()

    return thread, report_queue


def start_discovery(hcisocket):
    hcisocket.sr(HCI_Hdr() / HCI_Command_Hdr() / HCI_Cmd_LE_Set_Scan_Enable(enable=True, filter_dups=False))


def stop_discovery(hcisocket):
    hcisocket.sr(HCI_Hdr() / HCI_Command_Hdr() / HCI_Cmd_LE_Set_Scan_Enable(enable=False))


def ble_socket():
    return BluetoothHCISocket(0)
