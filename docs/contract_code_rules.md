# 中国期货合约代码命名规则

## 一、各交易所代码格式

| 交易所 | 简称 | CTP InstrumentID 格式 | 年份位数 | 大小写 | 正例 |
|--------|------|----------------------|---------|--------|------|
| 上海期货交易所 | SHFE | ProductCode + YYMM | 4位 | 小写 | `rb2510` |
| 大连商品交易所 | DCE | ProductCode + YYMM | 4位 | 小写 | `m2609` |
| 郑州商品交易所 | CZCE | ProductCode + YMM | **3位** | **大写** | `CF609` |
| 中国金融期货交易所 | CFFEX | ProductCode + YYMM | 4位 | 大写 | `IF2601` |
| 上海国际能源交易中心 | INE | ProductCode + YYMM | 4位 | 小写 | `sc2609` |
| 广州期货交易所 | GFEX | ProductCode + YYMM | 4位 | 小写 | `si2609` |

## 二、本项目合约模型

本项目使用 CTP 原生合约代码（`instrument_id`），不做任何格式转换。

```python
from src.common.contract import Contract
from src.common.exchange import Exchange

# CTP 原始代码直接传入
c = Contract.from_ctp("rb2510", Exchange.SHFE)
c.instrument_id  # "rb2510"
c.exchange       # Exchange.SHFE
c.product_id     # "rb"
c.year_month     # "2510"
c.year           # 25
c.month          # 10

# CZCE 3 位代码也原生支持
c = Contract.from_ctp("CF609", Exchange.CZCE)
c.instrument_id  # "CF609"
c.product_id     # "CF"
c.year_month     # "2609"
c.year           # 26
c.month          # 9
```

## 三、Contract 类字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `instrument_id` | str | CTP 原生格式（如 `rb2510`、`CF609`） |
| `exchange` | Exchange | 交易所枚举 |
| `product_id` | str | 产品代码（如 `rb`、`CF`、`IF`） |
| `year` | int | 年份后两位（CZCE 3 位自动拼接 `2` 前缀） |
| `month` | int | 月份 1~12 |
| `year_month` | str | 4 位年月（如 `2510`、`2609`） |

## 四、各交易所 Product Code 列表

### SHFE 上海期货交易所
`rb` 螺纹钢, `cu` 铜, `al` 铝, `au` 黄金, `ag` 白银, `hc` 热轧卷板, `ru` 天然橡胶, `bu` 沥青, `sp` 纸浆, `fu` 燃料油, `ss` 不锈钢, `ni` 镍, `sn` 锡, `pb` 铅, `zn` 锌, `wr` 线材

### DCE 大连商品交易所
`m` 豆粕, `y` 豆油, `c` 玉米, `a` 豆一, `b` 豆二, `p` 棕榈油, `i` 铁矿石, `j` 焦炭, `jm` 焦煤, `jd` 鸡蛋, `l` 聚乙烯, `v` 聚氯乙烯, `pp` 聚丙烯, `eg` 乙二醇, `eb` 苯乙烯, `pg` 液化石油气, `lh` 生猪, `rr` 粳米

### CZCE 郑州商品交易所（产品代码大写）
`CF` 棉花, `SR` 白糖, `TA` PTA, `MA` 甲醇, `OI` 菜籽油, `FG` 玻璃, `RM` 菜粕, `ZC` 动力煤, `SA` 纯碱, `PF` 短纤, `UR` 尿素, `PK` 花生, `AP` 苹果, `CJ` 红枣, `SH` 烧碱, `SF` 硅铁, `SM` 锰硅

### CFFEX 中国金融期货交易所（产品代码大写）
`IF` 沪深300股指, `IC` 中证500股指, `IH` 上证50股指, `IM` 中证1000股指, `T` 30年期国债, `TF` 5年期国债, `TS` 2年期国债, `TL` 10年期国债

### INE 上海国际能源交易中心
`sc` 原油, `nr` 20号胶, `lu` 低硫燃料油, `bc` 国际铜, `ec` 欧线集运

### GFEX 广州期货交易所
`si` 工业硅, `lc` 碳酸锂