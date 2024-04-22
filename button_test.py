import RPi.GPIO as GPIO
import time

# GPIO 핀 번호 (BCM 모드)
BUTTON_PIN = 23

def button_callback(channel):
    print("1")

def main():
    # GPIO 설정
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING, callback=button_callback, bouncetime=200)

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("Program terminated.")
    finally:
        # GPIO 정리
        GPIO.cleanup()

if __name__ == '__main__':
    main()
