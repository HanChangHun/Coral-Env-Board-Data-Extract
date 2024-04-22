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

import RPi.GPIO as GPIO
from coral.enviro.board import EnviroBoard
from coral.cloudiot.core import CloudIot
from luma.core.render import canvas
from PIL import Image, ImageDraw, ImageFont
from time import sleep

import argparse
import itertools
import os
import signal

import json
import pymysql


with open("mysql_config.json", "r") as f:
    db_config = json.load(f)

db = pymysql.connect(
    host=db_config['host'],
    user=db_config['user'], 
    db=db_config['db'],
    password=db_config['password'],
    charset='utf8'
)

BUTTON_PIN = 23
DEFAULT_CONFIG_LOCATION = os.path.join(os.path.dirname(__file__), "cloud_config.ini")

button_pressed = False


def update_display(display, msg, font, rotate=True):
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

def insert_with_retry(cursor, query, values):
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
        "--upload_delay", help="Cloud upload delay (seconds)", type=int, default=1
    )
    parser.add_argument(
        "--cloud_config", help="Cloud IoT config file", default=DEFAULT_CONFIG_LOCATION
    )
    args = parser.parse_args()

    font_path = "/usr/share/fonts/truetype/noto/NotoMono-Regular.ttf"
    font_size = 12
    font = ImageFont.truetype(font_path, font_size)

    # Button setting
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(
        BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200
    )

    # Create instances of EnviroKit and Cloud IoT.
    enviro = EnviroBoard()
    cursor = db.cursor()

    with CloudIot(args.cloud_config) as cloud:
        sensors = {}
        read_period = int(args.upload_delay / (2 * args.display_duration))
        for read_count in itertools.count():
            sensors["ambient_light"] = enviro.ambient_light
            sensors["pressure"] = enviro.pressure
            sensors["temperature"] = enviro.temperature
            sensors["humidity"] = enviro.humidity
            
            query = """
                INSERT INTO env_board (device_id, ambient_light, pressure, temperature, humidity)
                VALUES (%s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    ambient_light = VALUES(ambient_light),
                    pressure = VALUES(pressure),
                    temperature = VALUES(temperature),
                    humidity = VALUES(humidity)
            """

            values = ('env_board_1', sensors["ambient_light"], sensors["pressure"], sensors["temperature"], sensors["humidity"])

            insert_with_retry(cursor, query, values)
            db.commit()

            if button_pressed:
                # 조도와 기압 출력
                msg = "Light: %.2f lux\n" % _none_to_nan(sensors["ambient_light"])
                msg += "Pressure: %.2f kPa" % _none_to_nan(sensors["pressure"])
                update_display(enviro.display, msg, font, rotate=False)
            else:
                # 온도와 습도 출력
                msg = "Temp: %.2f C\n" % _none_to_nan(sensors["temperature"])
                msg += "RH: %.2f %%" % _none_to_nan(sensors["humidity"])
                update_display(enviro.display, msg, font, rotate=False)

            if read_count % read_period == 0 and cloud.enabled():
                cloud.publish_message(sensors)

            sleep(args.display_duration)
            
    db.close()
    GPIO.cleanup()


if __name__ == "__main__":
    main()
