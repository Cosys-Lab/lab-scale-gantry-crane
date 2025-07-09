Arduino code for an Arduino with the Conveyor shield V1.0 connected to 
the Fischertechnik conveyorbelt.

The command structure is described below

# G1 - Move indefinitely
## Description

The `G1` command moves the conveyor forwards or backwards indefinitely.

## Usage

`G1 [dir]`

### Parameters

[dir]: `F` for forwards, `B` for backwards.

## Example

`G1 F` # move forward indefinitely

# G2 - Move amount of pulses

## Description

The `G2` command moves the conveyor forwards or backwards a certain amount of pulses/steps.
one pulse is 1/8th of a rotatino of the conveyor's axle.

## Usage

`G1 [dir][pulses]`

### Parameters

[dir]: `F` for forwards, `B` for backwards.
[pulses]: number of pulses to move

## Example

`G1 F4` # move forward 4 pulses

# G3 - Move untill sensor

## Description

The `G3` command moves the conveyor forwards or backwards until the object
on the conveyor meets the start/end sensor.

## Usage

`G3 [dir]`

### Parameters

[dir]: `F` for forwards, `B` for backwards.

## Example

`G3 F` # move forward until the end sensor is triggered.

# G4 - Query Sensor State

## Description

The `G4` command queries the sensor (start, stop and pulse counter) state.

## Usage

`G4`

### Returns

`START_SENSOR: [1/0], END_SENSOR [1/0], PULSE_COUNT: [integer]`

## Example

`G4` # request sensor state
`START_SENSOR: 1, END_SENSOR 0, PULSE_COUNT: 40` # printer returns

# G5 - Stop movement

## Description

The `G5` command stops the conveyor.

## Usage

`G5`

# G6 - Electromagnet Control

## Description

The `G6` command controls the electromagnet

## Usage

`G6 [on/off]`

### Parameters

[on/off]: 0 to turn off, any other value to turn on.

## Example

`G6 1` # turn magnet on
`G6 0` # turn magnet off

# Other notes:

When a command is received that does not output data to the printer, 
it will return `OK [repeat command]` on the terminal

When an unknown command is received, it will return `NOK [repeat command]`

# Continuous angle output

The arduino also continuously measures the angle and the angular velocity
of the encoder and outputs it at a rate of 100 Hz.

This output has the shape `A: SX.XX,V: SY.YY`, where S is the optional
minus (-) sign, and the angle and angular velocity are printed with 2
decmial places. 

e.g. `A: -360.00,V: 10.15`




