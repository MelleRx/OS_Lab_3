from main import *


class Reader:
    def __init__(self, fn):
        self.fo, self.writable = (open(fn, 'rb+'), True)
        self.fn = fn
        self.fo.seek(0x0b)
        data = list(map(lambda x: self.read_num(x), [2, 1, 2, 1]))
        self.b_per_sec, self.sec_per_clus, res_sec, self.n_of_fats = data
        self.fo.seek(0x24)
        self.sec_per_fat = self.read_num(2)
        self.start_fat = res_sec * self.b_per_sec
        self.len_fat = self.sec_per_fat * self.b_per_sec
        self.root_dir = self.n_of_fats * self.len_fat + self.start_fat
        self.len_clus = self.sec_per_clus * self.b_per_sec
        date_time = ("00:00:00", "01.01.1980")
        self.root = MyFile("root", 2, Type.dir_, *date_time, 0, (0, 0))
        self.current = self.root
        self.cd(self.root)

    def read_num(self, n, num=None):
        result = 0
        data = num if num else self.fo.read(n)
        for i in range(n):
            result += data[i] * (256 ** i)
        return result

    def cd(self, file_):
        if not file_.start:
            self.cd(self.root)
            return
        self.current = file_
        data = self.get_data(file_.start)
        name, self.files, k = (b'', [], 0)
        for i in range(len(data) // 32):
            if k > 0:
                k -= 1
                continue
            block = data[i * 32:(i + 1) * 32]
            if block[0] in [0xe5, 0x00]:
                continue
            while block[0x0b] == 0x0f:
                k += 1
                name = parse_record(block) + name
                block = data[(i + k) * 32:(i + k + 1) * 32]
            name = name.decode('utf-16')
            start, type_f, time, date, namen, size = get_info(block)
            if not name:
                name = namen
            f = MyFile(name, start, type_f, time, date, size, (i, k + 1))
            self.files.append(f)
            name = b''

    def get_data(self, start):
        return b''.join(self.get_data_by_clusters(start))

    def get_data_by_clusters(self, start):
        clusters = self.get_clusters(start)
        for c in clusters:
            self.fo.seek(self.root_dir + (c - 2) * self.len_clus)
            yield self.fo.read(self.len_clus)

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

    def add_cluster(self, end=None):
        self.fo.seek(self.start_fat)
        for n in range(self.len_fat // 4):
            if not self.read_num(4):
                if end:
                    self.fo.seek(self.start_fat + end * 4)
                    self.fo.write(get_bytes(n))
                self.fo.seek(self.start_fat + n * 4)
                self.fo.write(b'\xff' * 4)
                self.fo.seek(self.root_dir + (n - 2) * self.len_clus)
                self.fo.write(b'\x00' * self.len_clus)
                return n

    def cf(self, fn, start=0, size=0):
        self.check_double(fn)
        self.make_new_records(fn, Type.file_, start, size)

    def check_double(self, fn):
        for f in self.files:
            if f.name == fn:
                raise FileExistsError(fn)

    def make_dos_record(self, fn, typ, start, size):
        data = []
        start = get_bytes(start)
        dosname = str(len(self.files)).encode('latin-1')
        name, exp = (fn, b'') if fn in b'..' else (dosname[:8], dosname[8:])
        data.append((name + b' ' * 8)[:8])
        data.append((exp + b' ' * 3)[:3])
        data.append(b'\x10\x00' if typ == Type.dir_ else b'\x20\x00')
        date, time, ss = get_date_time()
        table_data = [ss, time, date, date, start[2:], time, date, start[:2]]
        for e in table_data:
            data.append(e)
        data.append(get_bytes(size))
        return b''.join(data)

    def make_new_records(self, dn, typ, start, size=0):
        dir_name = dn.encode("latin-1") if dn in '..' else b' '
        dos_rec = self.make_dos_record(dir_name, typ, start, size)
        chksum = dos_rec[0]
        for i in range(1, 11):
            chksum = (((chksum & 1) << 7) + (chksum >> 1) + dos_rec[i]) % 256
        data = make_lfn_records(dn.encode('utf-16')[2:], chksum) + dos_rec
        while data:
            data = self.add_entry(data)
            if data:
                last = self.add_cluster(last)

    def add_entry(self, data):
        d_data = self.get_data(self.current.start)
        for i in range(len(d_data) // 32):
            if not d_data[i * 32]:
                d_data = d_data[:i * 32] + data[:32] + d_data[(i + 1) * 32:]
                data = data[32:]
            if not data:
                break
        self.write_data(self.current.start, d_data)
        return data

    def write_data(self, start, data):
        while start < 0x0ffffff8:
            self.upwrite_data_by_cluster(start, data[:self.len_clus])
            data = data[self.len_clus:]
            self.fo.seek(self.start_fat + start * 4)
            start = self.read_num(4)

    def upwrite_data_by_cluster(self, n, data):
        self.fo.seek(self.root_dir + (n - 2) * self.len_clus)
        self.fo.write(data)

