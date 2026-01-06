#!/system/bin/sh
# This runs earlier than service.sh in KernelSU

MODDIR="/data/adb/modules/echoshield"

# Fix binary permissions
chmod 755 "$MODDIR/bin/python3"
chmod -R 755 "$MODDIR/lib"

# Fix SELinux Contexts (Android 14+ is strict)
chcon -R u:object_r:system_file:s0 "$MODDIR/bin"
chcon -R u:object_r:system_file:s0 "$MODDIR/lib"
chcon -R u:object_r:system_file:s0 "$MODDIR/deps"
