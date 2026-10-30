"""Measured-pose 5 m x 4 m rectangle: forward legs and four left quarter-turns."""
import math


def wrap(angle):
    return math.atan2(math.sin(angle), math.cos(angle))


class RectanglePath:
    def __init__(self, first_side=5.0, second_side=4.0, speed=.20, turn_speed=.30):
        values = (first_side, second_side, speed, turn_speed)
        if any(not math.isfinite(x) or x <= 0 for x in values):
            raise ValueError('Positive finite dimensions and speeds required')
        if first_side > 10 or second_side > 10 or speed > .30 or turn_speed > .50:
            raise ValueError('Route limits: 10 m sides, 0.30 m/s, 0.50 rad/s')
        self.lengths = (first_side, second_side, first_side, second_side)
        self.corners = ((first_side, 0.), (first_side, second_side), (0., second_side), (0., 0.))
        self.starts = ((0., 0.),) + self.corners[:-1]
        self.speed, self.turn_speed = speed, turn_speed
        self.origin = None
        self.side = 0
        self.phase = 'WAITING'
        self.deadline = None
        self.fault = None

    def abort(self, reason):
        self.fault, self.phase = reason, 'FAULT'
        return 0., 0.

    def update(self, x, y, yaw, now):
        if not all(math.isfinite(v) for v in (x, y, yaw, now)):
            return self.abort('NONFINITE_POSE')
        if self.phase in ('DONE', 'FAULT'):
            return 0., 0.
        if self.origin is None:
            self.origin = (x, y, yaw)
            self.phase = 'DRIVE'
            self.deadline = now + self.lengths[0] / self.speed * 2 + 10
        if now > self.deadline:
            return self.abort('SEGMENT_TIMEOUT')
        ox, oy, oyaw = self.origin
        dx, dy = x-ox, y-oy
        local_x = math.cos(oyaw)*dx + math.sin(oyaw)*dy
        local_y = -math.sin(oyaw)*dx + math.cos(oyaw)*dy
        local_yaw = wrap(yaw-oyaw)
        if self.phase == 'DRIVE':
            heading = self.side * math.pi/2
            sx, sy = self.starts[self.side]
            along = (local_x-sx)*math.cos(heading)+(local_y-sy)*math.sin(heading)
            cross = -(local_x-sx)*math.sin(heading)+(local_y-sy)*math.cos(heading)
            remaining = self.lengths[self.side]-along
            if abs(cross) > .25 or along < -.20 or remaining < -.20:
                return self.abort('PATH_DEVIATION')
            error = wrap(heading-local_yaw)
            if abs(error) > .40:
                return self.abort('HEADING_DEVIATION')
            if remaining <= .05:
                self.phase = 'TURN_LEFT'
                self.deadline = now + math.pi/2/self.turn_speed*3+10
                return 0., 0.
            # Small steering corrections; corners always turn counterclockwise.
            omega = max(-.20, min(.20, 1.2*error-.8*cross))
            return min(self.speed, .6*remaining), omega
        error = wrap((self.side+1)*math.pi/2-local_yaw)
        if abs(error) <= .04:
            self.side += 1
            if self.side == 4:
                self.phase = 'DONE'
            else:
                self.phase = 'DRIVE'
                self.deadline = now+self.lengths[self.side]/self.speed*2+10
            return 0., 0.
        if error < 0 or error > math.pi/2+.45:
            return self.abort('LEFT_TURN_DEVIATION')
        return 0., min(self.turn_speed, .8*error)
