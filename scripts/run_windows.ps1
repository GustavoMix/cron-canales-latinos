$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m channelwatch run @args
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
