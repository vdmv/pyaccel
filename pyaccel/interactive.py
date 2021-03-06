
"""Interactive pyaccel module

Use this module to define variables and functions to be globally available when
using

    'from pyaccel.interactive import *'

Names starting with an underscore ('_') will not be exported. In addition to
the objects defined here, all objects in pyaccel with the '@interactive'
decorator will also be available. In order to use this decorator in a pyaccel
module, import it from pyaccel.utils with

    'from pyaccel.utils import interactive'
"""

import numpy as np
import matplotlib.pyplot as plt
import pyaccel as _pyaccel


plt.ion()

pyaccel_version = _pyaccel.__version__

# helpful labels for phase-space coordinates
(rx, px) = 0, 1
(ry, py) = 2, 3
(de, dl) = 4, 5

__all__ = [name for name in dir() if not name.startswith('_')]

for f in _pyaccel.utils.interactive_list:
    name = f['name']
    module = getattr(_pyaccel, f['module'].split('.')[1])
    globals()[name] = getattr(module, name)
    __all__.append(name)
