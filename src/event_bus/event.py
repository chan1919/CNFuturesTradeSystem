from enum import Enum


class EventType(Enum):
    """行情/交易事件类型枚举"""

    # 系统事件
    SYSTEM = "system"

    # 行情服务器事件
    MD_CONNECTED = "md.connected"
    MD_DISCONNECTED = "md.disconnected"
    MD_LOGIN = "md.login"

    # 交易服务器事件
    TD_CONNECTED = "td.connected"
    TD_DISCONNECTED = "td.disconnected"
    TD_LOGIN = "td.login"
    TD_AUTHENTICATE = "td.authenticate"

    # 业务数据事件（由服务器主动推送）
    TICK = "tick"
    ORDER = "order"
    TRADE = "trade"
    POSITION = "position"
    ACCOUNT = "account"

    # 订单操作事件
    ORDER_INSERT = "order.insert"

    # 查询结果事件（由查询请求触发）
    QRV_ORDER = "qry.order"
    QRV_TRADE = "qry.trade"
    QRV_POSITION = "qry.position"
    QRV_ACCOUNT = "qry.account"
    QRV_INSTRUMENT = "qry.instrument"

    # 结算单事件
    SETTLEMENT_INFO = "settlement.info"
    SETTLEMENT_INFO_CONFIRMED = "settlement.confirmed"


class Event:
    def __init__(self, type: EventType | str, data: dict = None):
        self.type = type
        self.data = data
