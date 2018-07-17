from distutils.core import setup
import py2exe, sys, os

sys.argv.append('py2exe')

setup(
    windows=['mapgenerator.pyw'],
    options = {'py2exe': {'bundle_files': 1, 'compressed': True}},
    zipfile = None,
)

#>python setup.py py2exe