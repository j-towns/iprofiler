from ._version import version_info, __version__

from .iprofiler import *

def _jupyter_nbextension_paths():
    return [{
        'section': 'notebook',
        'src': 'static',
        'dest': 'iprofiler',
        'require': 'iprofiler/extension'
    }]
