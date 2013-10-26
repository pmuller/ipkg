import argparse
import sys

from . import core


def read():
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    args = parser.parse_args()
    file_ = open(args.url)
    sys.stdout.write(file_.read())
