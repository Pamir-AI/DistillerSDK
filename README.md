# start development on Distiller
## Unboxing the device
Details on how to use first time : https://docs.pamir.ai/Onboarding

## First time ssh setup
Once you connected the device to the network, you can ssh into the device using the following command:
```
ssh distiller@<device-ip>
```
The default password is `one`.

# software development environment setup

## Writing your first script
Once you in the ssh session, navigate to the `~/DistillerSDK` directory (which is this repo).
We recommend start with sample scripts from the `examples` directory. Some good starting points are:
 - ./app_transcription.py is a simple local transcription script that utilize whisper lib with some simple UI.
 - ./app_game_engine.py is a simple conversational driven game that utilize openAI asisstant api endpoint with some simple UI.

## Running your script
Note : kill the main process before test your own script, you can use command `ps -ef | grep main.py` to find the process id and then use `kill -9 <process-id>` to kill the process.
Or if you do not want the program to start everytime you power on the device, you can make changes to '/etc/rc.local' to comment out the line that starts the boot_up script.

To run your script, you can use the following command in the DistillerSDK directory:
```
venv/bin/python <your-script>.py
```

For more details on how to use the SDK, please refer to the [documentation](https://docs.pamir.ai/sdk_docs).

## clone the repo to local
```
git clone https://github.com/Pamir-AI/DistillerSDK.git
cd DistillerSDK
```
## install the distiller package (we preinstall all of them on the device at /home/distiller/DistillerSDK/venv)
```
python3 -m venv --system-site-packages venv
source venv/bin/activate
pip install -e .[hardware]
```