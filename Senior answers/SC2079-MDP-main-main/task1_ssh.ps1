# Usage: .\task1_ssh.ps1
# Requires: Windows built-in ssh (OpenSSH client, available on Windows 10/11)
#
# FIRST-TIME SETUP (run once to copy your SSH key to the RPi - avoids password prompts):
#   if (!(Test-Path "$env:USERPROFILE\.ssh\id_rsa.pub")) { ssh-keygen -t rsa -f "$env:USERPROFILE\.ssh\id_rsa" }
#   type "$env:USERPROFILE\.ssh\id_rsa.pub" | ssh mdp@192.168.20.1 "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
#   Enter the RPi password (pi) when prompted. After this, no password is needed.
#
# Task 1 configuration:
#   Robot starting position: bottom-left corner at (1, 1), facing NORTH
#   (These are the default values used by pathfinding() on the PC side.)

$REMOTE_USER = "mdp"
$REMOTE_HOST = "192.168.20.1"
$REMOTE_PASS = "pi"
$REMOTE_DIR  = "RPi"

# --- Step 1: Kill any existing task1.py instance ---
Write-Host "[1/3] Killing any existing task1.py on RPi..."
ssh mdp@${REMOTE_HOST} "echo $REMOTE_PASS | sudo -S pkill -f 'python3 task1.py' 2>/dev/null; echo $REMOTE_PASS | sudo -S rm -f /var/run/mdp-task1.lock"
Start-Sleep -Seconds 1

# --- Step 2: Launch SSH into RPi in a new window ---
Write-Host "[2/4] Opening new window to start RPi task1.py..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "ssh -tt -o StrictHostKeyChecking=no ${REMOTE_USER}@${REMOTE_HOST} 'echo $REMOTE_PASS | sudo -S pkill -f `"python3 task1.py`" 2>/dev/null; sleep 1; cd ~/$REMOTE_DIR && echo $REMOTE_PASS | sudo -S python3 task1.py'"

# --- Step 2: Wait for RPi to initialize ---
Write-Host "[3/4] Waiting for RPi to initialize (8s)..."
Start-Sleep -Seconds 8

# --- Step 4: Run PC Task1.py in this window ---
Write-Host "[4/4] Starting PC Task1.py..."
$pcScript = Join-Path $PSScriptRoot "PC\Task1.py"
python $pcScript
