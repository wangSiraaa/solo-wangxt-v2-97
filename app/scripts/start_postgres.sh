#!/usr/bin/env bash
# Start the locally-extracted PostgreSQL cluster (no root required).
set -euo pipefail

PGBIN="${PGBIN:-/home/node/pg/usr/lib/postgresql/16/bin}"
PGDATA="${PGDATA:-/home/node/pgdata}"
export LD_LIBRARY_PATH="/home/node/pg/usr/lib/aarch64-linux-gnu:${LD_LIBRARY_PATH:-}"

if [ ! -s "$PGDATA/PG_VERSION" ]; then
  "$PGBIN/initdb" -D "$PGDATA" -U postgres --auth=trust --no-locale --encoding=UTF8
  echo "unix_socket_directories = '/tmp'" >> "$PGDATA/postgresql.conf"
  echo "listen_addresses = '127.0.0.1'" >> "$PGDATA/postgresql.conf"
fi

"$PGBIN/pg_ctl" -D "$PGDATA" -l "$PGDATA/server.log" start
sleep 1

"$PGBIN/psql" -h 127.0.0.1 -U postgres -tc "SELECT 1 FROM pg_database WHERE datname='pumpingdb'" \
  | grep -q 1 || "$PGBIN/psql" -h 127.0.0.1 -U postgres -c "CREATE DATABASE pumpingdb;"
"$PGBIN/psql" -h 127.0.0.1 -U postgres -tc "SELECT 1 FROM pg_roles WHERE rolname='pumpapp'" \
  | grep -q 1 || "$PGBIN/psql" -h 127.0.0.1 -U postgres -c "CREATE USER pumpapp WITH PASSWORD 'pumpapp_dev';"
"$PGBIN/psql" -h 127.0.0.1 -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE pumpingdb TO pumpapp;"
"$PGBIN/psql" -h 127.0.0.1 -U postgres -d pumpingdb -c "GRANT ALL ON SCHEMA public TO pumpapp;"
echo "PostgreSQL ready: pumpingdb on 127.0.0.1:5432"
