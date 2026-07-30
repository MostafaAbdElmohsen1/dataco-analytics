# wsgi.py
#
# Entry point for PythonAnywhere.
#
# In the PythonAnywhere Web tab, open the WSGI configuration file and
# replace its whole contents with the two lines below (adjust the path
# and username if yours differ):
#
#     import sys
#     sys.path.insert(0, "/home/MostafaAbdElmohsen1/dataco-analytics")
#     from wsgi import application
#
# PythonAnywhere looks for a module-level object called `application`.

import os
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
if PROJECT_DIR not in sys.path:
    sys.path.insert(0, PROJECT_DIR)

from app import server as application  # noqa: E402  (Dash's Flask server)
