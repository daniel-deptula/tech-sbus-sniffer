import serial
import sys
import time
import base64
import binascii
import logging

LOG_FORMAT = ('%(asctime)-15s %(levelname)-8s %(message)s')
LOG_DATEFORMAT = ('%Y-%m-%d %H:%M:%S')


class Message:
    def __init__(self, msg):
        self.timestamp = time.time()
        self.msg = msg
        self.parse_msg()
        
    def parse_msg(self):
        if len(self.msg) > 12:
            self.src_addr = self.msg[0:4]
            self.dst_addr = self.msg[6:10]
            self.src_addr_str = self.src_addr.hex('-')
            self.dst_addr_str = self.dst_addr.hex('-')
            self.fromto_header = self.src_addr.hex('-') + "->" + self.dst_addr.hex('-')
            logger.debug('Msg from: ' + self.src_addr_str + " to: " + self.dst_addr_str)

            # I don't know what this value is
            self.smth1 = self.msg[4:6]
            self.smth2 = self.msg[10:12]
            # But it's always set to 0x50 0x00 when environmental measurements or commands are sent
            if self.smth1 == bytes([0x50, 0]):
                logger.debug('The message (type1) data: ' + self.msg[12:].hex(' '))
                self.data = self.msg[12:]
                self.parse_data_from_msg()
            # 0xE9 0xFD when timestamp is sent
            elif self.smth1 == bytes([0xE9, 0xFD]):
                logger.debug('The message (type2) data: ' + self.msg[12:].hex(' '))
                self.data = self.msg[12:]
                self.parse_data_from_msg()
                
        else:
            logger.error("Message too short. Unable to parse.")
            
    def parse_data_from_msg(self):
        if len(self.data) == 12 and self.data[0:4] == bytes([0x3F, 0xA1, 0x2E, 0xD0]):
            # Timestamp
            self.received_timestamp = int.from_bytes(self.data[4:12], byteorder='little', signed=False)
            self.process_timestamp()
        elif len(self.data) == 8 and self.data[0:4] == bytes([0xAC, 0xFF, 0xFF, 0xAC]):
            # ACK (bytes 0xAC, 0xFF, 0xFF, 0xAC followed by CRC-32 of the data received from the other node)
            if logger.getEffectiveLevel() <= logging.DEBUG:
                crc32 = self.data[4:8].hex(' ')
                logger.debug("ACK. CRC32 of the message acknowledged: " + crc32)
        else:
            i = 0
            while i < len(self.data):
                item_len = self.data[i]
                if item_len > 0 and i+item_len < len(self.data):
                    if self.data[i+1] == 0:
                        # Room temperature
                        self.room_temp = float(int.from_bytes(self.data[i+3:i+item_len+1], byteorder='little', signed=False))/10
                        self.process_room_temperature()
                    elif self.data[i+1] == 1:
                        # Floor temperature
                        self.floor_temp = float(int.from_bytes(self.data[i+3:i+item_len+1], byteorder='little', signed=False))/10
                        self.process_floor_temperature()
                    elif self.data[i+1] == 2:
                        # Humidity
                        self.humidity = float(int.from_bytes(self.data[i+3:i+item_len+1], byteorder='little', signed=False))/10
                        self.process_humidity()
                    elif self.data[i+1] == 0x14:
                        # Heating start/stop
                        self.heating = int.from_bytes(self.data[i+3:i+item_len+1], byteorder='little', signed=False)
                        self.process_heating()
                    elif self.data[i+1] == 0x20:
                        # Target temperature for how long
                        self.target_temp_time = int.from_bytes(self.data[i+3:i+item_len+1], byteorder='little', signed=False)
                        self.process_target_temp_time()
                    elif self.data[i+1] == 0x21:
                        # Target temperature
                        self.target_temp = float(int.from_bytes(self.data[i+3:i+item_len+1], byteorder='little', signed=False))/10
                        self.process_target_temp()
                    elif self.data[i+1] == 0x26 and item_len == 6:
                        # Time + target temperature (what's the purpose of it?!)
                        self.target_temp_time2 = int.from_bytes(self.data[i+3:i+5], byteorder='little', signed=False)
                        self.target_temp2 = float(int.from_bytes(self.data[i+5:i+7], byteorder='little', signed=False))/10
                        self.process_target_temp2()
                    else:
                        # Unknown parameter
                        logger.debug(self.fromto_header+",Unknown parameter: " + hex(self.data[i+1]))
                else:
                    # Something not supported
                    logger.debug(self.fromto_header+",Unsupported data: " + self.data.hex(' '))
                i += (item_len+1)

    def process_room_temperature(self):
        logger.info(self.fromto_header+",room temperature,"+str(self.room_temp))
    
    def process_floor_temperature(self):
        logger.info(self.fromto_header+",floor temperature,"+str(self.floor_temp))
        
    def process_humidity(self):
        logger.info(self.fromto_header+",humidity,"+str(self.humidity))
        
    def process_heating(self):
        if self.heating == 1:
            heating_str = "ON"
        elif self.heating == 0:
            heating_str = "OFF"
        else:
            heating_str = "!! " + str(self.heating)
        logger.info(self.fromto_header+",heating,"+heating_str)
            
    def process_target_temp_time(self):
        if self.target_temp_time == 0xFFFFFFFF:
            time_str = "OFF"
        else:
            time_str = str(self.target_temp_time)
        logger.info(self.fromto_header+",target temperature time,"+time_str)
    
    def process_target_temp(self):
        logger.info(self.fromto_header+",target temperature,"+str(self.target_temp))
        
    def process_target_temp2(self):
        if self.target_temp_time2 == 0xFFFF:
            time_str = "OFF"
        else:
            time_str = str(self.target_temp_time2)
        logger.info(self.fromto_header+",target temperature (2),"+str(self.target_temp2))
        logger.info(self.fromto_header+",target temperature time (2),"+time_str)
        
    def process_timestamp(self):
        my_timestamp = int(self.timestamp)
        tzoffset = time.localtime(my_timestamp).tm_gmtoff
        delta = my_timestamp + tzoffset - self.received_timestamp
        logger.info(self.fromto_header+",timestamp,"+str(self.received_timestamp)+","+str(delta))
    
    

if __name__ == "__main__":
    try:
        port = sys.argv[1]
        logfile = sys.argv[2]
    except IndexError:
        print("Usage: python3 {} serial_device logfile".format(sys.argv[0]))
        sys.exit(-1)
        
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename=logfile, encoding='utf-8', format=LOG_FORMAT, datefmt=LOG_DATEFORMAT, level=logging.DEBUG)
    
    with serial.Serial(port, 115200, parity=serial.PARITY_EVEN, bytesize=serial.SEVENBITS, timeout=None) as serial_conn:
        while True:
            # Read until LF (0x0A)
            msg = serial_conn.read_until(expected='\x0a'.encode('utf-8'), size=None)
            if len(msg) > 1:
                #Decoding the message
                strmsg = msg[0:-1].decode('ascii')
                logger.debug("Received: " + strmsg)
                if len(strmsg) > 6:
                    if strmsg[0] != '>':
                        logger.error("ERROR: Missing message start!")
                    #first char is ">"
                    #"==" at the end of the base64-encoded string is missing
                    #The last 6 characters are encoded CRC-32
                    encmsg = strmsg[1:-6]
                    enccrc = strmsg[-6:] + "=="
                    logger.debug("Base64 encoded message: " + encmsg)
                    logger.debug("Base64 encoded CRC-32: " + enccrc)
                    try:
                        decoded_msg = base64.b64decode(encmsg)
                        logger.debug("Base64 decoded message: " + decoded_msg.hex(' '))
                        decoded_crc = base64.b64decode(enccrc)
                        #Compute CRC-32 of the decoded message
                        crc = binascii.crc32(decoded_msg)
                        if crc.to_bytes(4,byteorder='little',signed=False) == decoded_crc:
                            logger.debug("CRC check pass")
                            Message(decoded_msg)
                        else:
                            logger.error("ERROR: CRC check failed")
                    except Exception as e:
                        logger.error("ERROR: Unable to decode: " + repr(e))
                else:
                    logger.error("ERROR: Message too short: " + str(len(strmsg)))
    sys.exit(0)
