import network
import wifi_config
from time import sleep

class WiFi:
    def __init__(self):
        self.ssid = wifi_config.ssid
        self.password = wifi_config.password
    
    def connect(self):
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)        
        while wlan.isconnected() == False:
            wlan.connect(self.ssid, self.password)
            self._check_connection(wlan)
        ip = wlan.ifconfig()[0]
        return ip
    
    def _check_connection(self,wlan,timeout=10):
        while timeout > 0:
            if wlan.status() >= 3:
                break
            timeout -= 1
            print('waiting for WiFi...')
            sleep(1)
        return wlan.isconnected()