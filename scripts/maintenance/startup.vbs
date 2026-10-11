Set shell = CreateObject("WScript.Shell")
Set filesystem = CreateObject("Scripting.FileSystemObject")
watcher = filesystem.BuildPath(filesystem.GetParentFolderName(WScript.ScriptFullName), "watch-maj.sh")

shell.Run """C:\Program Files\Git\bin\bash.exe"" """ & watcher & """", 0, False
