from machine import Pin, PWM, ADC, freq, lightsleep
from time import sleep_ms, ticks_ms
from random import seed, randrange

VERSION = "1.0.2"  # version of the Solar Cricket firmware
SPEAKER = PWM(Pin(20), freq=10, duty_u16=0)  # can't do freq=0
SPEAKER_ENABLE = Pin(12, Pin.OUT)  # enable pin for speaker
SPEAKER_ENABLE.value(0)  # start with speaker off
SENSOR = ADC(26)   # analog input for light level
LED = Pin("LED", Pin.OUT)      # digital output for status LED
DEBUG_LED = Pin(13, Pin.OUT)  # digital output for debug LED
DEBUG = True  # set to False to disable debug LED
DUSK_DELAY = 30   # minutes after nightfall to wait before chirping
CHIRP_WINDOW = 30  # chip for this number of minutes each night
MIN_LIGHT = 17000     # minimum amount of light to trigger night modes (0 to 65536)
NIGHT_SLEEP = 15  # hours to sleep before checking for daylight
DAY_SLEEP = 15     # minutes to sleep during daylight
SHORT_SLEEP = 2    # minutes to sleep during nightdelay and chirpwindow

mode='DAY'  # initial mode
sunset_time = 0  # time of sunset in milliseconds
freq(125000000)  # use default CPU freq
seed()  # start with a truly random seed

personal_freq_delta = randrange(200) - 99  # different pitch every time
chirp_data = [
    # cadence, duty_u16, freq
    # there is a cadence=1 silence after each of these
    [3, 16384, 4568 + personal_freq_delta],
    [4, 32768, 4824 + personal_freq_delta],
    [4, 32768, 4824 + personal_freq_delta],
    [3, 16384, 4568 + personal_freq_delta],
]
cadence_ms = 9  # length multiplier for playback

def blink(led, count, period_ms):
    """Blink an LED a number of times with a given period."""
    for _ in range(count):
        led.value(1)
        sleep_ms(period_ms // 2)
        led.value(0)
        sleep_ms(period_ms // 2)

def beep(pwm_channel, freq, duration_ms):
    """Beep a PWM channel at a given frequency for a duration."""
    SPEAKER_ENABLE.value(1)  # enable the speaker
    pwm_channel.freq(freq)
    pwm_channel.duty_u16(32768)  # half duty cycle
    sleep_ms(duration_ms)
    pwm_channel.duty_u16(0)  # turn off the PWM
    pwm_channel.freq(10)  # reset frequency to a low value
    SPEAKER_ENABLE.value(0) # disable the speaker

def cricket():
    chirp(SPEAKER)
    sleep_ms(randrange(200,250))
    chirp(SPEAKER)
 
def chirp(pwm_channel):
    # audio generation based on cricket simulator - scruss, 2024-02
    SPEAKER_ENABLE.value(1)  # enable the speaker
    for peep in chirp_data:
        pwm_channel.freq(peep[2])
        pwm_channel.duty_u16(peep[1])
        sleep_ms(cadence_ms * peep[0])
        # short silence
        pwm_channel.duty_u16(0)
        pwm_channel.freq(10)
        sleep_ms(cadence_ms)
    SPEAKER_ENABLE.value(0) # disable the speaker

def light_level():
    # return a number from 0 (dark) to 65535 (bright)
    return SENSOR.read_u16()

def check_state(mode):
    global sunset_time
    if mode == 'DAY' and light_level() < MIN_LIGHT:
        print("It's sunset, switching to DUSK")
        sunset_time = ticks_ms()  # record the time of sunset
        mode = 'DUSK'
    elif mode == 'DUSK':
        if light_level() >= MIN_LIGHT:
            print("It's light, switching to DAY")
            mode = 'DAY'
            return mode  # exit early to avoid unnecessary checks
        # Check if it's time to start chirping
        elif (ticks_ms() - sunset_time) > DUSK_DELAY * 60 * 1000:
            print("It's dark, switching to NIGHT_CHIRP")
            mode = 'NIGHT_CHIRP'
        else:
            print("It's dusk, staying in DUSK")
    elif mode == 'NIGHT_CHIRP':
        time_remaining = (DUSK_DELAY + CHIRP_WINDOW) * 60 * 1000 - (ticks_ms() - sunset_time)
        print(f"{time_remaining // 1000} secs of chrips remain")
        # Check if it's time to stop chirping
        if (ticks_ms() - sunset_time) > (DUSK_DELAY + CHIRP_WINDOW) * 60 * 1000:
            print("Chirping done, switching to NIGHT_SLEEP")
            mode = 'NIGHT_SLEEP'
        else:
           print("Staying in NIGHT_CHIRP")
    elif mode == 'NIGHT_SLEEP':
        # Check if it's time to wake up
        mode = 'DAY'
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
        if DEBUG: #turn off debug LED
            DEBUG_LED.off()
        print("night sleep...")
        sleep_ms(10)  # wait for serial to complete
        for hour in range(NIGHT_SLEEP):
            print(f"Sleeping for hour {hour + 1} of {NIGHT_SLEEP}")
            sleep_ms(10)  # wait for serial to complete
            lightsleep(60 * 60 * 1000)  # sleep one hour repeatedly
        print("night sleep done, waking up")
    else:
        print("mode unknown")
 
LED.value(0)  # led off at start; blinks each cycle
beep(SPEAKER, 4000, 250)  # beep to indicate startup

print("Waiting 5 seconds for startup...")
print("Press Ctrl-C to quit...")
sleep_ms(5000)  # give time to quit manually
print(f"Solar Cricket v{VERSION} starting...")

# Main loop
while True:
    blink(LED, 2, 100)
    if DEBUG: #toggle debug LED
        DEBUG_LED.toggle()
    mode=check_state(mode)
    if mode == 'DAY' or mode == 'DUSK': print("Light level:", light_level())
    print("Current mode:", mode)
    do_actions(mode);
