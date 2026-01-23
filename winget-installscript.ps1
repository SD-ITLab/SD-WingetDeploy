[CmdletBinding()]
param(
    [switch] $SetupWinget,
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]] $Apps
)

# =====================================================================
# Global Settings – Speed & Network
# =====================================================================

$ErrorActionPreference = 'Stop'
$ProgressPreference    = 'SilentlyContinue'
$PSDefaultParameterValues['Invoke-WebRequest:UseBasicParsing'] = $true
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

# =====================================================================
# GitHub: aktuellstes WinGet-Release (Bundle + Dependencies.zip)
# =====================================================================

function Get-WingetLatestReleaseAssets {
    [CmdletBinding()]
    param()

    $releasesUrl = 'https://api.github.com/repos/microsoft/winget-cli/releases/latest'
    Write-Host "INFO  - Querying latest WinGet release from GitHub..." 

    $release = Invoke-RestMethod -Uri $releasesUrl

    $bundleAsset = $release.assets |
        Where-Object { $_.browser_download_url.EndsWith('msixbundle') } |
        Select-Object -First 1

    $depsAsset = $release.assets |
        Where-Object { $_.name -eq 'DesktopAppInstaller_Dependencies.zip' } |
        Select-Object -First 1

    if (-not $bundleAsset) {
        throw "No MSIX bundle found in latest winget release."
    }
    if (-not $depsAsset) {
        throw "No DesktopAppInstaller_Dependencies.zip found in latest winget release."
    }

    Write-Host "INFO  - Latest WinGet tag: $($release.tag_name)"
    Write-Host "INFO  - Bundle: $($bundleAsset.name)"
    Write-Host "INFO  - Deps  : $($depsAsset.name)"

    return [pscustomobject]@{
        BundleUrl = $bundleAsset.browser_download_url
        DepsUrl   = $depsAsset.browser_download_url
        Tag       = $release.tag_name
    }
}

# =====================================================================
# Dependencies aus DesktopAppInstaller_Dependencies.zip installieren
# (VCLibs + UWPDesktop + WindowsAppRuntime 1.8)
# =====================================================================

function Install-WingetDependencies {
    Write-Host "INFO  - Installing WinGet dependencies (VCLibs + UWPDesktop + WindowsAppRuntime)..."

    $assets = Get-WingetLatestReleaseAssets

    $tempRoot = Join-Path $env:TEMP "WingetSetup-Dependencies"
    if (Test-Path $tempRoot) {
        Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue | Out-Null
    }
    New-Item $tempRoot -ItemType Directory -Force | Out-Null

    $zipPath  = Join-Path $tempRoot "DesktopAppInstaller_Dependencies.zip"
    $depsRoot = Join-Path $tempRoot "deps"

    try {
        Write-Host "INFO  - Downloading dependencies zip..."
        Invoke-WebRequest -Uri $assets.DepsUrl -OutFile $zipPath

        if (-not (Test-Path $zipPath)) {
            throw "Dependencies zip was not downloaded correctly."
        }

        Expand-Archive -Path $zipPath -DestinationPath $depsRoot -Force

        $x64Dir = Join-Path $depsRoot "x64"
        if (-not (Test-Path $x64Dir)) {
            throw "x64 directory not found in dependencies zip."
        }

        $appxFiles = Get-ChildItem -Path $x64Dir -Filter '*.appx' | Sort-Object Name

        foreach ($file in $appxFiles) {
            Write-Host "INFO  - Installing dependency: $($file.Name)"
            try {
                Add-AppxPackage -Path $file.FullName -ErrorAction Stop
                Write-Host "OK    - Dependency installed/updated: $($file.Name)"
            }
            catch {
                $text = $_ | Out-String
                Write-Host "WARN  - Failed to install dependency $($file.Name):"
                Write-Host $text
                throw
            }
        }

        Write-Host "OK    - All dependencies from dependencies zip processed."
    }
    finally {
        Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue | Out-Null
    }
}

# =====================================================================
# WinGet / DesktopAppInstaller installieren oder aktualisieren
# =====================================================================

function Install-WingetCli {
    Write-Host "INFO  - Checking WinGet / DesktopAppInstaller..."

    $pkgFamily        = 'Microsoft.DesktopAppInstaller_8wekyb3d8bbwe'
    $minWingetVersion = [version]"1.12.0.0"

    # 1) Aktuelle WinGet-Version prüfen
    $needInstall = $true
    try {
        $raw = winget --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $raw) {
            $verString = ($raw | Select-Object -First 1).Trim().TrimStart('v','V')
            $ver = [version]$verString
            Write-Host "INFO  - Current WinGet version: $ver"

            if ($ver -ge $minWingetVersion) {
                Write-Host "OK    - WinGet is already up to date (>= $minWingetVersion)."
                $needInstall = $false
            }
            else {
                Write-Host "WARN  - WinGet is too old (v$ver < $minWingetVersion) – updating..."
            }
        }
        else {
            Write-Host "INFO  - WinGet not callable (exitcode $LASTEXITCODE) – will install."
        }
    }
    catch {
        Write-Host "WARN  - Error while checking WinGet version – will install:"
        Write-Host ($_ | Out-String)
    }

    if (-not $needInstall) { return }

    # 2) Bundle herunterladen und lokal installieren
    $assets = Get-WingetLatestReleaseAssets

    $tempRoot = Join-Path $env:TEMP "WingetSetup-Bundle"
    if (Test-Path $tempRoot) {
        Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue | Out-Null
    }
    New-Item $tempRoot -ItemType Directory -Force | Out-Null

    $bundlePath = Join-Path $tempRoot "DesktopAppInstaller_latest.msixbundle"

    try {
        Write-Host "INFO  - Downloading DesktopAppInstaller bundle..."
        Invoke-WebRequest -Uri $assets.BundleUrl -OutFile $bundlePath

        if (-not (Test-Path $bundlePath)) {
            throw "Bundle msixbundle was not downloaded correctly."
        }

        Write-Host "INFO  - Installing DesktopAppInstaller/WinGet bundle..."
        Add-AppxPackage -Path $bundlePath -ErrorAction Stop
        Write-Host "OK    - DesktopAppInstaller bundle installed."

        # nach der Bundle-Installation WinGet/Store-App für den Benutzer registrieren (falls nötig)
        try {
            Add-AppxPackage -RegisterByFamilyName -MainPackage $pkgFamily -ErrorAction Stop
            Write-Host "OK    - WinGet registration requested after bundle installation."
        }
        catch {
            Write-Host "WARN  - Failed to register WinGet after bundle installation:"
            Write-Host ($_ | Out-String)
        }
    }
    finally {
        Remove-Item $tempRoot -Recurse -Force -ErrorAction SilentlyContinue | Out-Null
    }

    # 3) Version nach Installation nochmal prüfen
    try {
        Start-Sleep -Seconds 3
        $raw2 = winget --version 2>&1
        if ($LASTEXITCODE -eq 0 -and $raw2) {
            $verString2 = ($raw2 | Select-Object -First 1).Trim().TrimStart('v','V')
            $ver2 = [version]$verString2
            Write-Host "OK    - WinGet CLI now reports: $ver2"

            if ($ver2 -lt $minWingetVersion) {
                Write-Host "WARN  - WinGet version after install still below required $minWingetVersion."
            }
        }
        else {
            Write-Host "WARN  - WinGet still not callable after install (exitcode $LASTEXITCODE)."
        }
    }
    catch {
        Write-Host "WARN  - Error while checking WinGet version after install:"
        Write-Host ($_ | Out-String)
    }
}

# =====================================================================
# Apps via winget installieren (für -Apps ...)
# =====================================================================

function Invoke-WingetInstallForApps {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $AppIds
    )

    $wingetCmd = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $wingetCmd) {
        Write-Host "ERROR - winget command not found. Please run with -SetupWinget first."
        exit 1
    }

    $failedApps = @()
    $overallFailed = 0
    $total = $AppIds.Count
    $index = 0

    foreach ($id in $AppIds) {
        if ([string]::IsNullOrWhiteSpace($id)) { continue }
        $index++

        Write-Host "INFO  - [$index/$total] Installing app via winget: $id"

        $args = @(
            "install",
            "--id", $id,
            "--accept-source-agreements",
            "--accept-package-agreements",
            "--silent",
            "--disable-interactivity"
        )

        $proc = Start-Process -FilePath $wingetCmd.Source -ArgumentList $args -NoNewWindow -PassThru -Wait

        if ($proc.ExitCode -eq 0) {
            Write-Host "OK    - App installed successfully: $id"
        }
        else {
            Write-Host "ERROR - App installation failed for '$id' with exit code $($proc.ExitCode). Skipping and continuing..."
            $overallFailed++
            $failedApps += $id
        }
    }

    if ($overallFailed -gt 0) {
        $list = $failedApps -join ", "
        Write-Host "FAILED_APPS: $list"
        exit 1
    }
    else {
        Write-Host "OK    - All selected apps installed successfully."
        exit 0
    }
}

# =====================================================================
# Main
# =====================================================================

if ($SetupWinget.IsPresent) {
    Write-Host "INFO  - Running in SetupWinget mode."
    Install-WingetDependencies
    Install-WingetCli
    Write-Host "OK    - SetupWinget completed."
}
elseif ($Apps -and $Apps.Count -gt 0) {
    Write-Host "INFO  - Running in Apps-install mode for $($Apps.Count) app(s)."
    Invoke-WingetInstallForApps -AppIds $Apps
}
else {
    Write-Host "ERROR - No valid parameters provided. Use -SetupWinget or -Apps <ids>."
    exit 1
}
