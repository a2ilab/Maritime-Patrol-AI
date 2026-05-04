# Maritime Patrol AI - 서버 재구동 및 캐시·모델 초기화
# .\restart_servers.ps1           서버 새 창에서 기동
# .\restart_servers.ps1 -NoStart   종료·초기화만

param(
    [switch]$NoStart
)

# UTF-8 콘솔 (Windows Terminal / PowerShell 호환)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Get-NetstatListenPids {
    param([int]$Port)
    $seen = New-Object System.Collections.Generic.HashSet[int]
    try {
        $lines = @(cmd /c "netstat -ano -p tcp" 2>$null)
        foreach ($raw in $lines) {
            $line = $raw.Trim()
            if ($line -notmatch '\bLISTENING\b') { continue }
            if ($line -notmatch ":$Port\s") { continue }
            $tokens = @($line -split '\s+' | Where-Object { $_ })
            if ($tokens.Count -lt 2) { continue }
            $last = [int]$tokens[-1]
            if ($last -gt 4) { [void]$seen.Add($last) }
        }
    } catch { }
    return $seen
}

function Stop-ProcessesOnPorts {
    param([int[]]$Ports)
    for ($attempt = 1; $attempt -le 15; $attempt++) {
        $pidsFound = New-Object System.Collections.Generic.HashSet[int]
        foreach ($port in $Ports) {
            foreach ($conn in @(Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue)) {
                $pidNum = [int]$conn.OwningProcess
                if ($pidNum -gt 4) { [void]$pidsFound.Add($pidNum) }
            }
            foreach ($pidNum in @(Get-NetstatListenPids -Port $port)) {
                [void]$pidsFound.Add($pidNum)
            }
        }
        if ($pidsFound.Count -eq 0) { break }
        foreach ($procId in $pidsFound) {
            try { & taskkill.exe /PID $procId /F /T 2>$null | Out-Null } catch { }
            try { Stop-Process -Id $procId -Force -ErrorAction Stop } catch { }
            Write-Host "  종료 시도 PID: $procId" -ForegroundColor Gray
        }
        Start-Sleep -Milliseconds 750
    }
}

Write-Host "=== 포트별 프로세스 종료 (8000, 8502) ===" -ForegroundColor Yellow
Stop-ProcessesOnPorts -Ports @(8000, 8502)

Start-Sleep -Seconds 1

$portsStillOccupied = $false
foreach ($listenPort in @(8000, 8502)) {
    $n = @(Get-NetTCPConnection -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue)
    $statIds = @(Get-NetstatListenPids -Port $listenPort)
    if (($n.Count -gt 0) -or ($statIds.Count -gt 0)) {
        $portsStillOccupied = $true
        break
    }
}
if ($portsStillOccupied) {
    Write-Host "경고: 일부 포트가 아직 리스닝 중입니다. map-viewer / uvicorn 관련 프로세스를 추가로 종료합니다." -ForegroundColor Red
    try {
        $procs = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
            $cmd = $_.CommandLine
            if (-not $cmd) { return $false }
            if ($cmd -notmatch '(?i)(python\.exe|py\.exe)') { return $false }
            if ($cmd -notmatch '(?i)Maritime-Patrol-AI') { return $false }
            if ($cmd -notmatch '(?i)map-viewer') { return $false }
            ($cmd -match '(?i)(run\.py|uvicorn|main:app)')
        }
        foreach ($wp in @($procs)) {
            $wpid = [int]$wp.ProcessId
            if ($wpid -le 4) { continue }
            & taskkill.exe /PID $wpid /F /T 2>$null | Out-Null
            Write-Host "  python/uvicorn 정리 PID: $wpid" -ForegroundColor Gray
        }
    } catch { }
    Start-Sleep -Seconds 1
}

$portsStillOccupiedAfter = $false
foreach ($listenPort in @(8000, 8502)) {
    $n = @(Get-NetTCPConnection -LocalPort $listenPort -State Listen -ErrorAction SilentlyContinue)
    $statIds = @(Get-NetstatListenPids -Port $listenPort)
    if (($n.Count -gt 0) -or ($statIds.Count -gt 0)) {
        $portsStillOccupiedAfter = $true
        break
    }
}
if ($portsStillOccupiedAfter) {
    Write-Host "경고: 8000/8502 에 리스너가 남아 있을 수 있습니다. 작업 관리자에서 python 프로세스를 확인하거나 관리자 권한으로 다시 실행해 보세요." -ForegroundColor Red
} elseif ($portsStillOccupied) {
    Write-Host "포트 추가 정리 후 해제 확인." -ForegroundColor Green
} else {
    Write-Host "포트 리스너 종료 확인." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== 캐시 / 학습 모델 초기화 ===" -ForegroundColor Yellow

$cacheCount = 0
Get-ChildItem -Path $projectRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    ForEach-Object {
        Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        $cacheCount++
    }
Write-Host "  __pycache__ 삭제: $cacheCount 디렉터리" -ForegroundColor Gray

$modelsDir = Join-Path $projectRoot "models"
if (Test-Path $modelsDir) {
    $modelFiles = @(Get-ChildItem -Path $modelsDir -Filter "*.npz" -ErrorAction SilentlyContinue)
    foreach ($f in $modelFiles) {
        Remove-Item $f.FullName -Force -ErrorAction SilentlyContinue
        Write-Host "  모델 삭제: $($f.Name)" -ForegroundColor Gray
    }
    if ($modelFiles.Count -eq 0) {
        Write-Host "  저장된 .npz 모델 없음" -ForegroundColor Gray
    }
} else {
    Write-Host "  models 디렉터리 없음" -ForegroundColor Gray
}

Write-Host "초기화 완료." -ForegroundColor Green

if ($NoStart) {
    Write-Host ""
    Write-Host "-NoStart: 서버는 기동하지 않았습니다." -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

Write-Host ""
Write-Host "=== 서버 시작 (별도 창) ===" -ForegroundColor Yellow
Write-Host "API: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Map Viewer: http://127.0.0.1:8502" -ForegroundColor Cyan
Write-Host ""

Start-Process -FilePath "py" -ArgumentList @("-3", "api.py") -WorkingDirectory $projectRoot -WindowStyle Normal
Start-Sleep -Seconds 2
Start-Process -FilePath "py" -ArgumentList @("-3", "run.py") -WorkingDirectory (Join-Path $projectRoot "map-viewer") -WindowStyle Normal

Write-Host "새 창에서 서버를 실행했습니다." -ForegroundColor Green
Write-Host ""
