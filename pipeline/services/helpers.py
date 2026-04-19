import math
from numbers import Integral, Real
from pathlib import Path


def extract_month(path: Path) -> int:
    name = path.stem # e.g. yellow_tripdata_2019-01 from path/to/yellow_tripdata_2019-01.parquet
    month_str = name.split("-")[-1] # e.g. 01 from yellow_tripdata_2019-01
    return int(month_str) # e.g. 1 from 01


def percent(part: int, total: int, digits: int = 5) -> float:
    if total == 0:
        return 0.0
    return round(part / total * 100, digits)


def round_if_needed(value, digits: int = 2):
    if isinstance(value, float):
        rounded_value = round(value, digits)
        if rounded_value != value:
            return rounded_value
    return value


def serialize_number(value, digits: int = 2):
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, Real):
        as_float = float(value)
        if math.isinf(as_float) or math.isnan(as_float):
            return None
        return round_if_needed(as_float, digits=digits)
    return value


def normalize_type_name(type_name: str) -> str:
    return (type_name or "").strip().lower().replace(" ", "")

