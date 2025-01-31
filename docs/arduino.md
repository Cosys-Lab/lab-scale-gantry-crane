# arduino.md

## Prerequisites

Install following dependencies in the arduino IDE:

[Encoder](https://github.com/PaulStoffregen/Encoder)
[PinChangeInterrupt](https://github.com/NicoHood/PinChangeInterrupt/#pinchangeinterrupt-table)

## Explanation

In a nutshell: there are two arduino scripts

* one to measure angles with the encoder
* one to control the electromagnet (with additional functions)
    * this script requires you to build the arduino shield, for which KiCad files are provided.

In the future all of this code should be placed on one Arduino,
and the shield updated to a V2, which is future work.

## MQTT Wrapper

The shield was actually used to control a Fischertechnik conveyor belt with the arduino,
(to be detailled more) The command interface over serial can be found in the readme.md file in the folder.
We also provide an MQTT wrapper around it such that you can interface with Python or any other general purpose programming language.
TODO: document.