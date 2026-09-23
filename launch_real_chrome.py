import subprocess
import sys
import time
import urllib.request

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE_DIR = r"C:\Users\acer\chrome-debug-profile"
URL = "http://127.0.0.1:8000/"

cmd = [
    CHROME_PATH,
    "--remote-debugging-port=9222",
    f"--user-data-dir={PROFILE_DIR}",
    "--no-first-run",
    "--no-default-browser-check",
    URL
]

DETACHED_PROCESS = 0x00000008
CREATE_NEW_PROCESS_GROUP = 0x00000200

p = subprocess.Popen(
    cmd,
    creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
    close_fds=True
)

print(f"Started Chrome process PID: {p.pid}")

# Wait and verify CDP is listening
success = False
for attempt in range(10):
    time.sleep(1)
    try:
        with urllib.request.urlopen("http://127.0.0.1:9222/json/version", timeout=2.0) as resp:
            data = resp.read().decode()
            print("CDP Connected successfully!")
            print(data)
            success = True
            break
    except Exception as e:
        print(f"Waiting for CDP (attempt {attempt+1}/10)... {e}")

if not success:
    sys.exit(1)

print("Real Chrome CDP server is running and standing by...")
# Keep parent alive so child process remains alive in background
p.wait()

