import time
import board
import digitalio
import pwmio
import analogio
import random
import audiomp3
import audiopwmio
import os

MP3_VERSION = True


# -------------------------------------------------------------------
# Helpers to emulate MicroPython timing functions
# -------------------------------------------------------------------

def sleep_ms(ms):
    time.sleep(ms / 1000.0)

def ticks_ms():
    return int(time.monotonic() * 1000)

# lightsleep is not supported on CircuitPython RP2350
def lightsleep(ms):
    time.sleep(ms / 1000.0)

# -------------------------------------------------------------------
# Hardware setup (CircuitPython)
# -------------------------------------------------------------------

# PWM speaker
if MP3_VERSION:
    audio = audiopwmio.PWMAudioOut(board.GP20)
else:
    SPEAKER = pwmio.PWMOut(board.GP20, frequency=10, duty_cycle=0, variable_frequency=True)

# Enable pin for speaker amplifier
SPEAKER_ENABLE = digitalio.DigitalInOut(board.GP12)
SPEAKER_ENABLE.direction = digitalio.Direction.OUTPUT
SPEAKER_ENABLE.value = False

# Light sensor (ADC 26 → A0)
SENSOR = analogio.AnalogIn(board.A0)

# Status LED
LED = digitalio.DigitalInOut(board.LED)
LED.direction = digitalio.Direction.OUTPUT

# Debug LED
DEBUG_LED = digitalio.DigitalInOut(board.GP13)
DEBUG_LED.direction = digitalio.Direction.OUTPUT

DEBUG = True

# -------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------

VERSION = "1.1.9"

DUSK_DELAY = 30   # min
CHIRP_WINDOW_LOW = 20 # min
CHIRP_WINDOW_HIGH = 40 # min
DEFAULT_LIGHT_HIGH = 50000
DEFAULT_LIGHT_LOW = 1000
FORCE_UPDATE_DELAY = 28 # hours
NIGHT_SLEEP = 22 # hours
DAY_SLEEP = 15 # min
SHORT_SLEEP = 2 # min

mode = "DAY"
sunset_time = 0

chirp_window = 30
print("Chirp window is", chirp_window)

chirp_file = "1-cricket.mp3"
chirp_samples = 14976

personal_freq_delta = random.randrange(200) - 99

chirp_data = [
    [3, 16384, 4568 + personal_freq_delta],
    [4, 32768, 4824 + personal_freq_delta],
    [4, 32768, 4824 + personal_freq_delta],
    [3, 16384, 4568 + personal_freq_delta],
]

cadence_ms = 9

def scan_cricket_files():
    global cricket_files
    dir_list = os.listdir("sounds")
    cricket_files = {}
    for file in dir_list:
        if file.endswith("cricket.mp3") and not file.startswith("."):
            decoder = audiomp3.MP3Decoder(open("sounds/" + file, "rb"))
            audio.play(decoder)
            while audio.playing:
                pass
            file_samples = decoder.samples_decoded
            print("Played:", file, "Samples:", file_samples)
            cricket_files[file] = file_samples

# -------------------------------------------------------------------
# Light level averaging
# -------------------------------------------------------------------

class LightLevels:
    def __init__(self):
        self.avg_high = DEFAULT_LIGHT_HIGH
        self.avg_low = DEFAULT_LIGHT_LOW
        self.load_avg()
        print("Loaded avg high", self.avg_high, "low", self.avg_low)
        self.today_high = 0
        self.today_low = 65535

    def update(self, level):
        if level > self.today_high:
            self.today_high = level
            print("New high today:", self.today_high)
        if level < self.today_low:
            self.today_low = level
            print("New low today:", self.today_low)

    def reset(self):
        self.today_high = 0
        self.today_low = 65535

    def update_avg(self):
        self.avg_high = (self.avg_high * 6 + self.today_high) // 7
        self.avg_low = (self.avg_low * 6 + self.today_low) // 7
        self.store_avg()
        self.reset()

    def increase_low_avg(self):
        self.avg_low = int(self.avg_low * 2)
        self.store_avg()
        self.reset()

    def read_min_light(self):
        return max(self.avg_high * 0.1, self.avg_low * 1.2)

    def store_avg(self):
        try:
            with open("light_levels.txt", "w") as f:
                f.write(f"{self.avg_low},{self.avg_high}\n")
        except Exception as e:
            print("Error storing:", e)

    def load_avg(self):
        try:
            with open("light_levels.txt", "r") as f:
                parts = f.readline().split(",")
                if len(parts) == 2:
                    self.avg_low = int(parts[0])
                    self.avg_high = int(parts[1])
        except OSError:
            print("No stored light levels, using defaults")
        except Exception as e:
            print("Error loading averages:", e)

light_levels = LightLevels()

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def blink(led, count, period_ms):
    for _ in range(count):
        led.value = True
        sleep_ms(period_ms // 2)
        led.value = False
        sleep_ms(period_ms // 2)

def beep(pwm, freq, duration_ms):
    SPEAKER_ENABLE.value = True
    pwm.frequency = freq
    pwm.duty_cycle = 32768
    sleep_ms(duration_ms)
    pwm.duty_cycle = 0
    pwm.frequency = 10
    SPEAKER_ENABLE.value = False

def chirp(pwm):
    SPEAKER_ENABLE.value = True
    for peep in chirp_data:
        pwm.frequency = peep[2]
        pwm.duty_cycle = peep[1]
        sleep_ms(cadence_ms * peep[0])
        pwm.duty_cycle = 0
        pwm.frequency = 10
        sleep_ms(cadence_ms)
    SPEAKER_ENABLE.value = False

def mp3_chirp():
    global chirp_file, chirp_samples
    start_time = time.monotonic()
    SPEAKER_ENABLE.value = True
    decoder = audiomp3.MP3Decoder(open("sounds/"+chirp_file, "rb"))
    decoder.sample_rate = random.randrange(-5000, 5000) + decoder.sample_rate
    print("MP3 sample rate:", decoder.sample_rate)
    audio.play(decoder)
    while audio.playing:
        if time.monotonic() - start_time > chirp_samples/decoder.sample_rate:
            break
    SPEAKER_ENABLE.value = False

def cricket():
    if MP3_VERSION:
        mp3_chirp()
        sleep_ms(random.randrange(200, 250))
        mp3_chirp()
    else:
        chirp(SPEAKER)
        sleep_ms(random.randrange(200, 250))
        chirp(SPEAKER)

def store_cricket(filename):
    try:
        with open("last_cricket.txt", "w") as f:
            f.write(f"{chirp_file}\n")
    except Exception as e:
        print("Error storing last_cricket.txt", e)

def light_level():
    return SENSOR.value  # 0–65535

# -------------------------------------------------------------------
# State machine
# -------------------------------------------------------------------

def check_state(mode):
    global sunset_time, chirp_window, chirp_file, chirp_samples

    min_light = light_levels.read_min_light()

    if ticks_ms() > sunset_time + FORCE_UPDATE_DELAY * 3600 * 1000:
        light_levels.increase_low_avg()
        sunset_time = ticks_ms()

    current_light = light_level()

    if mode == "DAY":
        if current_light < min_light:
            print("It's sunset → DUSK")
            sunset_time = ticks_ms()
            return "DUSK"

    elif mode == "DUSK":
        if current_light >= min_light:
            print("It's bright → DAY")
            return "DAY"

        if ticks_ms() - sunset_time > DUSK_DELAY * 60000:
            if MP3_VERSION:
                chirp_file, chirp_samples = random.choice(list(cricket_files.items()))
                print("Selected chirp file:", chirp_file)
                print("Selected chirp samples:", chirp_samples)
                store_cricket(chirp_file)
            chirp_window = random.randrange(CHIRP_WINDOW_LOW, CHIRP_WINDOW_HIGH)
            print("Night chirp window:", chirp_window)
            return "NIGHT_CHIRP"

    elif mode == "NIGHT_CHIRP":
        elapsed = ticks_ms() - sunset_time
        total = (DUSK_DELAY + chirp_window) * 60000
        if elapsed > total:
            print("Done chirping → NIGHT_SLEEP")
            return "NIGHT_SLEEP"

    elif mode == "NIGHT_SLEEP":
        light_levels.update_avg()
        return "DAY"

    return mode

# -------------------------------------------------------------------
# Action execution
# -------------------------------------------------------------------

def do_actions(mode):
    if mode == "DAY":
        print("Day sleep...")
        lightsleep(DAY_SLEEP * 60000)

    elif mode == "DUSK":
        print("Dusk wait...")
        lightsleep(SHORT_SLEEP * 60000)

    elif mode == "NIGHT_CHIRP":
        cricket()
        lightsleep(random.randrange(10000, 300000))

    elif mode == "NIGHT_SLEEP":
        DEBUG_LED.value = False
        print("Night sleep...")
        for hour in range(NIGHT_SLEEP):
            light_levels.update(light_level())
            lightsleep(3600000)

# -------------------------------------------------------------------
# Startup
# -------------------------------------------------------------------

LED.value = False
if MP3_VERSION:
    mp3_chirp()
else:
    beep(SPEAKER, 4000, 250)

print("Scanning cricket sound files...")
scan_cricket_files()
print("Solar Cricket v", VERSION, "starting...")

# -------------------------------------------------------------------
# Main loop
# -------------------------------------------------------------------

while True:
    blink(LED, 2, 100)

    if DEBUG:
        DEBUG_LED.value = not DEBUG_LED.value

    light_levels.update(light_level())
    mode = check_state(mode)

    print("Mode:", mode, "Light:", light_level())

    do_actions(mode)