from machine import Pin, PWM, ADC, freq, lightsleep
from time import sleep_ms, ticks_ms
from random import seed, randrange, random
import math
from picodfplayer import DFPlayer

VERSION = "1.2.2"  # version of the Solar Cricket firmware
DFPLAYER_VERSION = True  # set to False to use PWM chirps instead of DFPlayer
SENSOR = ADC(26)   # analog input for light level
LED = Pin("LED", Pin.OUT)      # digital output for status LED
DUSK_DELAY = 1 #30   # minutes after nightfall to wait before chirping
CHIRP_WINDOW_LOW = 20  # minimum chirp window in minutes
CHIRP_WINDOW_HIGH = 40 # maximum chirp window in minutes
DEFAULT_LIGHT_HIGH = 50000  # default high light level
DEFAULT_LIGHT_LOW = 1000   # default low light level
FORCE_UPDATE_DELAY = 28 # hours before forcing light level average update
NIGHT_SLEEP = 22  # hours to sleep before checking for daylight
DAY_SLEEP = 1 #15     # minutes to sleep during daylight
SHORT_SLEEP = 1 #2    # minutes to sleep during nightdelay and chirpwindow

mode='DAY'  # initial mode
sunset_time = 0  # time of sunset in milliseconds
current_chirp = 1  # index of current chirp file (DFPlayer index starts at 1)
freq(125000000)  # use default CPU freq
seed()  # start with a truly random seed

chirp_window = 30  # initial chirp window in minutes (randomised later)
print(f"Chirp window is {chirp_window} minutes")

#Constants. Change these if DFPlayer is connected to other pins.
UART_INSTANCE=0
TX_PIN = 16
RX_PIN=17
BUSY_PIN=6
class LightLevels:
    def __init__(self):
        self.avg_high = DEFAULT_LIGHT_HIGH
        self.avg_low = DEFAULT_LIGHT_LOW
        self.load_avg()  # load previous averages from file
        print(f"Loaded avg high {self.avg_high} and low {self.avg_low}")
        # today's high and low start at extremes
        self.today_high = 0
        self.today_low = 65535

    def update (self, level):
        # update today's high and low with new level
        if level > self.today_high:
            self.today_high = level
            print(f"New high today: {self.today_high}")
        if level < self.today_low or self.today_low == 0:
            self.today_low = level
            print(f"New low today: {self.today_low}")

    def reset (self):
        # reset today's high and low for next day
        self.today_high = 0
        self.today_low = 65535 

    def update_avg (self):
        # simple moving average
        self.avg_high = (self.avg_high * 6 + self.today_high) // 7
        self.avg_low = (self.avg_low * 6 + self.today_low) // 7
        self.store_avg() # store the averages to file
        self.reset()  # reset for next day

    def increase_low_avg (self):
        # increase the low average by 100%
        self.avg_low = int(self.avg_low * 2)
        self.store_avg() # store the averages to file
        self.reset()  # reset for next day

    def read_min_light (self):
        # return minimum light level to trigger night modes
        return max(self.avg_high * 0.1, self.avg_low + (self.avg_low * 0.2))
    
    def store_avg (self):
        # store average to file
        try:
            with open("light_levels.txt", "w") as f:
                f.write(f"{self.avg_low},{self.avg_high}\n")
        except Exception as e:
            print("Error storing light levels:", e)

    def load_avg (self):
        # load average from file
        try:
            with open("light_levels.txt", "r") as f:
                line = f.readline()
                parts = line.split(",")
                if len(parts) == 2:
                    self.avg_low = int(parts[0])
                    self.avg_high = int(parts[1])
        except OSError:
            print("No previous light levels found, using defaults")
            
        except Exception as e:
            print("Error loading light levels:", e)

light_levels = LightLevels()

def randn_int(a, b):
    mu = (a + b) * 0.5
    sigma = (b - a) / 6.0  # ~99.7% inside bounds

    while 1:
        u1 = random()
        if u1 > 0.0:
            u2 = random()
            z = math.sqrt(-2.0 * math.log(u1)) * math.cos(6.283185307179586 * u2)
            x = int(mu + z * sigma + 0.5)  # round to nearest int
            if a <= x <= b:
                return x
            
def blink(led, count, period_ms):
    """Blink an LED a number of times with a given period."""
    for _ in range(count):
        led.value(1)
        sleep_ms(period_ms // 2)
        led.value(0)
        sleep_ms(period_ms // 2)

def beep(pwm_channel, freq, duration_ms):
    """Beep a PWM channel at a given frequency for a duration."""
    pwm_channel.freq(freq)
    pwm_channel.duty_u16(32768)  # half duty cycle
    sleep_ms(duration_ms)
    pwm_channel.duty_u16(0)  # turn off the PWM
    pwm_channel.freq(10)  # reset frequency to a low value

def count_files(folder=1):
    """Count the number of files on the DFPlayer."""
    #Create player instance each time due to lightsleep()'s interfering with UART
    player=DFPlayer(UART_INSTANCE, TX_PIN, RX_PIN, BUSY_PIN)
    file_count_raw = player.sendcmd(0x4E, 0, folder) # query total number of tracks in given folder
    print("Raw file count response:", file_count_raw.hex(' ') if file_count_raw else "None")
    if file_count_raw is not None and len(file_count_raw) >= 17:
        return file_count_raw[16]
    else:
        print("Failed to read file count from DFPlayer.")
        return 0

def cricket():
    #Create player instance each time due to lightsleep()'s interfering with UART
    player=DFPlayer(UART_INSTANCE, TX_PIN, RX_PIN, BUSY_PIN)
    chirp_number = randn_int(1, 5)  # play 1-5 chirps with a normal distribution
    if chirp_number is not None:
        for i in range(chirp_number):
            mp3_chirp(player)
            sleep_ms(randrange(200, 250))

def mp3_chirp(player):
    print(f"Playing chirp {current_chirp}")
    player.playTrack(1,current_chirp)
    while player.queryBusy():
        sleep_ms(10)

def light_level():
    # return an integer from 0 (dark) to 65535 (bright)
    return SENSOR.read_u16()

def store_cricket(filename):
    try:
        with open("last_cricket.txt", "w") as f:
            f.write(f"{current_chirp}\n")
    except Exception as e:
        print("Error storing last_cricket.txt", e)

def check_state(mode):
    global sunset_time, chirp_window, current_chirp
    min_light = light_levels.read_min_light()
    if ticks_ms() > sunset_time + (FORCE_UPDATE_DELAY * 60 * 60 * 1000):
        light_levels.increase_low_avg()  # doubles the low average
        print(f"Forcing light level average increase after {FORCE_UPDATE_DELAY} hours")
        sunset_time = ticks_ms()  # reset the timer
    if mode == 'DAY' and light_level() < min_light:
        print("It's sunset, switching to DUSK")
        sunset_time = ticks_ms()  # record the time of sunset
        mode = 'DUSK'
    elif mode == 'DUSK':
        if light_level() >= min_light:
            print("It's light, switching to DAY")
            mode = 'DAY'
            return mode  # exit early to avoid unnecessary checks
        # Check if it's time to start chirping
        elif (ticks_ms() - sunset_time) > DUSK_DELAY * 60 * 1000:
            print("It's dark, switching to NIGHT_CHIRP")
            current_chirp = randn_int(1, count_files(folder=1))  # select a random chirp file
            chirp_window = randrange(CHIRP_WINDOW_LOW, CHIRP_WINDOW_HIGH)  # random chirp window
            print(f"Chirp window is {chirp_window} minutes")
            mode = 'NIGHT_CHIRP'
        else:
            print("It's dusk, staying in DUSK")
    elif mode == 'NIGHT_CHIRP':
        time_remaining = (DUSK_DELAY + chirp_window) * 60 * 1000 - (ticks_ms() - sunset_time)
        print(f"{time_remaining // 1000} secs of chrips remain")
        # Check if it's time to stop chirping
        if (ticks_ms() - sunset_time) > (DUSK_DELAY + chirp_window) * 60 * 1000:
            print("Chirping done, switching to NIGHT_SLEEP")
            mode = 'NIGHT_SLEEP'
        else:
           print("Staying in NIGHT_CHIRP")
    elif mode == 'NIGHT_SLEEP':
        # Check if it's time to wake up
        mode = 'DAY'
        light_levels.update_avg()  # update the averages for the day
    print(f"Min light level is {min_light}")
    return mode

def do_actions(mode):
    if mode == 'DAY':
        print("day sleep...")
        sleep_ms(10)  # wait for serial to complete
        lightsleep(DAY_SLEEP * 60 * 1000)  # sleep during the day
    elif mode == 'DUSK':
        print("dusk sleep...")
        sleep_ms(10)  # wait for serial to complete
        lightsleep(SHORT_SLEEP * 60 * 1000) # sleep during night delay
    elif mode == 'NIGHT_CHIRP':
        print("chirping")
        cricket()
        sleep_ms(10)  # wait for serial to complete
        lightsleep(randrange(10000,300000))  # sleep for random period
    elif mode == 'NIGHT_SLEEP':
        print("night sleep...")
        sleep_ms(10)  # wait for serial to complete
        for hour in range(NIGHT_SLEEP):
            light_levels.update(light_level()) # update light levels
            print(f"Sleeping for hour {hour + 1} of {NIGHT_SLEEP}")
            sleep_ms(10)  # wait for serial to complete
            lightsleep(60 * 60 * 1000)  # sleep one hour repeatedly
        print("night sleep done, waking up")
    else:
        print("mode unknown")
 
LED.value(0)  # led off at start; blinks each cycle

player=DFPlayer(UART_INSTANCE, TX_PIN, RX_PIN, BUSY_PIN)
mp3_chirp(player)  # play a chirp to indicate startup


print("Waiting 5 seconds for startup...")
print("Press Ctrl-C to quit...")
sleep_ms(5000)  # give time to quit manually
print(f"Solar Cricket v{VERSION} starting...")

# Main loop
while True:
    blink(LED, 2, 100)
    light_levels.update(light_level())
    mode=check_state(mode)
    if mode == 'DAY' or mode == 'DUSK': print("Light level:", light_level())
    print("Current mode:", mode)
    do_actions(mode);
