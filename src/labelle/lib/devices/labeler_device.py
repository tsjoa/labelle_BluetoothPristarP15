from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image


class LabelerDevice(ABC):
    """Abstract base class for all labeler devices."""

    def __init__(
        self,
        name: str,
        address: str,
        device_id: str,
        height_px: int,
        labeler_margin_px: int,
    ):
        self._name = name
        self._address = address
        self._device_id = device_id
        self._height_px = height_px
        self._labeler_margin_px = labeler_margin_px

    @property
    @abstractmethod
    def is_ready(self) -> bool:
        """Return True if the device is ready to print."""
        pass

    @abstractmethod
    def print(self, bitmap: Image.Image) -> None:
        """Print a label bitmap to the device."""
        pass

    @property
    @abstractmethod
    def tape_size_mm(self) -> int:
        """Return the tape size in mm."""
        pass

    @property
    @abstractmethod
    def height_px(self) -> int:
        """Return the height of the tape in pixels."""
        pass

    @property
    @abstractmethod
    def device_info(self) -> str:
        """Return a string with device information."""
        pass

    @property
    @abstractmethod
    def hash(self) -> str:
        """Return a unique hash for the device."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the device."""
        pass

    @abstractmethod
    def connect(self) -> None:
        """Connect to the device."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect from the device."""
        pass

    def is_match(self, patterns: list[str] | None) -> bool:
        if patterns is None:
            return True
        match = True
        for pattern in patterns:
            pattern = pattern.lower()
            match &= pattern in self.name.lower()
        return match
