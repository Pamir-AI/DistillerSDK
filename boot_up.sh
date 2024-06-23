#!/bin/bash

raspi-gpio set 22 pu
sleep 0.01
raspi-gpio set 22 pd
sleep 0.01

cd /home/distiller/DistillerSDK
venv/bin/python examples/main.py 
