<#
.SYNOPSIS
    Runs the full reconcile -> three-report pipeline for one property/client export.

.DESCRIPTION
    Generic wrapper around reconcile.py + generate_brief.js + fact_sheet/build_fact_sheet.js
    + collateral_summary/build_collateral_summary.js. Not tied to any one client -- pass in
    the CSV for whichever client/export you're working on.

.EXAMPLE
    .\run_client_reports.ps1 `
        -Csv "G:\My Drive\Newtree Capital Resources\Clients\Stephanie Spurgat\lpp-export-442892e4-ee99-4aae-8312-2d3c8057396e\lpp-export-442892e4-ee99-4aae-8312-2d3c8057396e.csv"

.EXAMPLE
    .\run_client_reports.ps1 -Csv $csv -OutDir $outDir -IncludeContactInfo

.EXAMPLE
    # Also emit PDFs (converted from the docx via LibreOffice headless -- this
    # renders the tables correctly, unlike Google Docs' own docx importer).
    .\run_client_reports.ps1 -Csv $csv -Pdf
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Csv,

    # Defaults to the CSV's own folder -- lpp-export-<uuid> folders are self-contained,
    # so outputs land next to the source CSV unless you say otherwise.
    [string]$OutDir,

    [string]$CompanyName = "Newtree Capital Resources LLC",

    [switch]$IncludeContactInfo,

    # Also convert each generated docx to PDF via LibreOffice headless.
    [switch]$Pdf
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path $Csv)) {
    throw "CSV not found: $Csv"
}

if (-not $OutDir) {
    $OutDir = Split-Path -Parent $Csv
}

if (-not (Test-Path $OutDir)) {
    throw "Output directory not found: $OutDir"
}

function Find-Soffice {
    $cmd = Get-Command soffice -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    foreach ($candidate in @(
        "C:\Program Files\LibreOffice\program\soffice.exe",
        "C:\Program Files (x86)\LibreOffice\program\soffice.exe"
    )) {
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

$reconciled = Join-Path $OutDir "reconciled.json"
$contactArg = if ($IncludeContactInfo) { @("--include-contact-info") } else { @() }
$docxPaths = @()

python reconcile.py --csv "$Csv" --out "$reconciled"
if (-not $?) { throw "reconcile.py failed" }

$brief = Join-Path $OutDir "01_Investment_Opportunity_Brief.docx"
node generate_brief.js $reconciled $brief $CompanyName @contactArg
if (-not $?) { throw "generate_brief.js failed" }
$docxPaths += $brief

$factSheet = Join-Path $OutDir "02_Property_Fact_Sheet.docx"
node fact_sheet/build_fact_sheet.js $reconciled $factSheet $CompanyName @contactArg
if (-not $?) { throw "build_fact_sheet.js failed" }
$docxPaths += $factSheet

$collateral = Join-Path $OutDir "03_Loan_Collateral_Summary.docx"
node collateral_summary/build_collateral_summary.js $reconciled $collateral $CompanyName @contactArg
if (-not $?) { throw "build_collateral_summary.js failed" }
# Only produced when reconcile.py had enough data to compute collateral_analysis --
# the generator exits without writing a file otherwise, so don't assume it's there.
if (Test-Path $collateral) { $docxPaths += $collateral }

if ($Pdf) {
    $soffice = Find-Soffice
    if (-not $soffice) {
        Write-Warning "LibreOffice (soffice) not found -- skipping PDF conversion. Install it or pass its path via PATH."
    } else {
        foreach ($docxPath in $docxPaths) {
            & $soffice --headless --convert-to pdf --outdir "$OutDir" "$docxPath" | Out-Null
            if (-not $?) { throw "PDF conversion failed for $docxPath" }
        }
    }
}

Write-Host "ALL DONE -- reports written to $OutDir"
