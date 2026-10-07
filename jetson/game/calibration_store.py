"""Validated, atomic camera geometry updates shared with the detector."""
import copy
import json
import os
from pathlib import Path
import threading
from . import geometry


class CalibrationConflict(ValueError):
    pass


class CalibrationStore:
    def __init__(self, path):
        self.path = Path(path)
        self.lock = threading.Lock()
        self.config = geometry.load(self.path) if self.path.exists() else None
        self.revision = 1 if self.config else 0

    def snapshot(self):
        with self.lock:
            return dict(config=copy.deepcopy(self.config), revision=self.revision)

    def save(self, config, expected_revision, width, height):
        if config is None:
            with self.lock:
                if type(expected_revision) is not int or expected_revision != self.revision:
                    raise CalibrationConflict('설정이 변경됐습니다. 새로 불러오세요.')
                if self.path.exists():
                    self.path.unlink()
                self.config = None
                self.revision += 1
                return dict(config=None,revision=self.revision)
        geometry.validate(config)
        geometry.check_size(config, width, height)
        # Persist known fields only; never accept file paths from browsers.
        config = copy.deepcopy({key:config[key] for key in
            ('schema_version','reference_size','roi','finish_line','finish_direction_point')})
        with self.lock:
            if type(expected_revision) is not int or expected_revision != self.revision:
                raise CalibrationConflict('설정이 다른 화면에서 변경됐습니다. 새로 불러오세요.')
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix('.tmp')
            try:
                with temporary.open('w', encoding='utf-8') as file:
                    json.dump(config, file, ensure_ascii=False)
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(str(temporary), str(self.path))
            finally:
                if temporary.exists():
                    temporary.unlink()
            self.config = config
            self.revision += 1
            return dict(config=copy.deepcopy(config), revision=self.revision)
