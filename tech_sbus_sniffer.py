import serial
import sys
import time
import base64
import binascii
import logging

LOG_FORMAT = ('%(asctime)-15s %(levelname)-8s %(message)s')
LOG_DATEFORMAT = ('%Y-%m-%d %H:%M:%S')

class EnvData:
    def __init__(self, msg):
        self.msg = msg
        self.read_data_from_msg()

    def read_data_from_msg(self):
        i = 0
        while i+4 < len(self.msg):
            if self.msg[i:i+4] == bytes([0xAC, 0xFF, 0xFF, 0xAC]):
                # Controller's ACK (bytes 0xAC, 0xFF, 0xFF, 0xAC followed by CRC-32 of measurement data received from sensor)
                if logger.getEffectiveLevel() <= logging.DEBUG:
                    crc32 = ""
                    if i+7 < len(self.msg):
                        crc32 = self.msg[i+4:i+8].hex(' ')
                    logger.debug("Controller's ACK. CRC32: " + crc32)
                break
            elif self.msg[i:i+3] == bytes([4, 0, 0]):
                # Room temperature
                self.room_temp = float(int.from_bytes(self.msg[i+3:i+5], byteorder='little', signed=False))/10
                logger.debug("Room temperature: "+str(self.room_temp))
            elif self.msg[i:i+3] == bytes([4, 1, 0]):
                # Floor temperature
                self.floor_temp = float(int.from_bytes(self.msg[i+3:i+5], byteorder='little', signed=False))/10
                logger.debug("Floor temperature: "+str(self.floor_temp))
            elif self.msg[i:i+3] == bytes([4, 2, 0]):
                # Humidity
                self.humidity = float(int.from_bytes(self.msg[i+3:i+5], byteorder='little', signed=False))/10
                logger.debug("Humidity: "+str(self.humidity))
            else:
                # Unknown parameter
                logger.debug('Unknown parameter: ' + self.msg[i:i+3].hex(' '))
            i += 5

class Message:
    def __init__(self, msg):
        self.timestamp = time.time()
        self.msg = msg
        self.parse_msg()
        
    def parse_msg(self):
        if len(self.msg) > 12:
            self.src_addr = self.msg[0:4]
            self.dst_addr = self.msg[6:10]
            logger.debug('Msg from: ' + self.src_addr.hex('-') + " to: " + self.dst_addr.hex('-'))

            # I don't know what this value is
            self.smth1 = self.msg[4:6]
            self.smth2 = self.msg[10:12]
            # But it's always set to 0x50 0x00 when environmental measurements data is sent
            if self.smth1 == bytes([0x50, 0]):
                logger.debug('The message contains env data: ' + self.msg[12:].hex(' '))
                self.env_data = EnvData(self.msg[12:])
        else:
            logger.error("Message too short. Unable to parse.")

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
                            report = Message(decoded_msg)
                            report_str = ""
                            if hasattr(report, 'env_data'):
                                try:
                                    report_str += str(report.env_data.room_temp)+','
                                except AttributeError:
                                    report_str += ','
                                try:
                                    report_str += str(report.env_data.floor_temp)+','
                                except AttributeError:
                                    report_str += ','
                                try:
                                    report_str += str(report.env_data.humidity)
                                except AttributeError:
                                    pass
                                if len(report_str) > 2:
                                    report_str = 'MEASUREMENT,'+str(report.timestamp)+","+report.src_addr.hex('-')+','+report_str
                                    logger.info(report_str)
                        else:
                            logger.error("ERROR: CRC check failed")
                    except:
                        logger.error("ERROR: Unable to decode")
                else:
                    logger.error("ERROR: Message too short: " + str(len(strmsg)))
    sys.exit(0)
