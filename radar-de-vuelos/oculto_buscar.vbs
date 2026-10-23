' Corre una busqueda del radar sin ventana
Set fso = CreateObject("Scripting.FileSystemObject")
dir = fso.GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run "cmd /c """ & dir & "\2_buscar_ahora.bat""", 0, False
