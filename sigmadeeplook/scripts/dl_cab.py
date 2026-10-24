"""SigmaDeepLook: read the members of a Microsoft cabinet (.cab) in memory, standard library only (fix round 14, ticket 83 P0.14b.H5).

A cabinet holds folders (compression groups) and the files in them. A folder is stored (type 0) or MSZIP (type 1: one deflate stream per
data block, each block may use the 32 KB before it as its dictionary), both read here with zlib. LZX (type 3) and Quantum (type 2) are not
decoded here: such a member is named as not decoded, never guessed; 7-Zip reads them when it is installed. A member that continues in
another cabinet of a set is not read either. Nothing is written to disk; a member is read up to a byte cap.
"""
import struct
import zlib

MAX_MEMBER = 8 << 20          # a member is decoded up to this many bytes
MAX_FOLDER_BLOCKS = 1 << 16   # data blocks one folder may declare before the cabinet is taken as damaged
METHODS = {0: "stored", 1: "MSZIP", 2: "Quantum", 3: "LZX"}


class Cabinet:
    def __init__(self, raw):
        self.raw = raw
        self.folders, self.files = [], []   # folders: dict(start, blocks, type); files: dict(name, size, offset, folder, mtime)
        self.cb_data = 0
        self.parse()

    def parse(self):
        b = self.raw
        if len(b) < 36 or b[:4] != b"MSCF":
            raise ValueError("not a cabinet")
        coff_files = struct.unpack_from("<I", b, 16)[0]
        nfold, nfiles, flags = struct.unpack_from("<HHH", b, 26)
        pos, cb_folder = 36, 0
        if flags & 4:
            cb_header, cb_folder, self.cb_data = struct.unpack_from("<HBB", b, 36)
            pos = 40 + cb_header
        for bit in (1, 2):   # neighbour cabinet and disk names
            if flags & bit:
                for _ in range(2):
                    pos = b.index(b"\0", pos) + 1
        for i in range(nfold):
            at = pos + i * (8 + cb_folder)
            if at + 8 > len(b):
                raise ValueError("the folder table is cut off")
            start, blocks, ctype = struct.unpack_from("<IHH", b, at)
            self.folders.append({"start": start, "blocks": blocks, "type": ctype})
        at = coff_files
        for _ in range(nfiles):
            if at + 16 > len(b):
                break
            size, uoff, ifold, date, tm, attr = struct.unpack_from("<IIHHHH", b, at)
            end = b.find(b"\0", at + 16)
            if end < 0:
                break
            raw_name = b[at + 16:end]
            name = raw_name.decode("utf-8" if attr & 0x80 else "cp437", "replace")
            at = end + 1
            mtime = "%04d-%02d-%02d %02d:%02d:%02d" % (1980 + (date >> 9), (date >> 5) & 15 or 1, date & 31 or 1, tm >> 11, (tm >> 5) & 63, (tm & 31) * 2)
            self.files.append({"name": name, "size": size, "offset": uoff, "folder": ifold, "mtime": mtime})

    def method(self, ifold):
        if not 0 <= ifold < len(self.folders):
            return "continued in another cabinet"
        return METHODS.get(self.folders[ifold]["type"] & 0xF, f"type {self.folders[ifold]['type']:#x}")

    def readable(self, f):
        """True when the file's folder is stored or MSZIP and lies wholly in this cabinet."""
        return 0 <= f["folder"] < len(self.folders) and (self.folders[f["folder"]]["type"] & 0xF) in (0, 1)

    def folder_bytes(self, ifold, upto):
        """The first `upto` bytes (at least; whole blocks) of a folder's uncompressed data."""
        fo = self.folders[ifold]
        if fo["blocks"] > MAX_FOLDER_BLOCKS:
            raise ValueError("the folder declares too many data blocks")
        pos, out, prev = fo["start"], bytearray(), b""
        for _ in range(fo["blocks"]):
            if len(out) >= upto:
                break
            if pos + 8 + self.cb_data > len(self.raw):
                raise ValueError("a data block lies past the end of the file")
            cb, cu = struct.unpack_from("<HH", self.raw, pos + 4)
            body = self.raw[pos + 8 + self.cb_data:pos + 8 + self.cb_data + cb]
            pos += 8 + self.cb_data + cb
            if fo["type"] & 0xF == 0:
                block = body
            else:
                if body[:2] != b"CK":
                    raise ValueError("an MSZIP block lacks its CK mark")
                d = zlib.decompressobj(-15, zdict=prev[-32768:]) if prev else zlib.decompressobj(-15)
                block = d.decompress(body[2:], cu + 1)
            if len(block) != cu:
                raise ValueError("a data block does not decode to its declared size")
            out += block
            prev = block
        return bytes(out)

    def read(self, f, cap=MAX_MEMBER):
        """The bytes of file `f` (up to cap + 1), or None when its folder is not stored or MSZIP."""
        if not self.readable(f):
            return None
        want = min(f["size"], cap + 1)
        if f["offset"] + want > MAX_MEMBER * 4:
            return None
        data = self.folder_bytes(f["folder"], f["offset"] + want)
        return data[f["offset"]:f["offset"] + want]


def open_cab(path, cap=64 << 20):
    """-> Cabinet for a file that starts with MSCF and parses, else None."""
    try:
        with open(path, "rb") as fh:
            raw = fh.read(cap)
        return Cabinet(raw) if raw[:4] == b"MSCF" else None
    except (OSError, ValueError, struct.error):
        return None


def member_dicts(cab, file_size):
    """The members of a cabinet in the shape the archive code lists them: name, size, packed (the file's share of its folder), kind, enc, offset, mtime."""
    out = []
    totals = {}
    for f in cab.files:
        totals[f["folder"]] = totals.get(f["folder"], 0) + f["size"]
    for f in cab.files:
        fo = cab.folders[f["folder"]] if 0 <= f["folder"] < len(cab.folders) else None
        packed = 0
        if fo and totals.get(f["folder"]):
            nxt = [x["start"] for x in cab.folders if x["start"] > fo["start"]]
            span = (min(nxt) if nxt else file_size) - fo["start"]
            packed = int(span * f["size"] / totals[f["folder"]])
        out.append(dict(name=f["name"], size=f["size"], packed=packed, kind="file", enc=False, offset=None, mtime=f["mtime"], cab=f))
    return out


def reader(path):
    """-> read(name, cap) for the members of a cabinet (None for a member that is not stored or MSZIP, or whose data is damaged)."""
    cab = open_cab(path)
    if cab is None:
        return None
    by = {}
    for f in cab.files:
        by.setdefault(f["name"], f)

    def read(name, cap):
        f = by.get(name)
        if f is None:
            return None
        try:
            return cab.read(f, cap)
        except (ValueError, zlib.error, struct.error):
            return None
    return read
