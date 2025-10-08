# =============================================================
# 🧠 BLACKOUT VAULTS – Auto Launcher (Backend + Frontend)
# =============================================================

# --- SETTINGS ---
$backendPath = "D:\HK-Backup\blackoutvaults-backend"
$frontendPath = "D:\HK-Backup\blackoutvaults-frontend"
$backendPort = 10000
$frontendPort = 3000
$refreshHours = 6
$restartDelaySec = 3

# --- Notification Helper ---
function Show-Toast($title, $message) {
    Add-Type -AssemblyName System.Windows.Forms
    Add-Type -AssemblyName System.Drawing
    $notify = New-Object System.Windows.Forms.NotifyIcon
    $notify.Icon = [System.Drawing.SystemIcons]::Information
    $notify.BalloonTipTitle = $title
    $notify.BalloonTipText  = $message
    $notify.Visible = $true
    $notify.ShowBalloonTip(5000)
    Start-Sleep -Seconds 5
    $notify.Dispose()
}

# --- Kill Existing Processes ---
function Kill-Existing {
    Write-Host "🧹 Cleaning old processes..." -ForegroundColor Yellow
    Start-Process "taskkill.exe" -ArgumentList "/F", "/IM", "node.exe" -WindowStyle Hidden
    Start-Process "taskkill.exe" -ArgumentList "/F", "/IM", "python.exe" -WindowStyle Hidden
}

# --- Start Backend ---
function Start-Backend {
    Set-Location $backendPath
    Show-Toast "Blackout Vaults" "🚀 Starting backend on port $backendPort"
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"& .\.venv\Scripts\Activate.ps1; python main.py`""
    Start-Sleep -Seconds $restartDelaySec
}

# --- Start Frontend ---
function Start-Frontend {
    Set-Location $frontendPath
    Show-Toast "Blackout Vaults" "🌐 Starting frontend on port $frontendPort"
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"npm run dev`""
    Start-Sleep -Seconds $restartDelaySec
}

# --- MAIN LOOP ---
while ($true) {
    try {
        Kill-Existing
        Start-Backend
        Start-Frontend
        Show-Toast "Blackout Vaults" "✅ Running on ports $backendPort & $frontendPort"

        # Wait before auto restart
        for ($i = $refreshHours * 60; $i -gt 0; $i--) {
            Start-Sleep -Seconds 60
        }

        Show-Toast "Blackout Vaults" "♻ Restarting both systems..."
    }
    catch {
        Show-Toast "Blackout Vaults" "❌ Error detected - restarting..."
        Start-Sleep -Seconds 10
    }
}
