"""Small value types shared by native equations and JS image rendering."""
from dataclasses import dataclass

MAX_SOURCE = 16000


class FormulaError(ValueError):
    """A formula cannot be converted faithfully by a local backend."""


@dataclass(frozen=True)
class FormulaImage:
    data: bytes
    width_pt: float
    height_pt: float
    depth_pt: float
