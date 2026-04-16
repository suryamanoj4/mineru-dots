# Copyright (c) Opendatalab. All rights reserved.

import sys

from vparse.exceptions import BackendError, ConfigurationError, InputError, ProcessingError


class FileNotExisted(InputError):

    def __init__(self, path):
        self.path = path

    def __str__(self):
        return f'File {self.path} does not exist.'


class InvalidConfig(ConfigurationError):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f'Invalid config: {self.msg}'


class InvalidParams(InputError):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f'Invalid params: {self.msg}'


class EmptyData(ProcessingError):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f'Empty data: {self.msg}'

class CUDA_NOT_AVAILABLE(BackendError):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return f'CUDA not available: {self.msg}'


__all__ = [
    "FileNotExisted",
    "InvalidConfig",
    "InvalidParams",
    "EmptyData",
    "CUDA_NOT_AVAILABLE",
]


_module = sys.modules[__name__]
sys.modules.setdefault("vparse.data.utils.exceptions", _module)
sys.modules.setdefault("mineru.data.utils.exceptions", _module)
