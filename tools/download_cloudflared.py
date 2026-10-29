"""Optional download of the official Cloudflare Windows x64 tunnel executable."""
import os
import shutil
import urllib.request
from pathlib import Path

if os.name!='nt': raise SystemExit('Windows x64 helper. For other platforms, use Cloudflare official downloads.')
target=Path(__file__).resolve().parent.parent/'bin'/'cloudflared.exe'
if target.exists(): raise SystemExit('cloudflared already exists; not overwritten.')
target.parent.mkdir(parents=True,exist_ok=True)
temporary=target.with_suffix('.download')
try:
    with urllib.request.urlopen('https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe',timeout=60) as src,temporary.open('wb') as dst: shutil.copyfileobj(src,dst)
    temporary.replace(target)
except Exception:
    temporary.unlink(missing_ok=True)
    raise
print('Downloaded official executable to bin/cloudflared.exe; verify --version before use.')
