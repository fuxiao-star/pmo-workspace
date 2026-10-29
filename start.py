"""Start the database receiver and a temporary HTTPS tunnel. Ctrl+C stops both."""
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
import server

def main():
    public,admin=server.start()
    state=server.DATA/'connection.json'
    state.write_text('{}',encoding='utf-8')
    executable=server.ROOT/'bin'/'cloudflared.exe'
    if not executable.exists():
        print('cloudflared.exe is missing. See README.md.',flush=True)
        return 1
    child=subprocess.Popen([str(executable),'tunnel','--no-autoupdate','--url',f'http://127.0.0.1:{server.PUBLIC_PORT}','--protocol','http2'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    def monitor():
        for line in child.stdout:
            match=re.search(r'https://[a-z0-9-]+\.trycloudflare\.com',line)
            if match:
                url=match.group(0)
                state.write_text(json.dumps({'url':url,'startedAt':time.time()}),encoding='utf-8')
                print('Share website: '+url,flush=True)
            if 'Registered tunnel connection' in line:
                print('HTTPS tunnel connected.',flush=True)
        state.write_text('{}',encoding='utf-8')
        print('Tunnel stopped. Reports already received remain in the database.',flush=True)
    threading.Thread(target=monitor,daemon=True).start()
    print(f'PMO admin: http://127.0.0.1:{server.ADMIN_PORT}',flush=True)
    print('Keep this process running. Open the local admin page to create group codes.',flush=True)
    try:
        while child.poll() is None: time.sleep(1)
    except KeyboardInterrupt: pass
    finally:
        child.terminate()
        try: child.wait(timeout=10)
        except subprocess.TimeoutExpired: child.kill()
        public.shutdown();admin.shutdown()
        state.write_text('{}',encoding='utf-8')
    return 0

if __name__=='__main__': sys.exit(main())
