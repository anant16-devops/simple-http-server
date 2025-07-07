#!/bin/bash
yum update -y
yum install -y python3 python3-pip unzip

# Create app directory
mkdir -p /opt/simple-http-server
cd /opt/simple-http-server

# Decode and extract application files
echo "${app_files}" | base64 -d > app.zip
unzip -o app.zip
rm app.zip

# Start the application
nohup python3 main.py -hs 0.0.0.0 -p 8000 > /var/log/simple-http-server.log 2>&1 &