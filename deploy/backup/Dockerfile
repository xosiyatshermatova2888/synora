FROM postgres:16-alpine

# Nightly pg_dump sidecar. Runs in a loop (sleep between runs) instead of cron
# so there is no host cron dependency on the VM. Backups land as gzip files in
# /backups with RETENTION_DAYS pruning; mount /backups to durable storage.

COPY backup.sh /usr/local/bin/synora-backup.sh
RUN chmod +x /usr/local/bin/synora-backup.sh

CMD ["/usr/local/bin/synora-backup.sh"]