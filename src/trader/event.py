from enum import Enum


class EventType(str, Enum):
    """行情/交易事件类型枚举"""

    # 系统事件
    SYSTEM = "system"

    # 行情服务器事件
    MD_CONNECTED = "md.connected"          # 行情服务器连接成功
    MD_DISCONNECTED = "md.disconnected"    # 行情服务器断开
    MD_LOGIN = "md.login"                  # 行情服务器登录完成

    # 交易服务器事件
    TD_CONNECTED = "td.connected"          # 交易服务器连接成功
    TD_DISCONNECTED = "td.disconnected"    # 交易服务器断开
    TD_LOGIN = "td.login"                  # 交易服务器登录完成
    TD_AUTHENTICATE = "td.authenticate"    # 交易服务器认证结果

    # 业务数据事件（由服务器主动推送）
    TICK = "tick"                          # Tick 行情数据
    ORDER = "order"                        # 委托单状态更新
    TRADE = "trade"                        # 成交回报
    POSITION = "position"                  # 持仓更新
    ACCOUNT = "account"                    # 账户资金更新

    # 查询结果事件（由查询请求触发）
    QRV_ORDER = "qry.order"                # 委托单查询结果
    QRV_TRADE = "qry.trade"                # 成交查询结果
    QRV_POSITION = "qry.position"          # 持仓查询结果
    QRV_ACCOUNT = "qry.account"            # 账户资金查询结果
    QRV_INSTRUMENT = "qry.instrument"      # 合约信息查询结果

    # 结算单事件
    SETTLEMENT_INFO = "settlement.info"             # 结算单信息
    SETTLEMENT_INFO_CONFIRMED = "settlement.confirmed"  # 结算单确认结果


class Event:
    def __init__(self, type: EventType, data: dict = None):
        self.type = type
        self.data = data