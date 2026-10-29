"""Desktop launcher: reuse a running receiver, otherwise start this project."""
import os
import runpy
import sys
import urllib.request
from pathlib import Path

root=Path(__file__).resolve().parent
def running():
    try:
        import json
        with urllib.request.urlopen('http://127.0.0.1:8765/health',timeout=2) as response:
            return json.load(response).get('service')=='pmo-local'
    except Exception:return False

if running():
    print('PMO is already running. Open http://127.0.0.1:8766/ for the project dashboard.')
    print('No duplicate service or database has been created.')
else:
    os.chdir(root)
    sys.path.insert(0,str(root))
    runpy.run_path(str(root/'start.py'),run_name='__main__')
