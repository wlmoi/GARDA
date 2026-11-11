#!/usr/bin/env python3
"""Convert a tb_vga_render pixel dump (x y RGB444) into a PNG."""
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
img = np.zeros((480, 640, 3))
for line in open(sys.argv[1]):
    x, y, c = line.split()
    v = int(c, 16)
    img[int(y), int(x)] = [(v >> 8 & 15) / 15, (v >> 4 & 15) / 15, (v & 15) / 15]
plt.imsave(sys.argv[2], img)
print("wrote", sys.argv[2])
