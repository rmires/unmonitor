#!/bin/bash
if [ -z "$CRON_SCHEDULE" ]; then
  CRON_SCHEDULE="@hourly"
fi

if [ -z "$CONFIG_PATH" ]; then
  CONFIG_PATH="/config/config.yaml"
fi

echo "$CRON_SCHEDULE python /app/unmonitor.py $CONFIG_PATH" > /var/spool/cron/crontabs/root 

echo "Crontab:"
cat /var/spool/cron/crontabs/root 

echo
crond -f -L /dev/stdout
