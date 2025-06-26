from machine import Pin, PWM, ADC, freq, lightsleep, deepsleep
from time import sleep_ms, ticks_ms
from random import seed, randrange
 
freq(125000000)  # use default CPU freq
seed()  # start with a truly random seed

SPEAKER = PWM(Pin(20), freq=10, duty_u16=0)  # can't do freq=0
SENSOR = ADC(26)   # analog input for light level
LED = Pin("LED", Pin.OUT)      # digital output for status LED
NIGHTDELAY = 30   # minutes after nightfall to wait before chirping
CHIRPWINDOW = 30  # chip for this number of minutes each night
MINLIGHT = 10000     # minimum amount of light to trigger night modes (0 to 1023)
NIGHTSLEEP = 15  # hours to sleep before checking for daylight
DAYSLEEP = 15     # minutes to sleep during daylight
SHORTSLEEP = 2    # minutes to sleep during nightdelay and chirpwindow

mode='DAY'  # initial mode

sunset_time = 0  # time of sunset in milliseconds

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
    pwm_channel.freq(freq)
    pwm_channel.duty_u16(32768)  # half duty cycle
    sleep_ms(duration_ms)
    pwm_channel.duty_u16(0)  # turn off the PWM
    pwm_channel.freq(10)  # reset frequency to a low value

def cricket():
    chirp(SPEAKER)
    sleep_ms(randrange(200,250))
    chirp(SPEAKER)
 
def chirp(pwm_channel):
    # audio generation based on cricket simulator - scruss, 2024-02
    for peep in chirp_data:
        pwm_channel.freq(peep[2])
        pwm_channel.duty_u16(peep[1])
        sleep_ms(cadence_ms * peep[0])
        # short silence
        pwm_channel.duty_u16(0)
        pwm_channel.freq(10)
        sleep_ms(cadence_ms)

def light_level():
    # return a number from 0 (dark) to 65535 (bright)
    return SENSOR.read_u16()

#CHECK STATE
def check_state(mode):
    global sunset_time
    if mode == 'DAY' and light_level() < MINLIGHT:
        print("It's sunset, switching to DUSK")
        sunset_time = ticks_ms()  # record the time of sunset
        mode = 'DUSK'
    elif mode == 'DUSK':
        if light_level() >= MINLIGHT:
            print("It's light, switching to DAY")
            mode = 'DAY'
            return mode  # exit early to avoid unnecessary checks
        # Check if it's time to start chirping
        elif (ticks_ms() - sunset_time) > NIGHTDELAY * 60 * 1000:
            print("It's dark, switching to NIGHT_CHIRP")
            mode = 'NIGHT_CHIRP'
        else:
            print("It's dusk, staying in DUSK")
    elif mode == 'NIGHT_CHIRP':
        # Check if it's time to stop chirping
        if (ticks_ms() - sunset_time) > (NIGHTDELAY + CHIRPWINDOW) * 60 * 1000:
            print("Chirping window closed, switching to NIGHT_SLEEP")
            mode = 'NIGHT_SLEEP'
        else:
            print("Time remains, staying in NIGHT_CHIRP")
    elif mode == 'NIGHT_SLEEP':
        # Check if it's time to wake up
        mode = 'DAY'
    return mode

# DO ACTIONS
def do_actions(mode):
    if mode == 'DAY':
        print("day sleep...")
        sleep_ms(10)  # wait for serial to complete
        lightsleep(DAYSLEEP * 60 * 1000)  # sleep during the day
    elif mode == 'DUSK':
        print("dusk sleep...")
        sleep_ms(10)  # wait for serial to complete
        lightsleep(SHORTSLEEP * 60 * 1000) # sleep during night delay
    elif mode == 'NIGHT_CHIRP':
        print("chirping")
        cricket()
        sleep_ms(10)  # wait for serial to complete
        lightsleep(randrange(3000,30000))  # sleep for random period
    elif mode == 'NIGHT_SLEEP':
        print("night sleep...")
        sleep_ms(10)  # wait for serial to complete
        for hour in range(NIGHTSLEEP):
            lightsleep(60 * 60 * 1000)  # sleep one hour repeatedly
        print("night sleep done, waking up")
    else:
        print("mode unknown")
 
LED.value(0)  # led off at start; blinks each cycle

beep(SPEAKER, 4000, 250)  # beep to indicate startup

print("Waiting 5 seconds for startup...")
print("Press Ctrl-C to quit...")
sleep_ms(5000)  # give time to quit manually
print("Solar Cricket v1.0 starting...")

# Main loop
while True:
    blink(LED, 2, 100);
    if mode == 'DAY' or mode == 'DUSK': print("Light level:", light_level())
    mode=check_state(mode);
    print("Current mode:", mode)
    do_actions(mode);
