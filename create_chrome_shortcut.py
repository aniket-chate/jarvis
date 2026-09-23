import os
import subprocess
from pathlib import Path

desktop = Path(os.path.expanduser("~/Desktop"))
target = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
shortcut_path = desktop / "Google Chrome (Debugging).lnk"
args = '--remote-debugging-port=9222 --user-data-dir="C:\\Users\\acer\\chrome-debug-profile" http://127.0.0.1:8000/'

ps_script = f"""
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('{str(shortcut_path)}')
$Shortcut.TargetPath = '{str(target)}'
$Shortcut.Arguments = '{args}'
$Shortcut.Save()
"""

ps_file = Path("d:/assignment/JARVIS/create_shortcut.ps1")
ps_file.write_text(ps_script, encoding="utf-8")

subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps_file)], check=True)
print("Shortcut successfully created at:", shortcut_path)
