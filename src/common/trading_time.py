from datetime import datetime, time


DAY_START = time(8, 56)
DAY_END = time(15, 1)

NIGHT_START = time(20, 56)
NIGHT_END = time(2, 45)


def in_connection_window(now: datetime) -> bool:
    t = now.time()
    w = now.weekday()

    # 日盘：周一~五 8:56–15:01
    if 0 <= w <= 4 and DAY_START <= t <= DAY_END:
        return True

    # 夜盘 20:56–23:59：周日~四晚（周一~五日盘前一天晚）
    if t >= NIGHT_START:
        return w <= 4

    # 夜盘 0:00–2:45：周二~六凌晨（周一凌晨排除，那是周日夜盘尾巴）
    if t <= NIGHT_END:
        return 1 <= w <= 5

    return False


def session_label(now: datetime) -> str | None:
    if not in_connection_window(now):
        return None

    current_time = now.time()
    if DAY_START <= current_time <= DAY_END:
        return "day"
    return "night"
