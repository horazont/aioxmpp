try:
    from aioopenssl import *
except ImportError:
    from ._ssl_transport import *
