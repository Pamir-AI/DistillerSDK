#!/bin/bash

# hijack screen over
raspi-gpio set 22 pu
sleep 0.01
raspi-gpio set 22 pd
sleep 0.01

# adjust fan speed
/home/distiller/DistillerSDK/src/distiller/firmware/Fan/daemon.sh &

cd /home/distiller/DistillerSDK
venv/bin/python examples/main.py 
