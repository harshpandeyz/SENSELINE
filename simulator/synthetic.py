"""Reproducible, hardware-free sensor frames and measurement records."""
from dataclasses import dataclass
import random

SUPPORTED_WIDTHS=(8,16,24,32)
UINT32_MODULUS=1<<32


@dataclass(frozen=True)
class SyntheticMeasurement:
    timestamp_ms: int
    sequence: int
    count: int
    frame_hex: str
    unit: str

    def as_dict(self):
        return {"timestamp_ms":self.timestamp_ms,"sequence":self.sequence,"count":self.count,"frame_hex":self.frame_hex,"unit":self.unit}


def encode_register_count(count: int, width_bits: int, byte_order: str="big", signed: bool=True) -> str:
    if width_bits not in SUPPORTED_WIDTHS: raise ValueError("width_bits must be 8, 16, 24, or 32")
    if byte_order not in ("big","little"): raise ValueError("byte_order must be big or little")
    if not isinstance(signed,bool): raise ValueError("signed must be boolean")
    if isinstance(count,bool) or not isinstance(count,int): raise ValueError("count must be an integer")
    encoded=count.to_bytes(width_bits//8,byte_order,signed=signed)
    return encoded.hex()


def generate_measurements(seed: int, count: int, *, start_timestamp_ms: int=1_800_000_000_000, interval_ms: int=1000, width_bits: int=16, byte_order: str="big", signed: bool=True, unit: str="C") -> list[dict]:
    """Create reproducible synthetic temperature-like measurements.

    Values are random integer register counts in a conservative fraction of the
    signed/unsigned range. Sequence values deliberately cross uint32 rollover
    when the starting sequence is chosen near its modulus.
    """
    if isinstance(seed,bool) or not isinstance(seed,int): raise ValueError("seed must be integer")
    if isinstance(count,bool) or not isinstance(count,int) or count<0: raise ValueError("count must be a nonnegative integer")
    if isinstance(start_timestamp_ms,bool) or not isinstance(start_timestamp_ms,int) or start_timestamp_ms<0: raise ValueError("start timestamp must be nonnegative milliseconds")
    if isinstance(interval_ms,bool) or not isinstance(interval_ms,int) or interval_ms<0: raise ValueError("interval must be nonnegative milliseconds")
    if width_bits not in SUPPORTED_WIDTHS: raise ValueError("width_bits must be 8, 16, 24, or 32")
    if byte_order not in ("big","little"): raise ValueError("byte_order must be big or little")
    if not isinstance(signed,bool): raise ValueError("signed must be boolean")
    rng=random.Random(seed)
    magnitude=(1<<(width_bits-(1 if signed else 0)))-1
    bound=max(1,min(magnitude,10000))
    seq_start=UINT32_MODULUS-2
    rows=[]
    for index in range(count):
        value=rng.randint(-bound,bound) if signed else rng.randint(0,bound)
        rows.append(SyntheticMeasurement(start_timestamp_ms+index*interval_ms,(seq_start+index)%UINT32_MODULUS,value,encode_register_count(value,width_bits,byte_order,signed),unit).as_dict())
    return rows
