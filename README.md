# tech-sbus-sniffer
RS485 sniffer and parser of the Tech SBUS protocol

# Overview
TECH SBUS is a name used by vendor "Tech Sterowniki" for a custom communication protocol over RS-485, most probably developed by them. The protocol is used by their products - room sensors/regulators and central heating actuator controllers.

This project is a very simple Python script that collects data sent over a RS-485 bus and extracts transmitted temperature and humidity measurements.

It is a result of my reverse engineering of the protocol so only the limited functionality is available at the moment. If time permits new features may be added in future because much more data is transmitted. Everyone's encouraged to contribute.

Devices used for testing:
- L-X WiFi - central controller
- R-12S - wired room regulator with air temperature sensor, humidity sensor and a connector for floor temperature NTC sensor

# The protocol

The data sent over a serial bus consists of ASCII characters.

A single frame starts with a '>' (0x3E) and ends with a line feed (0x0A). Between these two characters there're two base64-encoded strings:
1) everything without the last 6 characters: **the message**
2) the last 6 characters (without "==" padding): **CRC-32 of the message**

The structure of the message:

| Length (bytes) | Function  |
| ----------- | ----------- |
| 4 | Source address (every regulator or controller has it's own 4-byte address)    |
| 2 | ? (when measurements are sent it's 50 00; in some other messages it's E9 FD)  |
| 4 | Destination address                                                           |
| 2 | ? (looks like it's always the same as the two bytes after the source address) |
| n | The data                                                                      |

## The data
### Temperature and humidity values
One or multiple parameters can be included in one message. Three bytes mean the type of the parameter and are followed by two bytes with the value.
Types of parameters:
* 04 00 00 - room temperature
* 04 01 00 - floor temperature?
* 04 02 00 - humidity

The values are two-byte integers which divided by 10 give temperature in Celsius degrees or humidity percentage.

Example:
```
04 00 00 f2 00 04 01 00 04 01 04 02 00 4c 02
^^^^^^^^ ^^^^^ ^^^^^^^^ ^^^^^ ^^^^^^^^ ^^^^^
room     24,2  floor    26    humidity 58,8%
temp     deg   temp     deg
```
### Other values
There're many other types of information transmitted but I didn't have time to analyse them / figure out what is what. I noticed for example date and time transmitted regularly by the central controller as follows:
```
3f a1 2e d0 24 94 6e 38 00 00 00 00
            ^^^^^^^^^^^
            Seconds from the Unix Epoch
            946770980 = Sat Jan  1 23:56:20 UTC 2000
```

# Script usage

Once started, the script opens the serial port given as the first parameter and starts listening for the communication on the RS485 bus. The messages are saved to the log file specified as the second parameter. The default "debug" logging level logs all messages and a lot of details about the processing. The temperature and humidity values are logged with the "info" level in the following format (CSV):
```
type of data,unix timestamp (when data received),source device address,room temperature,floor temperature,humidity
```
Example:
```
MEASUREMENT,946700000.0300002,00-01-02-03,21.5,27.2,60.4
```
Currently the only way to reduce the logging verbosity is to change the following piece of code:
```
level=logging.DEBUG
```
to for example:
```
level=logging.INFO
```
## Starting the script
```
/usr/bin/python3 ./tech_sbus_sniffer.py /dev/ttyUSB0  ./environment.log
                 ^^^^^^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^
                 script path            serial        log file path
                                        device
```
## Serial devices
I used USB RS485 serial interfaces with the following chips and they both work fine:
- FT232RL
- CH341
