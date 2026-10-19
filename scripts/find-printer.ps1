<#
.SYNOPSIS
  Finds network receipt printers (ESC/POS, raw port 9100) on your local network.

.DESCRIPTION
  Most LAN/Wi-Fi thermal printers listen on TCP port 9100. This script tries that
  port on every address of your local /24 network(s) and lists the ones that
  answer, together with the MAC address / hostname when Windows knows it.

  Run it on a PC connected to the SAME Wi-Fi/LAN as the printer:

      powershell -ExecutionPolicy Bypass -File scripts\find-printer.ps1

  Use the IP it prints in  Settings -> Printers -> Add  (port 9100).
  Tip: a printer's IP can change after a router restart. Give it a fixed
  ("static" / "reserved") address in the printer's settings or the router.

.PARAMETER Port
  TCP port to probe (default 9100).

.PARAMETER Subnet
  Scan this /24 prefix instead of auto-detecting, e.g. -Subnet 192.168.1
#>
param(
    [int]$Port = 9100,
    [string]$Subnet = ""
)

$ErrorActionPreference = "Stop"

function Get-Prefixes {
    if ($Subnet) { return @($Subnet.TrimEnd('.')) }
    $prefixes = @()
    $addresses = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" -and $_.PrefixOrigin -ne "WellKnown" }
    foreach ($a in $addresses) {
        $octets = $a.IPAddress.Split(".")
        $p = ($octets[0..2] -join ".")
        # Only private ranges: never port-scan public address space.
        if ($a.IPAddress -match "^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[0-1])\.)") { $prefixes += $p }
    }
    return $prefixes | Select-Object -Unique
}

$prefixes = Get-Prefixes
if (-not $prefixes) {
    Write-Host "No private network detected. Connect to the restaurant's Wi-Fi/LAN, or pass -Subnet 192.168.1" -ForegroundColor Yellow
    exit 1
}

$found = @()
foreach ($prefix in $prefixes) {
    Write-Host "Scanning $prefix.1 - $prefix.254 on port $Port ..." -ForegroundColor Cyan
    $probes = foreach ($i in 1..254) {
        $client = New-Object System.Net.Sockets.TcpClient
        [pscustomobject]@{ Ip = "$prefix.$i"; Client = $client; Task = $client.ConnectAsync("$prefix.$i", $Port) }
    }
    # All 254 connections run in parallel; give them a moment to answer.
    $deadline = (Get-Date).AddSeconds(3)
    while ((Get-Date) -lt $deadline -and ($probes | Where-Object { -not $_.Task.IsCompleted })) {
        Start-Sleep -Milliseconds 100
    }
    foreach ($p in $probes) {
        if ($p.Task.IsCompleted -and -not $p.Task.IsFaulted -and -not $p.Task.IsCanceled -and $p.Client.Connected) {
            $found += $p.Ip
        }
        $p.Client.Dispose()
    }
}

if (-not $found) {
    Write-Host ""
    Write-Host "No device answered on port $Port." -ForegroundColor Yellow
    Write-Host "Check: the printer is on and on this same network; its network cable/Wi-Fi is connected;"
    Write-Host "print the printer's self-test page (usually: hold FEED while powering on) - it shows its IP."
    exit 2
}

$arp = arp -a 2>$null
Write-Host ""
Write-Host "Found $($found.Count) device(s) listening on port ${Port}:" -ForegroundColor Green
foreach ($ip in $found) {
    $mac = ($arp | Where-Object { $_ -match "^\s*$([regex]::Escape($ip))\s" } | ForEach-Object { ($_ -split "\s+")[2] } | Select-Object -First 1)
    $name = try { [System.Net.Dns]::GetHostEntry($ip).HostName } catch { "" }
    Write-Host ("  {0,-15}  MAC {1,-18} {2}" -f $ip, $mac, $name)
}
Write-Host ""
Write-Host "Enter that IP (port $Port) in SYNORA: Settings -> Printers -> Add." -ForegroundColor Green
