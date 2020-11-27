from enum import Enum
from datetime import datetime


class Type(Enum):
    dir = 1
    file = 2


class MyFile:
    def __init__(self, name, start, type_f, time, date, size, blocks):
        self.name = name
        self.start = start
        self.type = type_f
        self.time = time
        self.date = date
        self.size = size
        self.blocks = blocks

    def __str__(self):
        return self.name

    def get_line(self, fn):
        t = "d" if self.type == Type.dir_ else "f"
        date, time, size = (self.date, self.time, self.size)
        size = str(size)
        return f"{date}  {time}  {t}  {size}  {fn}"


class CrossedCluster(Exception):
    def __init__(self, cluster):
        self.cluster = cluster
        super().__init__()

    def __str__(self):
        return f"Crossed cluster {self.cluster}"


def get_bytes(num):
    result = []
    for i in range(4):
        result.append(num % 256)
        num //= 256
    return bytes(result)


def parse_record(record):
    name = record[1:11] + record[14:26] + record[28:]
    for i in range(len(name) // 2):
        if name[i*2:(i + 1)*2] == b'\x00\x00':
            return name[:i * 2]
    return name


def get_info(block):
    indexes = [0x1a, 0x1b, 0x14, 0x15]
    for i in range(len(indexes)):
        indexes[i] = block[indexes[i]] * (256 ** i)
    start = sum(indexes)
    type_f, n, size = (Type.file_, 0, 0)
    if block[0x0b] & 0x10:
        type_f = Type.dir_
    for i in range(0x16, 0x1a):
        n += block[i] * 256 ** (i - 0x16)
        size += block[i + 6] * 256 ** (i - 0x16)
    n = ("0" * 32 + bin(n)[2:])[-32:]
    data = [n[16:21], n[21:-5], n[-5:], n[11:16], n[7:11], n[:7]]
    for i in range(len(data)):
        data[i] = int(data[i], 2)
    for i in [0, 1, 3, 4]:
        data[i] = ("00" + str(data[i]))[-2:]
    time = f"{data[0]}:{data[1]}:'0'{str(data[2] * 2)[-2:]}"
    date = f"{data[3]}.{data[4]}.{data[5] + 1980}"
    name = block[:8].decode("latin-1")
    exp = block[8:11].decode("latin-1")
    while name[-1] == " ":
        name = name[:-1]
    if exp != "   ":
        while name[-1] == " ":
            name = name[:-1]
        name = f"{name}.{exp}"
    return start, type_f, time, date, name, size


def make_lfn_records(fn, chk_sum):
    result = []
    k = len(fn) // 26
    if k*26 < len(fn):
        fn += b'\x00\x00' + b'\xff'*((k + 1)*26 - len(fn) - 2)
    k = 0
    while fn:
        data, k = ([], k + 1)
        data.append(bytes([k]))
        data.append(fn[:10])
        fn = fn[10:]
        data.append(b'\x0f\x00')
        data.append(bytes([chk_sum]))
        data.append(fn[:12])
        fn = fn[12:]
        data.append(b'\x00\x00')
        data.append(fn[:4])
        fn = fn[4:]
        if not fn:
            n = len(data) - 7
            data.insert(n, bytes([data.pop(n)[0]+0x40]))
        result.insert(0, b''.join(data))
    return b''.join(result)


def find_last_cluster(self, file_):
    n = self.start_fat + file_.start * 4
    self.fo.seek(n)
    s = self.start_fat + self.read_num(4) * 4
    while s < 0x0ffffff8:
        n = s
        self.fo.seek(s)
        s = self.start_fat + self.read_num(4) * 4
    return n


def get_clusters(self, n, err=None):
    if err is None:
        err = []
    result = []
    while 0x0ffffff8 > n > 1:
        result.append(n)
        self.fo.seek(self.start_fat + n * 4)
        n = self.read_num(4)
        if n in result:
            err.append(str(CrossedCluster(n)))
            return result
    return result


def get_date_time():
    dt = datetime.now()
    dt = [dt.second//2, dt.minute, dt.hour, dt.day, dt.month, dt.year-1980]
    sec, minute, hour = map(lambda x: bin(x)[2:], dt[:3])
    time = ('0'*5 + hour)[-5:] + ('0'*6 + minute)[-6:] + ('0'*5 + sec)[-5:]
    time = get_bytes(int(time, 2))[:2]
    day, mon, year = map(lambda x: bin(x)[2:], dt[3:])
    date = ('0'*7+year)[-7:] + ('0'*4+mon)[-4:] + ('0'*5+day)[-5:]
    date = get_bytes(int(date, 2))[:2]
    return date, time, bytes([datetime.now().microsecond // 10000])




