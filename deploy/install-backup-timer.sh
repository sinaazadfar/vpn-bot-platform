#!/usr/bin/env sh
set -eu

APP_DIR="${APP_DIR:-/opt/vpn-bot-platform}"

cat >/etc/systemd/system/vpn-bot-platform-backup.service <<EOF
[Unit]
Description=VPN Bot Platform Postgres backup

[Service]
Type=oneshot
Environment=APP_DIR=$APP_DIR
Environment=BACKUP_DIR=$APP_DIR/backups/postgres
WorkingDirectory=$APP_DIR
ExecStart=/bin/sh $APP_DIR/deploy/backup-postgres.sh
EOF

cat >/etc/systemd/system/vpn-bot-platform-backup.timer <<EOF
[Unit]
Description=Run VPN Bot Platform Postgres backup daily

[Timer]
OnCalendar=*-*-* 03:15:00
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now vpn-bot-platform-backup.timer
systemctl list-timers vpn-bot-platform-backup.timer --no-pager
