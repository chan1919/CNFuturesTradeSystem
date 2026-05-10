from enum import Enum


class Exchange(Enum):
    """交易所枚举

    每一条对应一个国内期货交易所的简称与官方代码。
    """

    # 上海期货交易所（上期所）
    # 产品代码示例: rb(螺纹钢), cu(铜), au(黄金), ag(白银)
    SHFE = "SHFE"

    # 大连商品交易所（大商所）
    # 产品代码示例: m(豆粕), i(铁矿石), jd(鸡蛋), p(棕榈油)
    DCE = "DCE"

    # 郑州商品交易所（郑商所）
    # 产品代码示例: CF(棉花), SR(白糖), TA(PTA), MA(甲醇)
    # 注意：CTP 合约代码只有 1 位年份 + 2 位月份 = 共 3 位，全大写
    CZCE = "CZCE"

    # 中国金融期货交易所（中金所）
    # 产品代码示例: IF(沪深300), IC(中证500), T(国债)
    CFFEX = "CFFEX"

    # 上海国际能源交易中心（能源中心）
    # 产品代码示例: sc(原油), nr(20号胶), lu(低硫燃料油)
    INE = "INE"

    # 广州期货交易所（广期所）
    # 产品代码示例: si(工业硅), lc(碳酸锂)
    GFEX = "GFEX"


# ---- 交易所分组常量 ----

CZCE_EXCHANGES = {Exchange.CZCE}
"""郑商所集合，用于判断是否需要特殊的 3 位年份转换"""

FOUR_DIGIT_EXCHANGES = {Exchange.SHFE, Exchange.DCE, Exchange.CFFEX, Exchange.INE, Exchange.GFEX}
"""使用标准 4 位年份月份的交易所集合"""