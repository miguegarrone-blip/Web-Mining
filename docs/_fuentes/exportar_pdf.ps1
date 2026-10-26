# Exporta informe-tp.docx y presentacion-tp.pptx a PDF con Word y PowerPoint (para verlos directo en GitHub).
# Uso, desde docs/_fuentes:  powershell -ExecutionPolicy Bypass -File exportar_pdf.ps1
# Trabaja sobre copias temporales abiertas en solo lectura y sin dialogos: funciona aunque los documentos
# esten abiertos en Word o PowerPoint (si no, Word queda esperando un aviso invisible de "archivo en uso").
$docs = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$tmp = Join-Path $env:TEMP ("exportar_pdf_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory $tmp | Out-Null
Copy-Item (Join-Path $docs "informe-tp.docx"), (Join-Path $docs "presentacion-tp.pptx") $tmp

$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $d = $word.Documents.Open((Join-Path $tmp "informe-tp.docx"), $false, $true)   # sin confirmar conversion, solo lectura
    $d.TablesOfContents | ForEach-Object { $_.Update() }                        # el indice se completa al exportar
    $d.SaveAs2((Join-Path $docs "informe-tp.pdf"), 17)                          # 17 = wdFormatPDF
    $d.Close(0)
} finally { $word.Quit() }

$ppt = New-Object -ComObject PowerPoint.Application
try {
    $p = $ppt.Presentations.Open((Join-Path $tmp "presentacion-tp.pptx"), $true, $false, $false)   # solo lectura, sin ventana
    $p.SaveAs((Join-Path $docs "presentacion-tp.pdf"), 32)                      # 32 = ppSaveAsPDF
    $p.Close()
} finally { $ppt.Quit() }

Remove-Item $tmp -Recurse -Force
Write-Output "PDF generados en $docs"
