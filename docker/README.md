# Dockerized services

This folder contains the docker compose file and config/init files to get the additional services running:

- TimescaleDB
- Grafana
- Mosquitto

To start the services, from the docker folder run:

    $docker compose up -d

When running WSL, copy over the contents to your WSL instance, then run docker compose.

The mosquitto configuration is part of the image, after changing it, you have to rebuild the image:

    $docker compose up -d --build mosquitto
