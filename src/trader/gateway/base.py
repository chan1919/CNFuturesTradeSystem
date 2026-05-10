"""网关基类，定义通用接口"""
from abc import ABC, abstractmethod


class GatewayStatus:
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LOGINED = "logined"


class BaseGateway(ABC):
    def __init__(self):
        self._status = GatewayStatus.DISCONNECTED

    @property
    def status(self) -> str:
        return self._status

    @status.setter
    def status(self, value: str):
        self._status = value

    @abstractmethod
    def connect(self):
        ...

    @abstractmethod
    def close(self):
        ...

    @abstractmethod
    def login(self):
        ...