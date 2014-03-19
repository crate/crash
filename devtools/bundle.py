import argparse
import os
import zipfile
import re
import stat

excludes = re.compile(''.join(r"""(
readline\.py|
.*EGG-INFO.*|
setuptools/.*|
_markerlib/.*|
easy_install\.py|
pkg_resources\.py|
.*/__pycache__/.*|
.*\.py[co]$
)""".strip().split('\n')))


def zipdir(path, zip):
    if path.endswith('/'):
        path = path[:-1]
    for root, dirs, files in os.walk(path, followlinks=True):
        for file in files:
            p = os.path.join(root, file)
            name = p[len(path)+1:]
            if excludes.match(name):
                continue
            zip.write(p, name)


def main(out_path, libdir):

    with open(out_path, 'w') as out_file:
        print >> out_file, '#!/usr/bin/env python'

    st = os.stat(out_path)
    os.chmod(out_path, st.st_mode | stat.S_IEXEC)

    zipf = zipfile.ZipFile(out_path, 'a', zipfile.ZIP_DEFLATED)
    zipdir(libdir, zipf)

    startscript = """
import sys, os, re
try:
    del sys.modules['crate']
except:
    pass
pattern = re.compile('^.*site-packages.*$')
for p in sys.path:
    if pattern.match(p):
        sys.path.remove(p)
from crate.crash.command import main;
main()
"""
    print(startscript)
    zipf.writestr('__main__.py', startscript)
    zipf.close()


if __name__ == '__main__':
    libdir = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                          'parts', 'omelette')
    parser = argparse.ArgumentParser(
        description="Bundle script for crash",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("output_path")
    args = parser.parse_args()
    main(args.output_path, libdir)
