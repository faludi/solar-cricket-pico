# based on cricket simulator - scruss, 2024-02


# TODOS:
# create a workspace for this project
# chirp only at night and only for the window period
# create modes for DAY, NIGHT_WAIT, NIGHT_CHIRP, NIGHT_SLEEP
# create state machine: checkState / doActions / simpleBlink
# add sleep functionality
# add simple beep and simple blink

 
from machine import Pin, PWM, ADC, freq, lightsleep, deepsleep
from time import sleep_ms, ticks_ms, ticks_diff
from random import seed, randrange
 
freq(125000000)  # use default CPU freq
seed()  # start with a truly random seed
pwm_out = PWM(Pin(20), freq=10, duty_u16=0)  # can't do freq=0
led = Pin("LED", Pin.OUT)
light_sensor = ADC(26)  # ADC0 on GP26

#define SENSORPIN A0   // analog input for light level
#define LEDPIN 13      // digital output for status LED
#define NIGHTDELAY 30   // minutes after nightfall to wait before chirping
#define CHIRPWINDOW 60  // chip for this number of minutes each night
#define MINLIGHT 20     // minimum amount of light to trigger night modes (0 to 1023)
#define NIGHTSLEEP 960  // minutes to sleep before checking for daylight
#define DAYSLEEP 15     // minutes to sleep during daylight
#define SHORTSLEEP 2    // minutes to sleep during nightdelay and chirpwindow

# enum {DAY, NIGHT_WAIT, NIGHT_CHIRP, NIGHT_SLEEP};

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
 
 
def chirp(pwm_channel):
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
    return light_sensor.read_u16()
 
 
led.value(0)  # led off at start; blinks if chirping
### Start: pause a random amount (less than 2 s) before starting
sleep_ms(randrange(2000))
 
while True:
    print("Light level:", light_level())
    loop_start_ms = ticks_ms()
    sleep_ms(5)  # tiny delay to stop the main loop from thrashing
    led.value(1)
    loop_period_ms = randrange(30000,300000)
    chirp(pwm_out)
    sleep_ms(randrange(200,250))
    chirp(pwm_out)
    led.value(0)
    loop_elapsed_ms = ticks_diff(ticks_ms(), loop_start_ms)
    sleep_ms(loop_period_ms - loop_elapsed_ms)
