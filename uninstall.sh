#!/system/bin/sh

# 1. Kill all background processes
# We target the Python binary and the specific UI script
pkill -f "shield_ui.py"
pkill -f "bin/python3"

# 2. Revert Networking Changes
# We remove the specific rule we added to Port 5000
# -D deletes the exact rule that matches our criteria
iptables -D INPUT -p tcp --dport 5000 -j ACCEPT 2>/dev/null

# 3. Cleanup State and PIDs
# Magisk deletes the module folder automatically, but if you created
# any files in /data/local/tmp or /cache during runtime, delete them here.
rm -f /data/local/tmp/echoshield.pid
rm -rf /cache/echoshield_cache

# 4. Log the Uninstallation
# Helpful for debugging if a user reports issues after removal
echo "[$(date)] EchoShield uninstalled successfully." >> /data/local/tmp/echoshield_uninstall.log
