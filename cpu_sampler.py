# cpu_sampler.py (FreeBSD correct approach)

import ctypes
import ctypes.util


class CPUSampler:
    def __init__(self):
        lib = ctypes.util.find_library("procstat")
        if not lib:
            raise RuntimeError("libprocstat not found")

        self.libprocstat = ctypes.CDLL(lib)

        libc = ctypes.util.find_library("c")
        self.libc = ctypes.CDLL(libc)

        # sysctlbyname signature
        self.libc.sysctlbyname.argtypes = [
            ctypes.c_char_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_size_t),
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]

        self.fscale = self._get_fscale()

    # --------------------------------------------------------

    def _get_fscale(self):
        name = b"kern.fscale"

        value = ctypes.c_int()
        size = ctypes.c_size_t(ctypes.sizeof(value))

        if self.libc.sysctlbyname(name, ctypes.byref(value), ctypes.byref(size), None, 0) != 0:
            raise RuntimeError("Failed to read kern.fscale")

        return value.value

    # --------------------------------------------------------

    def sample(self):
        result = {}

        # ⚠️ Use procstat CLI instead of struct guessing
        import subprocess

        try:
            output = subprocess.check_output(["ps", "-axo", "pid,%cpu"], text=True)
        except:
            return result

        lines = output.strip().split("\n")[1:]

        for line in lines:
            try:
                parts = line.split()
                pid = int(parts[0])
                cpu = float(parts[1])
                result[pid] = cpu
            except:
                continue

        return result