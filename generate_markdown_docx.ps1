param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Escape-Xml {
    param([string]$Text)

    if ($null -eq $Text) {
        return ""
    }

    return [System.Security.SecurityElement]::Escape($Text)
}

function New-RunXml {
    param(
        [string]$Text,
        [int]$Size,
        [string]$Color,
        [bool]$Bold = $false
    )

    $escaped = Escape-Xml $Text
    $boldXml = if ($Bold) { "<w:b/><w:bCs/>" } else { "" }

    return @"
<w:r>
  <w:rPr>
    <w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:eastAsia="Microsoft YaHei"/>
    $boldXml
    <w:color w:val="$Color"/>
    <w:sz w:val="$Size"/>
    <w:szCs w:val="$Size"/>
  </w:rPr>
  <w:t xml:space="preserve">$escaped</w:t>
</w:r>
"@
}

function New-ParagraphXml {
    param(
        [string]$Text,
        [string]$Kind = "body"
    )

    switch ($Kind) {
        "title" {
            $size = 34
            $color = "1A3C5E"
            $bold = $true
            $spacing = '<w:spacing w:before="260" w:after="160"/>'
            $alignment = '<w:jc w:val="center"/>'
            $indent = ""
            $content = $Text
        }
        "subtitle" {
            $size = 22
            $color = "555555"
            $bold = $false
            $spacing = '<w:spacing w:before="20" w:after="80"/>'
            $alignment = '<w:jc w:val="center"/>'
            $indent = ""
            $content = $Text
        }
        "h1" {
            $size = 28
            $color = "1A3C5E"
            $bold = $true
            $spacing = '<w:spacing w:before="320" w:after="120"/>'
            $alignment = ""
            $indent = ""
            $content = $Text
        }
        "h2" {
            $size = 24
            $color = "2E75B6"
            $bold = $true
            $spacing = '<w:spacing w:before="180" w:after="80"/>'
            $alignment = ""
            $indent = ""
            $content = $Text
        }
        "bullet" {
            $size = 22
            $color = "1A1A1A"
            $bold = $false
            $spacing = '<w:spacing w:before="20" w:after="40"/>'
            $alignment = ""
            $indent = '<w:ind w:left="360"/>'
            $content = "- $Text"
        }
        "flow" {
            $size = 21
            $color = "4F5B66"
            $bold = $false
            $spacing = '<w:spacing w:before="20" w:after="30"/>'
            $alignment = ""
            $indent = '<w:ind w:left="360"/>'
            $content = $Text
        }
        "note" {
            $size = 20
            $color = "666666"
            $bold = $false
            $spacing = '<w:spacing w:before="20" w:after="40"/>'
            $alignment = ""
            $indent = ""
            $content = $Text
        }
        "blank" {
            return "<w:p/>"
        }
        "pagebreak" {
            return @"
<w:p>
  <w:r>
    <w:br w:type="page"/>
  </w:r>
</w:p>
"@
        }
        default {
            $size = 22
            $color = "1A1A1A"
            $bold = $false
            $spacing = '<w:spacing w:before="20" w:after="50"/>'
            $alignment = ""
            $indent = ""
            $content = $Text
        }
    }

    $runXml = New-RunXml -Text $content -Size $size -Color $color -Bold $bold

    return @"
<w:p>
  <w:pPr>
    $spacing
    $alignment
    $indent
  </w:pPr>
  $runXml
</w:p>
"@
}

function Get-ParagraphKind {
    param(
        [string]$Line,
        [int]$Index
    )

    if ([string]::IsNullOrWhiteSpace($Line)) {
        return @{ Kind = "blank"; Text = "" }
    }

    if ($Line -eq "!PAGEBREAK") {
        return @{ Kind = "pagebreak"; Text = "" }
    }

    if ($Line.StartsWith("# ")) {
        return @{ Kind = "title"; Text = $Line.Substring(2) }
    }

    if ($Line.StartsWith("## ")) {
        return @{ Kind = "h1"; Text = $Line.Substring(3) }
    }

    if ($Line.StartsWith("### ")) {
        return @{ Kind = "h2"; Text = $Line.Substring(4) }
    }

    if ($Line.StartsWith("- ")) {
        return @{ Kind = "bullet"; Text = $Line.Substring(2) }
    }

    if ($Line.StartsWith("> ")) {
        return @{ Kind = "flow"; Text = $Line.Substring(2) }
    }

    if ($Index -lt 4) {
        return @{ Kind = "subtitle"; Text = $Line }
    }

    return @{ Kind = "body"; Text = $Line }
}

function New-DocumentXml {
    param([string[]]$Lines)

    $paragraphs = New-Object System.Collections.Generic.List[string]

    for ($i = 0; $i -lt $Lines.Count; $i++) {
        $parsed = Get-ParagraphKind -Line $Lines[$i] -Index $i
        $paragraphs.Add((New-ParagraphXml -Text $parsed.Text -Kind $parsed.Kind))
    }

    $bodyXml = ($paragraphs -join "`n")

    return @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:wpc="http://schemas.microsoft.com/office/word/2010/wordprocessingCanvas"
            xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006"
            xmlns:o="urn:schemas-microsoft-com:office:office"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
            xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"
            xmlns:v="urn:schemas-microsoft-com:vml"
            xmlns:wp14="http://schemas.microsoft.com/office/word/2010/wordprocessingDrawing"
            xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
            xmlns:w10="urn:schemas-microsoft-com:office:word"
            xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
            xmlns:wpg="http://schemas.microsoft.com/office/word/2010/wordprocessingGroup"
            xmlns:wpi="http://schemas.microsoft.com/office/word/2010/wordprocessingInk"
            xmlns:wne="http://schemas.microsoft.com/office/word/2006/wordml"
            xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"
            mc:Ignorable="w14 wp14">
  <w:body>
$bodyXml
    <w:sectPr>
      <w:pgSz w:w="11906" w:h="16838"/>
      <w:pgMar w:top="1417" w:right="1417" w:bottom="1417" w:left="1417" w:header="720" w:footer="720" w:gutter="0"/>
      <w:cols w:space="720"/>
      <w:docGrid w:linePitch="360"/>
    </w:sectPr>
  </w:body>
</w:document>
"@
}

function New-CoreXml {
    param([string]$Title)

    $now = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $escapedTitle = Escape-Xml $Title

    return @"
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/"
                   xmlns:dcterms="http://purl.org/dc/terms/"
                   xmlns:dcmitype="http://purl.org/dc/dcmitype/"
                   xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <dc:title>$escapedTitle</dc:title>
  <dc:subject>Photography Agent Product Design</dc:subject>
  <dc:creator>Codex</dc:creator>
  <cp:keywords>photography, agent, product design</cp:keywords>
  <dc:description>Generated from markdown source</dc:description>
  <cp:lastModifiedBy>Codex</cp:lastModifiedBy>
  <cp:revision>1</cp:revision>
  <dcterms:created xsi:type="dcterms:W3CDTF">$now</dcterms:created>
  <dcterms:modified xsi:type="dcterms:W3CDTF">$now</dcterms:modified>
  <cp:category>Product Document</cp:category>
</cp:coreProperties>
"@
}

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$templateDir = Join-Path $repoRoot "unpacked_doc"
$resolvedSource = Resolve-Path -LiteralPath $SourcePath
$resolvedOutput = [System.IO.Path]::GetFullPath((Join-Path $repoRoot $OutputPath))
$outputDir = Split-Path -Parent $resolvedOutput

if (-not (Test-Path -LiteralPath $templateDir)) {
    throw "Template directory not found: $templateDir"
}

if (-not (Test-Path -LiteralPath $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
}

$lines = Get-Content -LiteralPath $resolvedSource -Encoding UTF8
$title = ($lines | Where-Object { $_ -like "# *" } | Select-Object -First 1)
if ($null -eq $title) {
    $title = "# Generated Document"
}
$titleText = $title.Substring(2)

$documentXml = New-DocumentXml -Lines $lines
$coreXml = New-CoreXml -Title $titleText

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("docx_" + [System.Guid]::NewGuid().ToString("N"))
$packageDir = Join-Path $tempRoot "package"
$zipPath = Join-Path $tempRoot "package.zip"

New-Item -ItemType Directory -Path $packageDir -Force | Out-Null
Copy-Item -LiteralPath $templateDir -Destination $packageDir -Recurse -Force

$workingDir = Join-Path $packageDir (Split-Path -Leaf $templateDir)
Set-Content -LiteralPath (Join-Path $workingDir "word\document.xml") -Value $documentXml -Encoding UTF8
Set-Content -LiteralPath (Join-Path $workingDir "docProps\core.xml") -Value $coreXml -Encoding UTF8

$itemsToArchive = Get-ChildItem -LiteralPath $workingDir -Force | ForEach-Object { $_.FullName }

if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
}

Compress-Archive -LiteralPath $itemsToArchive -DestinationPath $zipPath -CompressionLevel Optimal

if (Test-Path -LiteralPath $resolvedOutput) {
    Remove-Item -LiteralPath $resolvedOutput -Force
}

Move-Item -LiteralPath $zipPath -Destination $resolvedOutput
Remove-Item -LiteralPath $tempRoot -Recurse -Force

Write-Output "Generated: $resolvedOutput"
