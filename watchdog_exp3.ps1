# Watchdog for Exp 3 runner (PowerShell version — avoids Python shim issues)
# Monitors exp3_fingerprint.py and auto-restarts if it dies.
# Stops when 164 tasks have FINAL rows in exp3_results.csv.
# Usage: powershell -ExecutionPolicy Bypass -File watchdog_exp3.ps1

$ROOT        = Split-Path -Parent $MyInvocation.MyCommand.Path
$RESULTS_CSV = "$ROOT\results\exp3_results.csv"
$RUNNER_PY   = "$ROOT\experiments\exp3_fingerprint.py"
$PYTHON      = "$ROOT\.venv\Scripts\python.exe"
$LOG         = "$ROOT\results\exp3_watchdog.log"
$TARGET      = 50
$INTERVAL    = 60

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[watchdog $ts] $msg"
    Write-Host $line
    Add-Content -Path $LOG -Value $line -Encoding UTF8
}

function Get-CompletedCount {
    if (-not (Test-Path $RESULTS_CSV)) { return 0 }
    $count = 0
    Import-Csv $RESULTS_CSV | ForEach-Object {
        if ($_.round_num -eq "FINAL" -and $_.fingerprint_distance -ne "ERROR") {
            $count++
        }
    }
    return $count
}

function Get-RunnerPid {
    # Find the actual python process running exp3_fingerprint.py (not the shim)
    $procs = Get-WmiObject Win32_Process | Where-Object {
        $_.Name -like "python*" -and $_.CommandLine -like "*exp3_fingerprint*"
    }
    return $procs
}

Write-Log "Watchdog started. Target: $TARGET tasks."
$proc = $null

while ($true) {
    $done = Get-CompletedCount
    Write-Log "Progress: $done/$TARGET tasks complete"

    if ($done -ge $TARGET) {
        Write-Log "Done - all $TARGET tasks complete. Watchdog exiting."
        if ($proc -and -not $proc.HasExited) { $proc.Kill() }
        break
    }

    # Check if runner is alive
    $runnerProcs = Get-RunnerPid
    if (-not $runnerProcs) {
        if ($proc) {
            Write-Log "Runner died. Restarting..."
        } else {
            Write-Log "Starting runner..."
        }
        $psi = New-Object System.Diagnostics.ProcessStartInfo
        $psi.FileName = $PYTHON
        $psi.Arguments = "`"$RUNNER_PY`" --max-rounds 4 --workers 2"
        $psi.WorkingDirectory = $ROOT
        $psi.UseShellExecute = $false
        $psi.RedirectStandardOutput = $false
        $psi.RedirectStandardError = $false
        $proc = [System.Diagnostics.Process]::Start($psi)
        Write-Log "Runner started (PID=$($proc.Id))"
    } else {
        Write-Log "Runner alive (PIDs: $(($runnerProcs | ForEach-Object { $_.ProcessId }) -join ','))"
    }

    Start-Sleep -Seconds $INTERVAL
}
