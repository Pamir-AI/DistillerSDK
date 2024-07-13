#!/bin/bash

if [ -z "$EMC2301_CLK" ]; then
	EMC2301_CLK=32768
fi
if [ -z "$EMC2301_I2C_ADDR" ]; then
	EMC2301_I2C_ADDR="0x2f"
fi
EMC2301_DRIVE_REG="0x30"
EMC2301_FANCFG_REG="0x32"
EMC2301_DRIVEMIN_REG="0x38"
EMC2301_TACHVALID_REG="0x39"
EMC2301_TACHTARGET_REG="0x3c"
EMC2301_TACHREAD_REG="0x3e"
EMC2301_PRODID_REG="0xfd"
EMC2301_MANUID_REG="0xfe"
EMC2301_REV_REG="0xff"
EMC2301_TACHVALID_SHIFT=5
EMC2301_FSCA_MASK=128
EMC2301_FSCA_SHIFT=7
EMC2301_RANGE_MASK=96
EMC2301_RANGE_SHIFT=5
EMC2301_EDGES_MASK=24
EMC2301_EDGES_SHIFT=3
EMC2301_TACHREAD_SHIFT=3
EMC2301_TACHTARGET_SHIFT=3
EMC2301_TACHTARGET_OFF=8191
EMC2301_PRODID_VAL="0x37"
EMC2301_MANUID_VAL="0x5d"
EMC2301_REV_VAL="0x80"

EMC2301_FSCA_LAST=
EMC2301_RANGE_LAST=
EMC2301_RANGE_RPM_MIN=
EMC2301_EDGES_LAST=
EMC2301_EDGES_TACH_MIN=

HEX_toDec(){
	printf "%d" "$1"
}
HEX_revByte(){
	local hex="${1,,}"
	if [ "${hex:0:2}" = "0x" ]; then
		hex=${hex:2}
	fi
	echo -n "0x"
	echo "$hex" | fold -w2 | tac | tr -d "\n"
}
DEC_toHexByte(){
	printf "0x%02x" "$1"
}

EMC2301_get(){
    i2cget -y "$EMC2301_I2C_BUS" "$EMC2301_I2C_ADDR" "$1" "$2"
}

EMC2301_set(){
    i2cset -y "$EMC2301_I2C_BUS" "$EMC2301_I2C_ADDR" "$1" "$2" "$3"
}
EMC2301_check(){
	local product_id=$(EMC2301_get "$EMC2301_PRODID_REG" b)
	[ "$product_id" = "$EMC2301_PRODID_VAL" ] || (echo "$FUNCNAME: $product_id does not match Product ID" >&2 && return 1)
	local manufacturer_id=$(EMC2301_get "$EMC2301_MANUID_REG" b)
	[ "$manufacturer_id" = "$EMC2301_MANUID_VAL" ] || (echo "$FUNCNAME: $manufacturer_id does not match Manufacturer ID" >&2 && return 1)
	local revision=$(EMC2301_get "$EMC2301_REV_REG" b)
	[ "$revision" = "$EMC2301_REV_VAL" ] || (echo "$FUNCNAME: $revision does not match Revision" >&2 && return 1)
}
EMC2301_getDrive(){
	local drive_scaled_hex=$(EMC2301_get $EMC2301_DRIVE_REG b)
	local drive_scaled=$(HEX_toDec $drive_scaled_hex)
	echo "scale=0; $drive_scaled*100/255" | bc -l
}
EMC2301_setDrive(){
	local drive="$1"
	if [ "$drive" -gt 100 ]; then
		echo "$FUNCNAME: $drive exceeds max (100)" >&2
		return 1
	elif [ "$drive" -lt 0 ]; then
		echo "$FUNCNAME: $drive below min (0)" >&2
		return 1
	fi
	local drive_scaled=$(echo "scale=0; $drive*255/100" | bc -l)
	local drive_scaled_hex=$(DEC_toHexByte $drive_scaled)
	EMC2301_set $EMC2301_DRIVE_REG $drive_scaled_hex b
	echo "EMC set : $EMC2301_DRIVE_REG $drive_scaled_hex"
}
EMC2301_getDriveMin(){
	local drivemin_scaled_hex=$(EMC2301_get $EMC2301_DRIVEMIN_REG b)
	local drivemin_scaled=$(HEX_toDec $drivemin_scaled_hex)
	echo "scale=0; $drivemin_scaled*100/255" | bc -l
}
EMC2301_setDriveMin(){
	local drivemin="$1"
	if [ "$drivemin" -gt 100 ]; then
		 
		return 1
	elif [ "$drivemin" -lt 0 ]; then
		echo "$FUNCNAME: $drivemin below min (0)" >&2
		return 1
	fi
	local drivemin_scaled=$(echo "scale=0; $drivemin*255/100" | bc -l)
	local drivemin_scaled_hex=$(DEC_toHexByte $drivemin_scaled)
	EMC2301_set $EMC2301_DRIVEMIN_REG $drivemin_scaled_hex b
}

EMC2301_setFSCAEnable(){
    local fsca="$1"
    local fancfg_hex=$(EMC2301_get $EMC2301_FANCFG_REG b)
    if [ "$fsca" -eq 1 ]; then
        fancfg_hex=$((fancfg_hex | 0x80))
    else
        fancfg_hex=$((fancfg_hex & ~0x80))
    fi
    EMC2301_set $EMC2301_FANCFG_REG $fancfg_hex b
}
