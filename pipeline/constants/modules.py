import importlib


class LazyModule:
    def __init__(self, module_path: str):
        self.module_path = module_path
        self.module = None

    def _load(self):
        if self.module is None:
            self.module = importlib.import_module(self.module_path)
        return self.module

    def __getattr__(self, name):
        return getattr(self._load(), name)


DOWNLOAD_YELLOW_TRIPDATA = LazyModule("pipeline.taxi.etl.01_download_yellow_tripdata")
ETL02_INGEST = LazyModule("pipeline.taxi.etl.02_ingest_data")
ETL03_BUSINESS = LazyModule("pipeline.taxi.etl.03_apply_business_rules")
ETL04_UPPER_BOUNDS = LazyModule("pipeline.taxi.etl.04_apply_upper_bounds")
WEATHER01_DOWNLOAD = LazyModule("pipeline.weather.etl.01_download_weather")
WEATHER02_INGEST = LazyModule("pipeline.weather.etl.02_ingest_data")
WEATHER03_BUSINESS = LazyModule("pipeline.weather.etl.03_apply_business_rules")
