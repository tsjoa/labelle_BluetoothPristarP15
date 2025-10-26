from __future__ import annotations

import array
import logging
import math
import time

from bluepy.btle import BTLEDisconnectError
from matplotlib import font_manager
from PIL import Image, ImageDraw, ImageFont

from labelle.lib.devices.bluetooth_device import BluetoothDevice, BluetoothDeviceError
from labelle.lib.devices.labeler_device import LabelerDevice
from labelle.lib.constants import PIXELS_PER_MM

LOG = logging.getLogger(__name__)

SERVICE_UUID = "0000ff00-0000-1000-8000-00805f9b34fb"
CHAR_UUID = "0000ff02-0000-1000-8000-00805f9b34fb"


class PristarP15LabelerError(RuntimeError):
    pass


class PristarP15Labeler(BluetoothDevice):
    # Pristar P15 uses 12mm tape width
    DEFAULT_TAPE_SIZE_MM = 12
    SUPPORTED_TAPE_SIZES_MM = (12,)
    minimum_horizontal_margin_mm = 8.1  # Default value, adjust if needed

    @property
    def height_px(self) -> int:
        return 96

    @property
    def is_ready(self) -> bool:
        return self.is_connected()

    @property
    def tape_size_mm(self) -> int:
        return self._tape_size_mm

    @tape_size_mm.setter
    def tape_size_mm(self, value: int) -> None:
        if value not in self.SUPPORTED_TAPE_SIZES_MM:
            raise ValueError(f"Unsupported tape size: {value}mm")
        self._tape_size_mm = value

    @property
    def labeler_margin_px(self) -> int:
        return self._labeler_margin_px

    def __init__(
        self,
        address: str,
        name: str | None = None,
        tape_size_mm: int | None = None,
    ):
        super().__init__(
            name=name or "Pristar P15",
            address=address,
            device_id="p15",
            characteristic_uuid=CHAR_UUID,
            service_uuid=SERVICE_UUID,
            height_px=self.height_px,
            labeler_margin_px=(0.0, 0.0),
        )
        self._tape_size_mm = tape_size_mm or self.DEFAULT_TAPE_SIZE_MM

    def _bitmap_to_packet(self, bitmap):
        """Converts a PIL image to the printer's packet format."""
        width, height = bitmap.size
        bytes_ = []
        for x in range(width):
            for y_byte_group in range(height - 8, -1, -8):
                byte = 0
                for bit in range(8):
                    px_y = y_byte_group + bit
                    if 0 <= px_y < height and bitmap.getpixel((x, px_y)) == 0:
                        byte |= (1 << bit)
                bytes_.append(byte)
        return bytes(bytes_)

    def print(self, bitmap: Image.Image, segmented_paper=False):
        """Sends the print job to a connected printer with proper paper advance."""
        payload = self._bitmap_to_packet(bitmap)
        canvas_width = bitmap.width

        try:
            char = self._peripheral.getCharacteristics(uuid=CHAR_UUID)[0]

            # Build packets
            packets = [
                bytes([0x10, 0xff, 0x40]),  # init command
                bytes(
                    [
                        *([0x00] * 15),
                        0x10,
                        0xff,
                        0xf1,
                        0x02,
                        0x1d,
                        0x76,
                        0x30,
                        0x00,
                        0x0c,
                        0x00,
                        canvas_width & 0xFF,
                        (canvas_width >> 8) & 0xFF,
                    ]
                ),
                payload,
            ]

            # Add line feeds to advance paper
            packets.append(bytes([0x0A] * 5))  # feed 5 lines

            if segmented_paper:
                packets.extend(
                    [
                        bytes([0x1D, 0x0C, 0x10]),
                        bytes([0xFF, 0xF1, 0x45]),
                        bytes([0x10, 0xFF, 0x40]),
                        bytes([0x10, 0xFF, 0x40]),
                    ]
                )
            else:
                packets.extend([bytes([0x10, 0xFF, 0xF1, 0x45])])

            # Send packets
            for p in packets:
                self.send_data(p)

            LOG.info("Print successful!")
            return True
        except BTLEDisconnectError as e:
            raise PristarP15LabelerError("Printer disconnected unexpectedly.") from e
        except Exception as e:
            raise PristarP15LabelerError(f"Print error: {e}") from e