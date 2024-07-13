#!/bin/bash

set -e

cd $(readlink -f $(dirname ${BASH_SOURCE[0]}))

. emc2301.ini
. emc2301.sh
. daemon.ini

if [ -z "$VERBOSE" ]; then
    VERBOSE=0
fi

EMC2301_daemon(){
    EMC2301_check && echo "EMC2301 detected" || (echo "EMC2301 not detected" && return 1)
    
    EMC2301_setFSCAEnable 0
    echo "Fan Speed Control Algorithm disabled for direct control"
    
    EMC2301_setDriveMin $DAEMON_FAN_DRIVEMIN
    echo "Minimum Drive set to $DAEMON_FAN_DRIVEMIN"
    
    while true; do
        EMC2301_monitor
        sleep $DAEMON_FREQ_SEC
    done
}

EMC2301_convertTempRaw(){
    local temp_raw=$1
    echo $(((temp_raw + 500) / 1000))
}

EMC2301_monitor(){
    local temp_raw=$(cat $DAEMON_TEMP_SOURCE)
    local temp=$(EMC2301_convertTempRaw "$temp_raw")
    local drive=$(calculate_drive_from_temp $temp)
    
    calculate_drive_from_temp $temp

    EMC2301_setDrive $drive
    
    local read_drive=$(EMC2301_getDrive)
    if [ "$VERBOSE" -eq 1 ]; then
        echo "Raw Temperature: ${temp_raw}, Converted Temperature: ${temp}°C"
        echo "Calculated Drive: ${drive}, Set Drive: ${drive}, Read Drive: ${read_drive}"
        # echo "Current DAEMON_FAN_DRIVEMIN: $DAEMON_FAN_DRIVEMIN"
    fi
}
calculate_drive_from_temp() {
    local temp=$1
    local drive=0
    local temps_count=${#DAEMON_TEMPS[@]}
    # echo "temps_count : $temps_count"
    for i in $(seq 0 $((temps_count - 1))); do
        # echo "DAEMON_TEMPS $i : ${DAEMON_TEMPS[$i]}" 
        if [ $temp -ge ${DAEMON_TEMPS[$i]} ]; then
            drive=${DAEMON_SPEED[$i]}
            # echo "drive : $drive"
        else
            break
        fi
    done
    # echo "drive -2  : $drive"
    # Convert percentage to 0-255 range
    # drive=$((drive * 255 / 100))
    
    # Ensure the drive is at least DAEMON_FAN_DRIVEMIN
    if [ $drive -lt $DAEMON_FAN_DRIVEMIN ]; then
        drive=$DAEMON_FAN_DRIVEMIN
    fi
    
    echo $drive
}
EMC2301_daemon
