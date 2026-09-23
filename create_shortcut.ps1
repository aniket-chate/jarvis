
$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut('C:\Users\acer\Desktop\Google Chrome (Debugging).lnk')
$Shortcut.TargetPath = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
$Shortcut.Arguments = '--remote-debugging-port=9222 --user-data-dir="C:\Users\acer\chrome-debug-profile" http://127.0.0.1:8000/'
$Shortcut.Save()
