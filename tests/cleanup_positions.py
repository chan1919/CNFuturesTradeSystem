"""Check and close leftover positions from test runs"""
import sys
import os
import time
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from trader.engine import EventEngine
from trader.event import EventType
from trader.gateway.td_gateway import TdGateway
from trader.gateway.md_gateway import MdGateway


def main():
    load_dotenv(".env.local")
    cfg = {
        "user_id": os.environ["CTP_USER_ID"],
        "password": os.environ["CTP_PASSWORD"],
        "broker_id": os.environ["CTP_BROKER_ID"],
        "td_front": os.environ["CTP_TD_FRONT"],
        "md_front": os.environ["CTP_MD_FRONT"],
        "app_id": os.environ["CTP_APP_ID"],
        "auth_code": os.environ["CTP_AUTH_CODE"],
    }

    engine = EventEngine()
    td = TdGateway(
        engine,
        front_url=cfg["td_front"],
        broker_id=cfg["broker_id"],
        user_id=cfg["user_id"],
        password=cfg["password"],
        app_id=cfg["app_id"],
        auth_code=cfg["auth_code"],
    )
    md = MdGateway(
        engine,
        front_url=cfg["md_front"],
        broker_id=cfg["broker_id"],
        user_id=cfg["user_id"],
        password=cfg["password"],
    )

    results = []
    engine.register(EventType.TD_LOGIN, lambda e: results.append(("login", e.data)))
    engine.register(EventType.POSITION, lambda e: results.append(("position", e.data)))
    engine.register(EventType.TRADE, lambda e: results.append(("trade", e.data)))
    engine.register(EventType.ORDER, lambda e: results.append(("order", e.data)))
    engine.register(EventType.TICK, lambda e: results.append(("tick", e.data)))

    td.connect()
    deadline = time.time() + 30
    while time.time() < deadline:
        engine.process_one()
        if any(r[0] == "login" and r[1].get("error_id") == 0 for r in results):
            break
        time.sleep(0.02)

    print("TD login done")

    td.query_positions()
    time.sleep(3)
    for _ in range(200):
        engine.process_one()
        time.sleep(0.01)

    positions = [r[1] for r in results if r[0] == "position"]
    print(f"Positions: {len(positions)}")
    for p in positions:
        inst = p["instrument_id"]
        direction = p["posi_direction"]
        yd = p["yd_position"]
        today = p["today_position"]
        dir_name = "long" if direction == "2" else "short"
        print(f"  {inst} {dir_name} yd={yd} today={today}")

    if not positions:
        print("No positions to close.")
    else:
        md.connect()
        deadline = time.time() + 15
        while time.time() < deadline:
            engine.process_one()
            if any(r[0] == "tick" for r in results):
                break
            time.sleep(0.02)

        for p in positions:
            inst = p["instrument_id"]
            direction = p["posi_direction"]
            yd = p["yd_position"]
            today = p["today_position"]

            ticks = [r[1] for r in results if r[0] == "tick" and r[1].get("instrument_id") == inst]
            if not ticks:
                md.subscribe(inst)
                deadline = time.time() + 15
                while time.time() < deadline:
                    engine.process_one()
                    ticks = [r[1] for r in results if r[0] == "tick" and r[1].get("instrument_id") == inst]
                    if ticks:
                        break
                    time.sleep(0.02)

            if not ticks:
                print(f"  No tick for {inst}, skipping")
                continue

            last_tick = ticks[-1]
            dir_name = "long" if direction == "2" else "short"

            if direction == "2":
                close_dir = "sell"
                close_price = last_tick["bid_price1"]
            else:
                close_dir = "buy"
                close_price = last_tick["ask_price1"]

            total_vol = yd + today
            print(f"  Closing {inst} {dir_name} {total_vol} lots @ {close_price} ...")
            try:
                td.send_order(inst, close_dir, "close", close_price, total_vol)
            except RuntimeError as ex:
                print(f"    close failed: {ex}, trying close_today ...")
                try:
                    td.send_order(inst, close_dir, "close_today", close_price, total_vol)
                except RuntimeError as ex2:
                    print(f"    close_today also failed: {ex2}")
                    continue

            time.sleep(5)
            for _ in range(300):
                engine.process_one()
                time.sleep(0.01)

        results.clear()
        engine.register(EventType.POSITION, lambda e: results.append(("position", e.data)))
        td.query_positions()
        time.sleep(3)
        for _ in range(200):
            engine.process_one()
            time.sleep(0.01)
        remaining = [r[1] for r in results if r[0] == "position"]
        print(f"\nRemaining positions: {len(remaining)}")
        for p in remaining:
            print(f"  {p['instrument_id']} dir={p['posi_direction']} yd={p['yd_position']} today={p['today_position']}")

    td.close()
    md.close()
    print("Done.")


if __name__ == "__main__":
    main()