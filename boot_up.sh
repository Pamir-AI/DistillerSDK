#!/bin/bash

raspi-gpio set 22 pu
sleep 0.01
raspi-gpio set 22 pd
sleep 0.01


# start llama.cpp server

/home/distiller/llama.cpp/build/bin/llama-server -m /home/distiller/.cache/nexa/hub/official/DeepSeek-R1-Distill-Qwen-1.5B-NexaQuant/q4_0.gguf --port 8080 &

cd /home/distiller/DistillerSDK
venv/bin/python examples/main.py 
