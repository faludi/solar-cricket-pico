from machine import Pin, PWM, ADC, freq, lightsleep, deepsleep, Timer
from time import sleep_ms, ticks_ms, ticks_diff
from random import seed, randrange
 
freq(125000000)  # use default CPU freq
seed()  # start with a truly random seed

SPEAKER = PWM(Pin(20), freq=10, duty_u16=0)  # can't do freq=0
SENSORPIN = ADC(26)   # analog input for light level
LEDPIN = Pin("LED", Pin.OUT)      # digital output for status LED
NIGHTDELAY = 30   # minutes after nightfall to wait before chirping
CHIRPWINDOW = 60  # chip for this number of minutes each night
MINLIGHT = 20     # minimum amount of light to trigger night modes (0 to 1023)
NIGHTSLEEP = 960  # minutes to sleep before checking for daylight
DAYSLEEP = 15     # minutes to sleep during daylight
SHORTSLEEP = 2    # minutes to sleep during nightdelay and chirpwindow

MODE = enumerate(['DAY', 'NIGHT_WAIT', 'NIGHT_CHIRP', 'NIGHT_SLEEP'])

mode='DAY'  # initial mode

tim_day = Timer(-1)  # timer for day/night transitions
tim_chirp = Timer(-1)  # timer for chirping
tim_night_delay = Timer(-1)  # timer for night delay
tim_nightsleep = Timer(-1)  # timer for night sleep


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
    return SENSORPIN.read_u16()

#CHECK STATE
def check_state():
    mode = 'NIGHT_CHIRP'
    return mode


# DO ACTIONS
def do_actions(mode):
    if mode == 'DAY':
            pass
    elif mode == 'NIGHT_WAIT':
        pass
    elif mode == 'NIGHT_CHIRP':
        print("chirping")
        cricket()
        lightsleep(randrange(3000,30000))  # sleep for random period
    elif mode == 'NIGHT_SLEEP':
        pass
    else:
        print("mode unknown")

 
LEDPIN.value(0)  # led off at start; blinks each cycle

# Main loop
while True:
    blink(LEDPIN, 2, 100);
    print("Light level:", light_level())
    mode=check_state();
    do_actions(mode);
    print("Current mode:", mode)
