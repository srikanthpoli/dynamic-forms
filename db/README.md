# PostgreSQL Database Container

This folder contains a PostgreSQL container setup for the project, along with a pgAdmin container for viewing tables through a UI.

## Folder used by the database container

The database data is stored in a dedicated subfolder inside this `db` directory:

- `./postgres-data/pgdata`

This is mounted into the container so your database persists even if the container is restarted.

## Start the database + pgAdmin (recommended)

From this folder, run:

```bash
docker compose up -d
```

This starts two containers:

- `dynamicForms` — the PostgreSQL database
- `dynamicFormsPgAdmin` — the pgAdmin web UI

## Stop the containers

```bash
docker compose stop
```

## Start them again

```bash
docker compose start
```

## Remove the containers (keeps data, since it's on disk)

```bash
docker compose down
```

## Using pgAdmin

1. Open [http://localhost:5050](http://localhost:5050)
2. Log in with:
   - Email: `admin@dynamicforms.com`
   - Password: `admin`
3. Add a new server:
   - Name: `dynamicForms` (anything you like)
   - Host name/address: `dynamicForms` (the container name, since pgAdmin talks to it over the docker network)
   - Port: `5432`
   - Username: `postgres`
   - Password: `postgres`
4. Save, then expand **Servers → dynamicForms → Databases → dynamic_forms → Schemas → public → Tables** to view tables.

## Connect to the database from your machine (psql, DBeaver, etc.)

Use these connection settings:

- Host: `localhost`
- Port: `5433`
- Database: `dynamic_forms`
- Username: `postgres`
- Password: `postgres`

Example:

```bash
psql -h localhost -p 5433 -U postgres -d dynamic_forms
```

If prompted for a password, use:

```bash
postgres
```

## Connect from another device on the same network

Other devices on the same Wi-Fi/LAN can reach the database using your laptop's local network IP address instead of `localhost`:

- Host: `192.168.2.29` (Wi-Fi adapter IPv4 address — check with `ipconfig`, may change if you reconnect to Wi-Fi)
- Port: `5433`
- Database: `dynamic_forms`
- Username: `postgres`
- Password: `postgres`

```bash
psql -h 192.168.2.29 -p 5433 -U postgres -d dynamic_forms
```

Connection string:

```
postgresql://postgres:postgres@192.168.2.29:5433/dynamic_forms
```

> Note: this only works while your laptop is on the same network, the container is running, and Windows Firewall allows inbound connections on port 5433. This IP is not stable long-term — do not use it for production.

## Useful commands

```bash
docker ps

docker logs dynamicForms

docker logs dynamicFormsPgAdmin
```

## Alternative: manual docker run (without compose)

```bash
docker build -t dynamicforms-db .

mkdir -p postgres-data/pgdata

docker run --name dynamicForms \
  -e POSTGRES_DB=dynamic_forms \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5433:5432 \
  -v "$(pwd)/postgres-data/pgdata:/var/lib/postgresql/data" \
  -d dynamicforms-db

docker run --name dynamicFormsPgAdmin \
  -e PGADMIN_DEFAULT_EMAIL=admin@dynamicforms.com \
  -e PGADMIN_DEFAULT_PASSWORD=admin \
  -p 5050:80 \
  --link dynamicForms \
  -d dpage/pgadmin4:latest
```
