from __future__ import annotations

import logging
import time

from bluepy.btle import BTLEDisconnectError, Peripheral

from labelle.lib.devices.labeler_device import LabelerDevice

LOG = logging.getLogger(__name__)


class BluetoothDeviceError(RuntimeError):
    pass


class BluetoothDevice(LabelerDevice):
    def __init__(
        self,
        name: str,
        address: str,
        device_id: str,
        characteristic_uuid: str,
        service_uuid: str,
        height_px: int,
        labeler_margin_px: int,
    ):
        super().__init__(name, address, device_id, height_px, labeler_margin_px)
        self._peripheral = None
        self._characteristic = None
        self._characteristic_uuid = characteristic_uuid
        self._service_uuid = service_uuid

    @property
    def name(self) -> str:
        return self._name or self._address

    @property
    def hash(self) -> str:
        return self._address

    @property
    def device_info(self) -> str:
        return f"Bluetooth Device: {self.name} ({self._address})"

    def is_connected(self) -> bool:
        try:
            self._peripheral.getServices()
            return True
        except BTLEDisconnectError:
            return False

    def send_data(self, data: bytes, retries=5, delay=2) -> None:
        if not self.is_connected():
            raise RuntimeError("Not connected to device")
        for i in range(retries):
            try:
                for j in range(0, len(data), 96):
                    chunk = data[j:j + 96]
                    self._characteristic.write(chunk, withResponse=False)
                    time.sleep(0.03)
                return
            except BTLEDisconnectError as e:
                LOG.warning(f"Send data attempt {i+1}/{retries} failed: {e}")
                if i < retries - 1:
                    self.connect()
                    time.sleep(delay)
                else:
                    LOG.error("Could not send data. Printer disconnected.")
                    raise
            except Exception as e:
                LOG.error(f"Unexpected error: {e}")
                time.sleep(delay)

    def connect(self, retries=5, delay=2) -> None:
        for i in range(retries):
            try:
                LOG.debug(f"Connecting to {self._address} (attempt {i+1}/{retries})...")
                self._peripheral = Peripheral(self._address)
                self._peripheral.setMTU(100)  # Set MTU to a larger size for better throughput
                self._characteristic = self._peripheral.getCharacteristics(uuid=self._characteristic_uuid)[0]
                LOG.debug(f"Connected to {self.name}")
                return
            except BTLEDisconnectError as e:
                LOG.warning(f"Connection attempt {i+1}/{retries} failed: {e}")
                if i < retries - 1:
                    time.sleep(delay)
                else:
                    LOG.error("Could not connect. Make sure the printer is in BLE mode (blue light).")
                    raise
            except Exception as e:
                LOG.error(f"Unexpected error: {e}")
                time.sleep(delay)

    def disconnect(self) -> None:
        if self._peripheral:
            try:
                self._peripheral.disconnect()
                LOG.debug("Disconnected from %s", self.name)
            except Exception as e:
                LOG.error("Failed to disconnect from %s: %s", self.name, e)
            finally:
                self._peripheral = None
                self._characteristic = None

    @property
    def peripheral(self) -> Peripheral:
        if not self._peripheral:  # type: ignore
            raise BluetoothDeviceError("Not connected to a peripheral.")
        return self._peripheral