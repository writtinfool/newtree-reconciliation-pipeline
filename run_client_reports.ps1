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
#>

param(
    [Parameter(Mandatory = $true)]
    [string]$Csv,

    # Defaults to the CSV's own folder -- lpp-export-<uuid> folders are self-contained,
    # so outputs land next to the source CSV unless you say otherwise.
    [string]$OutDir,

    [string]$CompanyName = "Newtree Capital Resources LLC",

    [switch]$IncludeContactInfo
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

$reconciled = Join-Path $OutDir "reconciled.json"
$contactArg = if ($IncludeContactInfo) { @("--include-contact-info") } else { @() }

python reconcile.py --csv "$Csv" --out "$reconciled"
if (-not $?) { throw "reconcile.py failed" }

node generate_brief.js $reconciled (Join-Path $OutDir "01_Investment_Opportunity_Brief.docx") $CompanyName @contactArg
if (-not $?) { throw "generate_brief.js failed" }

node fact_sheet/build_fact_sheet.js $reconciled (Join-Path $OutDir "02_Property_Fact_Sheet.docx") $CompanyName @contactArg
if (-not $?) { throw "build_fact_sheet.js failed" }

node collateral_summary/build_collateral_summary.js $reconciled (Join-Path $OutDir "03_Loan_Collateral_Summary.docx") $CompanyName @contactArg
if (-not $?) { throw "build_collateral_summary.js failed" }

Write-Host "ALL DONE -- reports written to $OutDir"
