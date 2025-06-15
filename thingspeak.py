import urequests
import thingspeak_config

class ThingSpeakApi:
    def __init__(self):
        self.server = thingspeak_config.server
        self.writeapikey = thingspeak_config.writeapikey
        self.readapikey = thingspeak_config.readapikey
        self.channel = thingspeak_config.channel
        
    def write_single_field(self, fieldvalue):    
        url = f"{self.server}/update?api_key={self.writeapikey}&field1={fieldvalue}"
        request = urequests.post(url)
        request.close()
    
    def write_multiple_fields(self, field_data):    
        url = f"{self.server}/update?api_key={self.writeapikey}"
        i = 1
        for field_value in field_data: 
            url = url + f"&field{i}={field_value}"
            i = i + 1
        request = urequests.post(url)
        request.close()
        
    def read_single_field(self, fieldnumber):    
        url = f"{self.server}/channels/{self.channel}/fields/{fieldnumber}/last.json?api_key={self.readapikey}"
        request = urequests.get(url)
        return request
        request.close()