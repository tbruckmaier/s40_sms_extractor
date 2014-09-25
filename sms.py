# coding=utf-8

import binascii
import math
import os.path, datetime, time
import array

gsm = ("@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
       "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ`¿abcdefghijklmnopqrstuvwxyzäöñüà").decode('utf-8')
ext = ("````````````````````^```````````````````{}`````\\````````````[~]`"
       "|````````````````````````````````````€``````````````````````````")

def semi_octet_swap(octet):
    return ((octet & 0xF) * 10) +  ((octet & 0xF0) >> 4)
            
def extract_scts(scts):
    year = semi_octet_swap(scts[0])
    month = semi_octet_swap(scts[1])
    day = semi_octet_swap(scts[2])
    hour = semi_octet_swap(scts[3])
    minute = semi_octet_swap(scts[4])
    second = semi_octet_swap(scts[5])
    tz = semi_octet_swap(scts[6] & ~(0x08))/4.0

    # If the MSB (which is actually bit 3) is set, negate the number
    if (scts[6] & 0x8 == 0x8):
        tz = -tz

    gsm_date = datetime.datetime(year, month, day, hour, minute, second)
    gsm_offset = datetime.timedelta(hours=tz)
    # Subtraction due to normalization; this will serve to add positive time deltas
    gsm_date = gsm_date - gsm_offset

    return gsm_date

def extract_udh(data):
    udh_length = data[0]
    udh = {}
    i = 0;
    while i < udh_length:
        udh_type = data[1 + i]
        entry_length = data[1 + i + 1]
        udh[udh_type] = data[1 + i + 2:1 + i + 2 + entry_length]
        i += 2 + entry_length

    # Actual UDH length is in octets, but UD length is in septets. Round UDH length up to nearest 7
    udh_length = int(math.ceil((udh_length + 1)*8.0/7.0))
    return udh, udh_length

def extract_ud(ud, start):
    msg_chars = []
    shift = start % 8
    mask = 0x7f

    # If the last byte likely has two septets, pad out the data 
    if (ud[-1] > 127):
        ud.append(0xFF)

    for i in xrange(start, len(ud)):
        char = ((ud[i] & (mask >> shift)) << shift) | ud[i-1] >> (8 - shift)
        msg_chars.append(chr(char))
        shift += 1
        if (shift == 8) and (ud[i] != 0xff):
            shift = 0
            char = ((ud[i] & (mask >> shift)) << shift) | ud[i-1] >> (8 - shift)
            msg_chars.append(chr(char))
            shift += 1

    return ''.join(msg_chars)
        


class Pdu:
    # Bits 1..0: TP-MTI
    TP_MTI_MASK = 0b11
    TP_MTI_SMS_DELIVER = 0b00
    TP_MTI_SMS_SUBMIT = 0b01
    TP_MTI_SMS_CMD = 0b10
    TP_MTI_SMS_RESERVED = 0b11

    # Bit 2: TP-MMS if TP-MTI is SMS_DELIVER
    TP_MMS_MASK = 0b100
    TP_MMS = 0b100

    # Bit 2: TP-RD if TP-MTI is SMS_SUBMIT
    TP_RD_MASK = 0b100
    TP_RD = 0b100

    # Bits 4..3: TP-VPF if TP-MTI is SMS_SUBMIT
    TP_VPF_MASK = 0b11000
    TP_VPF_NONE = 0b00000
    TP_VPF_ENHANCED = 0b01000
    TP_VPF_RELATIVE = 0b10000
    TP_VPF_ABSOLUTE = 0b11000

    # Bit 5 is Status... not used

    # Bit 6 indicates the presence of UDHI
    TP_UDHI_MASK = 0b01000000
    TP_UDHI      = 0b01000000

    # Bit 7 is reply path... not used

    # Message types
    class Type:
        sent, received = range(2)

        
    def __init__(self, data):
        self.tp = data[0]

        # Identify type of message
        mti = self.tp & Pdu.TP_MTI_MASK
        if (mti == Pdu.TP_MTI_SMS_DELIVER):
            self.type = Pdu.Type.received
        elif (mti == Pdu.TP_MTI_SMS_SUBMIT):
            self.type = Pdu.Type.sent
        else:
            raise ValueError

        # Check UDHI flag
        if (Pdu.TP_UDHI == (self.tp & Pdu.TP_UDHI_MASK)):
            self.udhi = True
        else:
            self.udhi = False

        # Split header fields
        if (self.type == Pdu.Type.received):
            self.tp_mr = None
            (self.number, number_length) = self.extract_number(data[1:])
            self.tp_pid = data[2 + number_length + 1]
            self.tp_dcs = data[2 + number_length + 2]
            self.tp_vp = None
            self.tp_scts = data[2 + number_length + 3 : 2 + number_length + 10]
            self.tp_udl = data[2 + number_length + 10]
            self.ud = data[2 + number_length + 11:]
        elif (self.type == Pdu.Type.sent):
            self.tp_mr = data[1]
            (self.number, number_length) = self.extract_number(data[2:])
            self.tp_pid = data[3 + number_length + 1]
            self.tp_dcs = data[3 + number_length + 2]
            self.tp_vp = data[3 + number_length + 3]
            self.tp_scts = None
            self.tp_udl = data[3 + number_length + 4]
            self.ud = data[3 + number_length + 5:]
        else:
            raise ValueError

        # Extract timestamp
        if (self.tp_scts is not None):
            self.gsm_datetime = extract_scts(self.tp_scts)
        else:
            self.gsm_datetime = None

        # Check for UDH and extract it
        if (self.udhi):
            (self.udh, udh_length) = extract_udh(self.ud)
        else:
            self.udh = {}
            udh_length = 0

        # Extract rest of UD as the message itself
        # TODO check for 7/8/UCS2 encoding
        if self.tp_dcs == 0x08:
            uda = array.array('c', [chr(each) for each in self.ud])
            self.message = uda.tostring().decode('utf-16-be')
            
        else:
            self.message = extract_ud(self.ud, udh_length)
        
            

    def extract_number(self, data):
        number_length = data[0]
        number_length_real = int(math.ceil(number_length/2.0))
        number_type = data[1]
        number = []

        if (number_type == 0x91):
            number.append("+")
        
        for each in data[2:2 + number_length_real]:
            number.append(str((each & 0xF)))
            number.append(str((each & 0xF0) >> 4));

        if (number_length % 2 != 0):
            del number[-1]

        return ''.join(number), number_length_real


def extract_blocks(data):
    assert(int(binascii.hexlify(data[0]), 16) == 0x01)
    total_block_length = int(binascii.hexlify(data[1:3]), 16)

    blocks = {}
    i = 0
    while i < total_block_length:
        block_hdr = data[3 + i: 3 + i + 3]
        block_id = int(binascii.hexlify(block_hdr[0]), 16)
        block_length = int(binascii.hexlify(block_hdr[1:3]), 16)
        block = data[3 + i + 3:3 + i + 3 + block_length]
        # 0x3, 0x2b, 0x2c are utf-16-be
        if (block_id == 0x03) or (block_id == 0x2b) or (block_id == 0x2c):
            blocks[block_id] = block.decode('utf-16-be').rstrip('\0')
        elif (block_id == 0x02):
            blocks[block_id] = block.decode('utf-8').rstrip('\0')
        else:
            blocks[block_id] = [int(binascii.hexlify(each), 16) for each in array.array('c', block).tolist()]
        i += block_length + 3

    return blocks

    

class Message:

    def __init__(self, file):
        with open(file, "rb") as f:
            self.data = f.read()

        self.file_time = time.gmtime(os.path.getmtime(file))

        # Extract main header info
        self.hdr1 = int(binascii.hexlify(self.data[0:2]), 16)
        self.hdr2 = int(binascii.hexlify(self.data[2:4]), 16)
        self.pdu_length = int(binascii.hexlify(self.data[6:8]), 16)
        self.length = int(binascii.hexlify(self.data[8:12]), 16)

        assert(len(self.data) == self.length)

        # Calcuate offset
        self.pdu_offset = 0xB0
        self.block_offset = self.pdu_offset + self.pdu_length

        # Extract PDU
        pdu_raw = array.array('c', self.data[self.pdu_offset:self.pdu_offset + self.pdu_length]).tolist()
        pdu = [int(binascii.hexlify(each), 16) for each in pdu_raw]

        # Check MMS
        if (pdu[0] & 0x0C) == 0x0C:
            self.pdu = None
            self.message = ""
            self.number = ""
            return
        else:
            self.pdu = Pdu(pdu)

        # Copy data from PDU
        self.message = self.pdu.message
        # Set time to file time; sent messages don't have timestamps, so
        self.time = self.file_time
        if (self.pdu.type == Pdu.Type.sent):
            self.number = "+18043124663"
        else:
            self.number = self.pdu.number

        # Extract blocks
        if self.block_offset + 3 < self.length:
            self.blocks = extract_blocks(self.data[self.block_offset:])
        else:
            self.blocks = None

    def __str__(self):
        if (self.pdu is None):
            return "Invalid message"
            
        if (self.pdu.type == Pdu.Type.sent):
            send_chr = '>'
        elif (self.pdu.type == Pdu.Type.received):
            send_chr = '<'
        else:
            send_cdr = ' '

        return "%c %s %s %s" % (send_chr, time.strftime("%Y-%m-%d %H:%M:%S", self.time), self.number, self.message.encode('utf-8'))

def main():
    for path, dirs, files in os.walk("/Users/nicolae/Desktop/meh/predefmessages"):
        for file in files:
            full_path = os.path.join(path, file)
            msg = Message(full_path)
            print full_path, msg

if __name__ == "__main__":
    main()
