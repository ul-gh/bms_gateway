#!/bin/sh
DIR="$(dirname $0)"
#DUMP_FILE="${DIR}/candump_stack.log"
DUMP_FILE="${DIR}/candump_stack_inverter.log"
# Output CAN channel.
CAN_CH="vcan2"
echo "Playing CAN frames from file $DUMP_FILE on channel $CAN_CH. Press CTRL_C to stop."
canplayer -I "$DUMP_FILE" -t "${CAN_CH}=can1" -l i -g 1000

