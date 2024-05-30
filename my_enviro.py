# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import json
from time import sleep
import RPi.GPIO as GPIO
from coral.enviro.board import EnviroBoard
from PIL import Image, ImageDraw, ImageFont

import pymysql
import signal
import sys


def signal_handler(sig, frame):
    print("Exiting program...")
    db.close()
    GPIO.cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


with open("/home/pi/workspaces/env_board/mysql_config.json", "r") as f:
    db_config = json.load(f)


def connect_to_db():
    while True:
        try:
            db = pymysql.connect(
                host=db_config["host"],
                user=db_config["user"],
                db=db_config["db"],
                password=db_config["password"],
                charset="utf8",
            )
            return db
        except pymysql.err.OperationalError as e:
            print(f"Error: {e}. Retrying in 1 seconds...")
            sleep(1)  # 1초 대기 후 재시도
        except Exception as e:
            print(f"Error: {e}. Retrying in 1 seconds...")
            sleep(1)  # 1초 대기 후 재시도


db = connect_to_db()

BUTTON_PIN = 23
FONT_PATH = "/usr/share/fonts/truetype/noto/NotoMono-Regular.ttf"
FONT_SIZE = 12

delete_interval = "2 HOUR"
button_pressed = False


def update_display(display, msg, font, rotate=False):
    canvas = Image.new("1", (display.width, display.height), color=0)
    draw = ImageDraw.Draw(canvas)
    draw.text((0, 0), msg, fill=1, font=font)

    if rotate:
        canvas = canvas.rotate(180)

    display.display(canvas)


def _none_to_nan(val):
    return float("nan") if val is None else val


def button_callback(channel):
    global button_pressed
    button_pressed = not button_pressed


def execute_with_retry(cursor, query, values):
    while True:
        try:
            cursor.execute(query, values)
            db.commit()
            break
        except pymysql.err.OperationalError as e:
            print(f"Error: {e}. Retrying...")
            db.ping(reconnect=True)
            sleep(1)  # 1초 대기 후 재시도
        except Exception as e:
            print(f"Error: {e}. Retrying...")
            sleep(1)  # 1초 대기 후 재시도


def upload_data(cursor, sensors):
    query_log = """
        INSERT INTO env_board_log (device_id, ambient_light, pressure, temperature, humidity)
        VALUES (%s, %s, %s, %s, %s)
    """

    values_log = (
        "env_board_1",
        sensors["ambient_light"],
        sensors["pressure"],
        sensors["temperature"],
        sensors["humidity"],
    )

    query = """
        INSERT INTO env_board (device_id, ambient_light, pressure, temperature, humidity)
        VALUES (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            ambient_light = VALUES(ambient_light),
            pressure = VALUES(pressure),
            temperature = VALUES(temperature),
            humidity = VALUES(humidity)
    """

    values = (
        "env_board_1",
        sensors["ambient_light"],
        sensors["pressure"],
        sensors["temperature"],
        sensors["humidity"],
    )

    execute_with_retry(cursor, query_log, values_log)
    execute_with_retry(cursor, query, values)


def delete_old_data(cursor):
    query_delete = f"DELETE FROM env_board_log WHERE timestamp < DATE_SUB(NOW(), INTERVAL {delete_interval})"
    execute_with_retry(cursor, query_delete, None)


def setup_button():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(
        BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200
    )


def get_font():
    return ImageFont.truetype(FONT_PATH, FONT_SIZE)


def read_sensors(enviro):
    return {
        "ambient_light": enviro.ambient_light,
        "pressure": enviro.pressure,
        "temperature": enviro.temperature,
        "humidity": enviro.humidity,
    }


def main():
    # Pull arguments from command line.
    parser = argparse.ArgumentParser(description="Enviro Kit Demo")
    parser.add_argument(
        "--display_duration",
        help="Measurement display duration (seconds)",
        type=float,
        default=0.5,
    )
    parser.add_argument(
        "--upload_delay",
        help="Cloud upload delay (seconds)",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--rotate",
        action="store_true",
        default=False,
    )
    args = parser.parse_args()

    font = get_font()
    setup_button()

    enviro = EnviroBoard()
    cursor = db.cursor()

    while True:
        sleep(1e-4)
        sensors = read_sensors(enviro)

        upload_data(cursor, sensors)
        delete_old_data(cursor)

        msg = ""
        if button_pressed:
            msg = f"Light: {_none_to_nan(sensors['ambient_light']):.2f} lux\n"
            msg += f"Pressure: {_none_to_nan(sensors['pressure']):.2f} kPa"
        else:
            msg = f"Temp: {_none_to_nan(sensors['temperature']):.2f} C\n"
            msg += f"RH: {_none_to_nan(sensors['humidity']):.2f} %"
        update_display(enviro.display, msg, font, rotate=args.rotate)

        sleep(args.display_duration)


if __name__ == "__main__":
    main()
