"""Rectangle estimated from executed velocity commands; no measured position."""
import math


class TimedRectanglePath:
    def __init__(self, speed=.20, turn_speed=.30):
        if not 0 < speed <= .30 or not 0 < turn_speed <= .50:
            raise ValueError('Speed limits exceeded')
        self.speed, self.turn_speed = speed, turn_speed
        self.stages = []
        for distance in (5.,4.,5.,4.):
            self.stages.extend([('DRIVE',distance),('LEFT',math.pi/2)])
        self.index = 0
        self.progress = 0.
        self.elapsed = 0.
        self.fault = None

    @property
    def done(self):
        return self.index == len(self.stages)

    def update(self, dt, safe_vx, safe_vy, safe_wz):
        if self.fault or self.done:
            return 0.,0.
        if not all(math.isfinite(v) for v in (dt,safe_vx,safe_vy,safe_wz)) or not 0 < dt <= .20:
            self.fault='BAD_SAMPLE_OR_SCHEDULING_GAP'
            return 0.,0.
        kind, target = self.stages[self.index]
        self.elapsed += dt
        limit=target/(self.speed if kind=='DRIVE' else self.turn_speed)*2+10
        if self.elapsed > limit:
            self.fault='SEGMENT_TIMEOUT'
            return 0.,0.
        # Estimate from what the controller actually commanded, not elapsed
        # wall time while its safety gate may have stopped the robot.
        if kind=='DRIVE':
            if safe_vx < -.02 or abs(safe_vy)>.10 or abs(safe_wz)>.20:
                self.fault='UNEXPECTED_DRIVE_COMMAND'
                return 0.,0.
            self.progress += max(0.,safe_vx)*dt
        else:
            # A turn begins after a STOP interval, so translation is invalid.
            if abs(safe_vx)>.03 or abs(safe_vy)>.03 or safe_wz<-.02:
                self.fault='UNEXPECTED_LEFT_TURN_COMMAND'
                return 0.,0.
            self.progress += max(0.,safe_wz)*dt
        if self.progress >= target:
            self.index += 1
            self.progress = self.elapsed = 0.
            return 0.,0.
        return (self.speed,0.) if kind=='DRIVE' else (0.,self.turn_speed)
