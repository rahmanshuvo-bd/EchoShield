#!/system/bin/sh
MODDIR="/data/adb/modules/echoshield"
PIDFILE="$MODDIR/logs/service.pid"
LOGFILE="$MODDIR/logs/service.log"

# 1. Bootstrapping
mkdir -p "$MODDIR/logs"
chmod 777 "$MODDIR/logs"
export LD_LIBRARY_PATH="$MODDIR/lib"
export PYTHONHOME="$MODDIR"
export PYTHONPATH="$MODDIR/deps"

# 2. Strong Termination
if [ -f "$PIDFILE" ]; then
    OLD_PID=$(cat "$PIDFILE")
    # Check if PID is numeric and process exists
    if [ "$OLD_PID" -eq "$OLD_PID" ] 2>/dev/null && [ -d "/proc/$OLD_PID" ]; then
        echo "[$(date)] Terminating existing PID: $OLD_PID" >> "$LOGFILE"
        kill -9 "$OLD_PID" >/dev/null 2>&1
        sleep 1
    fi
    rm -f "$PIDFILE"
fi

# Fallback Scour
pkill -9 -f "shield_ui.py"

# 3. Idempotent Firewall Rule
iptables -D INPUT -p tcp --dport 5000 -j ACCEPT >/dev/null 2>&1
iptables -I INPUT -p tcp --dport 5000 -j ACCEPT

# 4. Clean Launch (The Android Way)
cd "$MODDIR"
echo "[$(date)] Launching EchoShield UI..." >> "$LOGFILE"

# We use ( ... ) & to subshell the process, further decoupling it from the terminal
(
    # Redirect all 3 descriptors to ensure no hangup on TTY close
    exec ./bin/python3 shield_ui.py >> "$LOGFILE" 2>&1
) &

NEW_PID=$!
echo "$NEW_PID" > "$PIDFILE"

echo "[$(date)] Service successfully started on PID: $NEW_PID" >> "$LOGFILE"
