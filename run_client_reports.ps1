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
    [switch]$Pdf,

    # Which python to run reconcile.py with. Defaults to whatever "python" resolves
    # to on PATH -- but a fresh powershell.exe (e.g. one spawned by report_ui.py)
    # does its own independent PATH lookup and can land on a different install than
    # you expect if more than one Python is on this machine. Pass an explicit path
    # (or have a caller pass sys.executable) if you hit a ModuleNotFoundError here
    # that "python -c '...'" doesn't reproduce in your own shell.
    [string]$PythonExe = "python"
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

& $PythonExe -c "import pdfplumber" 2>$null
if (-not $?) {
    throw "pdfplumber is not installed for '$PythonExe' (resolved to $(& $PythonExe -c 'import sys; print(sys.executable)' 2>$null)). " +
          "Run: $PythonExe -m pip install --user pdfplumber -- or pass -PythonExe with the interpreter that has it."
}

& $PythonExe reconcile.py --csv "$Csv" --out "$reconciled"
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
# Exits non-zero (by design, not an error) when reconcile.py didn't have enough data
# to compute collateral_analysis -- a loan balance AND at least one valuation basis.
# Only treat it as a real failure if it also didn't produce the file.
if (-not $? -and -not (Test-Path $collateral)) {
    Write-Warning "build_collateral_summary.js: no collateral summary produced (insufficient data) -- see message above."
} elseif (Test-Path $collateral) {
    $docxPaths += $collateral
}

if ($Pdf -and $docxPaths.Count -gt 0) {
    $soffice = Find-Soffice
    if (-not $soffice) {
        Write-Warning "LibreOffice (soffice) not found -- skipping PDF conversion. Install it or pass its path via PATH."
    } else {
        # One invocation for all files, not one per file -- soffice --headless launches a
        # background instance that locks its user profile, so firing it off repeatedly in
        # a loop races on that lock and can silently no-op for all but the last file.
        #
        # Even a single invocation is flaky in practice -- soffice --headless has a known
        # habit of intermittently failing (busy profile lock, slow startup) when launched
        # right after a previous conversion, so retry a couple of times before giving up.
        $maxAttempts = 3
        for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
            & $soffice --headless --convert-to pdf --outdir "$OutDir" @docxPaths | Out-Null
            $allProduced = $true
            foreach ($docxPath in $docxPaths) {
                $expectedPdf = [System.IO.Path]::ChangeExtension($docxPath, ".pdf")
                if (-not (Test-Path $expectedPdf)) { $allProduced = $false }
            }
            if ($allProduced) { break }
            if ($attempt -lt $maxAttempts) {
                Write-Warning "PDF conversion attempt $attempt of $maxAttempts didn't produce all files -- retrying..."
                Start-Sleep -Seconds 3
            } else {
                throw "PDF conversion failed after $maxAttempts attempts"
            }
        }
    }
}

Write-Host "ALL DONE -- reports written to $OutDir"
