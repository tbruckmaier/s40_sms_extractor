Nokia S40 backup SMS extractor

# About

This project is designed to extract SMS messages from a backup file created
by the built-in backup functionality of Nokia S40 devices. It has only been
tested with a Nokia 301 and is somewhat incomplete, but the actual data
extraction and parsing is there.

# Usage
Extract the Backup.NBF file (it's just a zip file) and update the path in
main() to point to the predefmessages folder in the extracted backup. 

# Message Format

S40 SMS format:

* 0x00 - 0xAF: Some kind of header
- 0x00-0x01: 2
- 0x02-0x03: 1
- 0x04-0x05: 0 (endianness test-- or upper 2 bytes of pdu length? unlikely,
  PDU has length limits)
- 0x06-0x07: Length of PDU data (starts at offset 0xB0)
- 0x08-0x09: 0 
- 0x0a-0x0b: Total length of record (should match byte size of dump file)
- 0x0c-0x5d: 0
- 0x5e-0xaf?: NUL-terminated utf-16-be remote number.

* 0xB0 - 0xB0 + [0x07]: PDU of message in GSM 03.40 format
- 0xB0: First octet 
Received messages:
- 0xB1: address-length
- 0xB2: address-type
- 0xB3 + ceil(address-length/2): semi-octet encoded number. trailing 'f's
  added to pad out to byte
- 0xB3 + ceil(address-length/2) + 1: TP-PID
- 0xB3 + ceil(address-length/2) + 2: TP-DCS
- 0xB3 + ceil(address-length/2) + 3 to + 9: TP_SCTS
- 0xB3 + ceil(address-length/2) + 10: TP-UDL (depends on DCS)
- 0xB3 + ceil(address-length/2) + 11 to end: UD
Sent messages:
- 0xB1: TP-MR
- 0xB2: address-length
- 0xB3: address-type
- 0xB4 + ceil(address-length/2): semi-octet encoded number. trailing 'f's
  added to pad out to byte. May be dummy number. 
- 0xB4 + ceil(address-length/2) + 1: TP-PID
- 0xB4 + ceil(address-length/2) + 2: TP-DCS
- 0xB4 + ceil(address-length/2) + 3: TP-VP
- 0xB4 + ceil(address-length/2) + 4: TP-UDL (depends on DCS)
- 0xB4 + ceil(address-length/2) + 5 to end: UD



* 0xB0 + [0x07] - [0x0b]: Additional fields:
0x00: 0x01
0x01-0x02: Length of rest of fields (not inclusive of header or length
itself

fields: x yy zzzzz (x -> id, yy -> length (16 bit le), zzzz -> data) 

# References

http://developer.nokia.com/community/discussion/showthread.php/4050-SMS-time-stamp-format-with-time-zone-parameter
http://en.wikipedia.org/wiki/Short_Message_Service#Flash_SMS
http://en.wikipedia.org/wiki/User_Data_Header
http://en.wikipedia.org/wiki/GSM_03.38#UCS-2_Encoding
http://en.wikipedia.org/wiki/GSM_03.40#Data_Coding_Scheme
http://mobileforensics.files.wordpress.com/2007/06/understanding_sms.pdf
http://wammu.eu/docs/manual/protocol/nokia-s40-sms.html
http://www.smartposition.nl/resources/sms_pdu.html
https://gist.github.com/laughinghan/6861452 (Incorrect though)
http://developer.nokia.com/community/discussion/showthread.php/204463-Raw-text-message-file-format-(from-*-nbf)-description
http://sourceforge.net/projects/nbuexplorer/

# 
