#!/bin/bash
yum update -y
yum install -y python3 git

# Clone the repository (replace with your repo URL)
cd /opt
git clone https://github.com/anant16-devops/simple-http-server.git simple-http-server
cd simple-http-server

# Start the application
nohup python3 main.py -hs 0.0.0.0 -p 8000 > /var/log/simple-http-server.log 2>&1 &