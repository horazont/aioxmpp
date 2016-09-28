
version_info = (0, 7, 0, "a0")

__version__ = ".".join(map(str, version_info[:3])) + ("-"+version_info[3] if
                                                      version_info[3] else "")

version = __version__
