#!/bin/bash
export HOST_IP=<HOST_IP>
cd /home/ubuntu/microservice
docker-compose scale <container_name>=0
docker rm $(docker ps -q -f status=exited)
docker rmi -f <image_name> && docker pull <image_name> && docker-compose up -d --remove-orphans