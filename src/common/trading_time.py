from datetime import datetime, time


DAY_START = time(8, 56)
DAY_END = time(15, 1)

NIGHT_START = time(20, 56)
NIGHT_END = time(2, 45)


def in_connection_window(now: datetime) -> bool:
    current_time = now.time()
    weekday = now.weekday()

    if weekday == 0 and current_time <= NIGHT_END:
        return False

    if 0 <= weekday <= 4 and DAY_START <= current_time <= DAY_END:
        return True

    if 0 <= weekday <= 3 and (current_time >= NIGHT_START or current_time <= NIGHT_END):
        return True

    if weekday == 4 and (current_time >= NIGHT_START or current_time <= NIGHT_END):
        return True
    if weekday == 5 and current_time <= NIGHT_END:
        return True

    return False


def session_label(now: datetime) -> str | None:
    if not in_connection_window(now):
        return None

    current_time = now.time()
    if DAY_START <= current_time <= DAY_END:
        return "day"
    return "night"
