# Renderlab installer for Windows (PowerShell 5.1 or 7+).
#
#   irm https://raw.githubusercontent.com/raiton0902/renderlab/main/install.ps1 | iex
#   & ([scriptblock]::Create((irm .../install.ps1))) -Claude
param(
  [string]$Dir,
  [switch]$Claude,
  [switch]$Force
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$repo = "raiton0902/renderlab"
$ref = if ($env:RENDERLAB_REF) { $env:RENDERLAB_REF } else { "main" }
$name = "renderlab"

if ($Dir) {
  $dest = $Dir
} elseif ($Claude) {
  $dest = Join-Path $HOME ".claude\skills\$name"
} else {
  $dest = Join-Path $HOME ".dsh\skills\$name"
}
$dest = [System.IO.Path]::GetFullPath($dest)

if ((Test-Path $dest) -and -not $Force) {
  Write-Host "renderlab: already installed at $dest"
  Write-Host "Add -Force to replace it, or -Dir to install somewhere else."
  exit 1
}

$tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("renderlab-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null

try {
  $url = "https://codeload.github.com/$repo/zip/refs/heads/$ref"
  $zip = Join-Path $tmp "pkg.zip"
  Write-Host "Downloading $repo ($ref)..."
  Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
  Expand-Archive -Path $zip -DestinationPath $tmp -Force

  $src = Get-ChildItem -Path $tmp -Directory -Filter "renderlab-*" |
    Select-Object -First 1
  if (-not $src) { throw "download did not contain the package" }

  if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
  New-Item -ItemType Directory -Path $dest -Force | Out-Null

  foreach ($item in @("SKILL.md", "README.md", "LICENSE", "scripts", "assets", "references")) {
    $from = Join-Path $src.FullName $item
    if (Test-Path $from) {
      Copy-Item $from -Destination (Join-Path $dest $item) -Recurse -Force
    }
  }

  Write-Host "renderlab installed -> $dest"
  Write-Host ""
  Write-Host "Next steps:"
  Write-Host "  1. Restart your agent (or reload skills) so it picks up the new folder."
  Write-Host '  2. Ask: "edit this video and render it using /Renderlab".'
  Write-Host ""
  Write-Host "Docs: https://github.com/raiton0902/renderlab"
}
finally {
  Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
