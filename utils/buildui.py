#!/usr/bin/env python3

# pyuic is not installed on my system, so here we go with a workaround

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-5", "--qt5",
        dest="version",
        action="store_const",
        const=5,
        default=4)
    parser.add_argument("uifile")
    parser.add_argument("pyfile")

    args = parser.parse_args()

    if args.version == 4:
        import PyQt4.uic as uic
    elif args.version == 5:
        import PyQt5.uic as uic
    else:
        raise ValueError("Invalid version: {}".format(args.version))

    with open(args.pyfile, "w") as f:
        f.write("#pylint: skip-file\n")
        uic.compileUi(args.uifile, f)
