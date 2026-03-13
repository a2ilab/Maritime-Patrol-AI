# Maritime Patrol AI - 서버 재구동 스크립트
# PowerShell에서 실행: .\restart_servers.ps1

$ErrorActionPreference = "Continue"

Write-Host "=== 기존 서버 프로세스 종료 ===" -ForegroundColor Yellow
$ports = @(8000, 8502)
$pidsToKill = @()

foreach ($port in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        $pidsToKill += $c.OwningProcess
    }
}

$pidsToKill = $pidsToKill | Select-Object -Unique
foreach ($p in $pidsToKill) {
    try {
        Stop-Process -Id $p -Force -ErrorAction Stop
        Write-Host "  종료: PID $p" -ForegroundColor Gray
    } catch {}
}

Start-Sleep -Seconds 3

# 포트 해제 확인
$stillListening = Get-NetTCPConnection -LocalPort 8000,8502 -State Listen -ErrorAction SilentlyContinue
if ($stillListening) {
    Write-Host "경고: 일부 포트가 아직 사용 중입니다. 관리자 권한으로 다시 시도하거나, 작업 관리자에서 python 프로세스를 수동 종료해 주세요." -ForegroundColor Red
} else {
    Write-Host "포트 해제 완료." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== 서버 시작 ===" -ForegroundColor Yellow
Write-Host "API 서버: http://127.0.0.1:8000" -ForegroundColor Cyan
Write-Host "Map Viewer: http://127.0.0.1:8502" -ForegroundColor Cyan
Write-Host ""
Write-Host "두 개의 새 터미널 창에서 각각 실행하세요:" -ForegroundColor White
Write-Host "  1) cd D:\Git\Maritime-Patrol-AI-master && py api.py" -ForegroundColor Gray
Write-Host "  2) cd D:\Git\Maritime-Patrol-AI-master\map-viewer && py run.py" -ForegroundColor Gray
Write-Host ""
