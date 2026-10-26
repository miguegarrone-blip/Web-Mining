# Exporta informe-tp.docx y presentacion-tp.pptx a PDF con Word y PowerPoint (para verlos directo en GitHub).
# Uso, desde docs/_fuentes:  powershell -ExecutionPolicy Bypass -File exportar_pdf.ps1
# - Trabaja sobre copias temporales abiertas en solo lectura y sin dialogos: anda aunque los documentos esten abiertos.
# - Cada conversion corre en un Start-Job con limite de tiempo: lanzada directo (p. ej. desde bash) Word puede quedar
#   esperando sin avanzar; dentro de un job no. Si se pasa del limite, se cierra solo la instancia automatica de Office.
$docs = if ($PSScriptRoot) { (Resolve-Path (Join-Path $PSScriptRoot "..")).Path } else { (Resolve-Path "..").Path }

function Convertir($nombre, $bloque) {
    $job = Start-Job -ScriptBlock $bloque -ArgumentList $docs
    if (Wait-Job $job -Timeout 150) { Receive-Job $job }
    else {
        Stop-Job $job
        Get-CimInstance Win32_Process -Filter "Name='WINWORD.EXE' OR Name='POWERPNT.EXE'" |
            Where-Object { $_.CommandLine -like '*Embedding*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
        Write-Warning "$nombre`: Office no respondio en 150 s (probar de nuevo o cerrar Word/PowerPoint)"
    }
    Remove-Job $job -Force
}

Convertir "informe" {
    param($docs)
    $tmp = Join-Path $env:TEMP ("pdf_" + [guid]::NewGuid().ToString("N") + ".docx")
    Copy-Item (Join-Path $docs "informe-tp.docx") $tmp
    $w = New-Object -ComObject Word.Application; $w.Visible = $false; $w.DisplayAlerts = 0
    try {
        $d = $w.Documents.Open($tmp, $false, $true)                    # sin confirmar conversion, solo lectura
        $d.TablesOfContents | ForEach-Object { $_.Update() }          # el indice se completa al exportar
        # Word se traba si guarda directo en Documentos (aviso invisible de proteccion de carpetas): guarda en TEMP y se copia
        $pdf = [IO.Path]::ChangeExtension($tmp, ".pdf")
        $d.SaveAs2($pdf, 17)                                           # 17 = wdFormatPDF
        $d.Close(0); Copy-Item $pdf (Join-Path $docs "informe-tp.pdf") -Force; Remove-Item $pdf -Force
        "informe-tp.pdf listo"
    } finally { $w.Quit(); Remove-Item $tmp -Force }
}

Convertir "presentacion" {
    param($docs)
    $tmp = Join-Path $env:TEMP ("pdf_" + [guid]::NewGuid().ToString("N") + ".pptx")
    Copy-Item (Join-Path $docs "presentacion-tp.pptx") $tmp
    $p = New-Object -ComObject PowerPoint.Application
    try {
        $x = $p.Presentations.Open($tmp, $true, $false, $false)      # solo lectura, sin ventana
        $x.SaveAs((Join-Path $docs "presentacion-tp.pdf"), 32)        # 32 = ppSaveAsPDF
        $x.Close(); "presentacion-tp.pdf listo"
    } finally { $p.Quit(); Remove-Item $tmp -Force }
}
