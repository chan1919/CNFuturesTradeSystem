from trader.common.exchange import Exchange, CZCE_EXCHANGES, FOUR_DIGIT_EXCHANGES


# ---- 合约代码转换工具函数 ----

def _split_instrument_id(instrument_id):
    """将合约代码拆分为字母部分和数字部分"""
    alpha = ""
    digits = ""
    for ch in instrument_id:
        if ch.isdigit():
            digits += ch
        else:
            alpha += ch
    return alpha, digits


def ctp_to_standard(instrument_id: str, exchange: Exchange) -> str:
    """CTP 原始合约代码 → 统一标准格式

    标准格式: 大写字母产品代码 + 4位数字年份月份
    例如: rb2510 → RB2510,  CF609 → CF2609
    """
    if exchange in CZCE_EXCHANGES:
        alpha, digits = _split_instrument_id(instrument_id)
        if len(digits) == 3:
            year_char = digits[0]
            month = digits[1:3]
            return f"{alpha}2{year_char}{month}"
        return instrument_id
    return instrument_id.upper()


def standard_to_ctp(symbol: str, exchange: Exchange) -> str:
    """统一标准格式 → CTP 原始合约代码（下单时使用）

    与 ctp_to_standard 相反操作。
    """
    if exchange in CZCE_EXCHANGES:
        alpha, digits = _split_instrument_id(symbol)
        if len(digits) == 4 and digits[0] == "2":
            return f"{alpha}{digits[1:]}"
        return symbol
    elif exchange == Exchange.CFFEX:
        return symbol
    return symbol.lower()


# ---- Contract 类 ----

class Contract:
    """统一合约模型

    内部统一使用"大写字母产品代码 + 4位数字"格式，
    向下单/查询时需要调用 to_ctp() 转为 CTP 原始格式。

    属性:
        symbol:     标准格式，如 RB2510, CF2609, IF2601
        ctp_id:     CTP 原始格式，如 rb2510, CF609, IF2601
        exchange:   所属交易所
        product_id: 产品代码，如 RB, M, CF
        year:       年份后两位，如 25, 26
        month:      月份 1~12
        year_month: 年份+月份，如 "2510", "2609"
    """

    CZCE_EXCHANGES = CZCE_EXCHANGES

    def __init__(self, symbol: str, ctp_id: str, exchange: Exchange, product_id: str, year: int, month: int):
        self.symbol = symbol
        self.ctp_id = ctp_id
        self.exchange = exchange
        self.product_id = product_id
        self.year = year
        self.month = month
        self.year_month = f"{year:02d}{month:02d}"

    @classmethod
    def from_ctp(cls, instrument_id: str, exchange: Exchange) -> "Contract":
        """从 CTP 回报数据构造合约实例

        自动识别年份格式并补全为标准格式。
        """
        if exchange not in Exchange.__members__.values():
            raise ValueError(f"不支持的交易所: {exchange}")

        ctp_id = instrument_id
        symbol = ctp_to_standard(instrument_id, exchange)
        product_id, digits = _split_instrument_id(symbol)

        if exchange in CZCE_EXCHANGES:
            raw_digits = _split_instrument_id(instrument_id)[1]
            if len(raw_digits) == 3:
                year = int("2" + raw_digits[0])
                month = int(raw_digits[1:3])
            else:
                year = int(digits[:2])
                month = int(digits[2:4])
        else:
            year = int(digits[:2])
            month = int(digits[2:4])

        return cls(
            symbol=symbol,
            ctp_id=ctp_id,
            exchange=exchange,
            product_id=product_id,
            year=year,
            month=month,
        )

    def to_ctp(self) -> str:
        """返回 CTP 下单可用的原始合约代码"""
        return standard_to_ctp(self.symbol, self.exchange)

    def __repr__(self):
        return f"<Contract {self.symbol} {self.exchange.value}>"

    def __str__(self):
        return self.symbol

    def __eq__(self, other):
        if not isinstance(other, Contract):
            return NotImplemented
        return self.symbol == other.symbol and self.exchange == other.exchange

    def __hash__(self):
        return hash((self.symbol, self.exchange))