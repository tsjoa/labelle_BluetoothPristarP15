from __future__ import annotations

import logging

from usb.core import NoBackendError, USBError

from labelle.lib.devices.labeler_device import LabelerDevice
from labelle.lib.devices.pristar_p15 import PristarP15Labeler
from labelle.lib.devices.usb_device import UsbDevice

LOG = logging.getLogger(__name__)
POSSIBLE_USB_ERRORS = (NoBackendError, USBError)


class DeviceManagerError(RuntimeError):
    pass


class DeviceManagerNoDevices(DeviceManagerError):
    def __init__(self, message: str = "No supported devices found"):
        super().__init__(message)


class DeviceManager:
    _devices: dict[str, LabelerDevice]

    def __init__(self) -> None:
        self._devices = {}

    def scan(self) -> bool:
        prev = self._devices
        cur: dict[str, LabelerDevice] = {}
        try:
            for dev in UsbDevice.supported_devices():
                if dev.hash:
                    cur[dev.hash] = dev
        except POSSIBLE_USB_ERRORS as e:
            LOG.warning(f"Failed scanning USB devices: {e}")

        # Add Pristar P15 Bluetooth printer (hardcoded for now)
        pristar_p15_address = "03:0D:7A:D6:5E:B1"  # From newprint5_withfeed.py
        pristar_p15 = PristarP15Labeler(address=pristar_p15_address, name="Pristar P15")
        cur[pristar_p15.hash] = pristar_p15

        if len(cur) == 0:
            self._devices.clear()
            raise DeviceManagerNoDevices("No supported devices found")

        prev_set = set(prev)
        cur_set = set(cur)

        for dev_hash in prev_set - cur_set:
            self._devices.pop(dev_hash)
        for dev_hash in cur_set - prev_set:
            self._devices[dev_hash] = cur[dev_hash]

        changed = prev_set != cur_set
        return changed

    @property
    def devices(self) -> list[LabelerDevice]:
        try:
            return sorted(self._devices.values(), key=lambda dev: dev.hash)
        except POSSIBLE_USB_ERRORS:
            return []

    def matching_devices(self, patterns: list[str] | None) -> list[LabelerDevice]:
        try:
            matching = filter(
                lambda dev: dev.is_match(patterns), self._devices.values()
            )
            return sorted(matching, key=lambda dev: dev.hash)
        except POSSIBLE_USB_ERRORS:
            return []

    def find_and_select_device(self, patterns: list[str] | None = None) -> LabelerDevice:
        devices = [
            device for device in self.matching_devices(patterns)
        ]
        if len(devices) == 0:
            raise DeviceManagerError("No matching devices found")
        if len(devices) > 1:
            LOG.debug("Found multiple matching devices. Using first device")
        else:
            LOG.debug("Found single device")
        for dev in devices:
            LOG.debug(dev.device_info)
        dev = devices[0]
        LOG.debug(f"Recognized device as {dev.name}")
        return dev
