"""A1 legacy express capsules (answer 0x82), verified XOR before interpolation.

Protocol reference: Slamtec SDK handler_capsules.cpp, _onScanNodeCapsuleData.
Each capsule's 32 samples need the next capsule's start angle.
"""
import functools
import operator


def validate(packet):
    if len(packet) != 84 or packet[0] >> 4 != 10 or packet[1] >> 4 != 5:
        raise ValueError('Invalid express capsule header/length')
    checksum = (packet[0] & 15) | ((packet[1] & 15) << 4)
    if functools.reduce(operator.xor, packet[2:], 0) != checksum:
        raise ValueError('Express capsule checksum mismatch')
    angle = int.from_bytes(packet[2:4], 'little') & 0x7fff
    if angle >= 360 * 64:
        raise ValueError('Express capsule angle outside rotation')


def decode_pair(previous, current):
    validate(previous)
    validate(current)
    if int.from_bytes(current[2:4], 'little') & 0x8000:
        return []  # Scanner reset: the cached preceding capsule is not continuous.
    before = (int.from_bytes(previous[2:4], 'little') & 0x7fff) << 2
    after = (int.from_bytes(current[2:4], 'little') & 0x7fff) << 2
    increment = ((after - before) % (360 << 8)) << 3
    raw = before << 8
    result = []
    for offset in range(4, 84, 5):
        cabin = previous[offset:offset+5]
        for index in range(2):
            value = int.from_bytes(cabin[index*2:index*2+2], 'little')
            correction = ((cabin[4] >> (index*4)) & 15) | ((value & 3) << 4)
            angle_q6 = ((raw - (correction << 13)) >> 10) % (360 << 6)
            start = ((raw + increment) % (360 << 16)) < increment
            distance = (value & 0xfffc) / 4000
            # Express has no physical quality field; SDK derives validity from nonzero distance.
            result.append(dict(start=start, angle_deg=angle_q6/64, distance_m=distance,
                               quality=47 if distance else 0, quality_source='derived_nonzero_express_distance'))
            raw += increment
    return result
