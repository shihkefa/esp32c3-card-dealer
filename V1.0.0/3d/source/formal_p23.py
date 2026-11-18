"""Only enlarge the existing P23 vertical countersink to a true7mm mouth.

The cutting cone extends0.2mm beyond the pad: its actual Z63.7 mouth is
exactly7.0mm. The3.4mm passage and two horizontal holes remain unchanged.
"""
AXIS_XY=(81.,27.)
PAD_TOP_Z=63.7
MOUTH_DIAMETER=7.0
THROAT_DIAMETER=3.4
CONE_BOTTOM_Z=61.9

def build(c,old):
    # Diameter7.4 at Z63.9 -> diameter7.0 at the actual Z63.7 top face.
    return old-c.cyl(7.4,2.,d2=3.4).rot(x=180).move(81,27,63.9)
