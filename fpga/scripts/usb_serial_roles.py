"""Resolve the unique known FPGA USB-UART adapter without relying on its COM number."""
from serial.tools import list_ports


def fpga_port(requested='auto'):
    candidates = [p for p in list_ports.comports() if (p.vid, p.pid) == (0x067b, 0x2303)
                  and (requested.lower() == 'auto' or p.device.upper() == requested.upper())]
    if len(candidates) != 1:
        raise RuntimeError(f'Expected one FPGA Prolific 067B:2303 adapter for {requested}; found {[p.device for p in candidates]}')
    return candidates[0].device
