import time
from abc import ABCMeta, abstractmethod
from pytrinamic.evalboards import TMC4671_eval
from pytrinamic.ic import TMC4671
from pytrinamic.connections import ConnectionManager
from numpy import pi

class Motor(metaclass=ABCMeta):
    """A class representing a motor.
    """

    def __init__(self, port, pulley_circumference, I_max) -> None:
        """Initializes a Motor instance.

        Args:
            port: serial port of the motor controller
            pulley_circumference: circumference of the motor pulley
            I_max: maximum current
        """
        self.mc_interface = ConnectionManager(arg_list="--port="+port).connect()

        if self.mc_interface.supports_tmcl():
            # Create an TMC4671 IC class which communicates over the Landungsbrücke via TMCL
            self.board = TMC4671_eval(self.mc_interface)
            self.mc = self.board.ics[0]
        else:
            # Create an TMC4671 IC class which communicates directly over UART
            self.mc = TMC4671(self.mc_interface)
            # Use IC like an "EVAL" to use this example for both access variants
            self.board = self.mc

        # parameters
        self.pulley_diameter = pulley_circumference
        self.mm_to_counts = 65536/self.pulley_diameter
        self.mm_s_to_rpm = 60/self.pulley_diameter
        self.I_max = int(1000*I_max) # convert amps to mA.

        # increase baudrate of UART logging interface
        # 921600 is the maximum the FTDI adapter does in windows
        self.board.write_register(self.mc.REG.UART_BPS, 0x00921600)
        
    @abstractmethod
    def _motorConfig(self):
        """Configure the motor."""
    
    @abstractmethod
    def _ADCConfig(self):
        """Configure the ADC."""

    @abstractmethod
    def _encoderConfig(self):
        """Configure the encoder."""
    
    @abstractmethod
    def _limitConfig(self):
        """Configure operating limits."""
    
    @abstractmethod
    def _PIConfig(self):
        """Configure the PI controller."""

    @abstractmethod
    def _feedbackSelection(self):
        """Select feedback source for position and velocity."""

    @abstractmethod
    def _homeAndCalibrate(self):
        """Home and calibrate the motor."""

    def setTorqueMode(self):
        """Set motor drive to torque mode."""
        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, self.mc.ENUM.MOTION_MODE_TORQUE)

    def setVelocityMode(self):
        """Set motor driver to velocity mode"""
        #self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, self.mc.ENUM.MOTION_MODE_VELOCITY)
        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, 0x00000002)
    
    def setPositionMode(self):
        """Set motor driver to position mode"""
        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, self.mc.ENUM.MOTION_MODE_POSITION)

    def setTorque(self, tgt):
        """Set the target torque.

        Note: assumes printer is in torque mode.
        Printer can be set in torque mode with setTorqueMode.

        Args:
            tgt: target torque
        """
        self.board.write_register_field(self.mc.FIELD.PID_TORQUE_TARGET, int(tgt))
        self.board.write_register_field(self.mc.FIELD.PID_FLUX_TARGET, 0)

    def getTorque(self):
        """Get the actually exerted torque.

        Returns:
            int: The actually exerted torque.
        """
        return self.board.read_register(self.mc.REG.PID_TORQUE_FLUX_ACTUAL, signed=True)

    def getVelocity(self):
        """Get the current velocity.

        Returns:
            int: The current velocity.
        """
        return self.board.read_register(self.mc.REG.PID_VELOCITY_ACTUAL, signed=True)

    def getPosition(self):
        """Get the current position.

        Returns:
            int: The current position
        """
        return self.board.read_register(self.mc.REG.PID_POSITION_ACTUAL, signed=True)

    def setLimits(self, acc, vel):
        """Set acceleration and velocity limits.

        Args:
            acc: Acceleration limit.
            vel: Velocity limit.
        """
        self.board.write_register(self.mc.REG.PID_ACCELERATION_LIMIT, int(acc))
        self.board.write_register(self.mc.REG.PID_VELOCITY_LIMIT, int(vel))

    def setAccelLimit(self, acc):
        """Set acceleration limit.
        
        Args:
            acc: Acceleration limit.
        """
        self.board.write_register(self.mc.REG.PID_ACCELERATION_LIMIT, int(acc))

    def setVelocityLimit(self, vel):
        """Set velocity limit.

        Args:
            vel: Velocity limit.
        """
        self.board.write_register(self.mc.REG.PID_VELOCITY_LIMIT, int(vel))

    def setPosition(self, pos):
        """Set the current position.

        Args:
            pos: current position.
        """
        self.board.write_register(self.mc.REG.PID_POSITION_TARGET, int(pos))

    def setVelocity(self, vel):
        """Set the current velocity

        Args:
            vel: The current velocity.
        """
        self.board.write_register(self.mc.REG.PID_VELOCITY_TARGET, int(vel))

class Stepper(Motor, metaclass=ABCMeta):
    """Specialization of the Motor class into a Stepper motor."""

    def __init__(self, port, pulley_diameter, I_max) -> None:
        """Initialize a Stepper instance."""
        super().__init__(port, pulley_diameter, I_max)

    def _motorConfig(self):
        """Configure the motor as stepper motor.
        """
        super()._motorConfig()
        # Motor type &  PWM configuration
        self.board.write_register(self.mc.REG.MOTOR_TYPE_N_POLE_PAIRS, 0x00020032)
        self.board.write_register(self.mc.REG.PWM_POLARITIES, 0x00000000)
        self.board.write_register(self.mc.REG.PWM_MAXCNT, 0x00000F9F)
        self.board.write_register(self.mc.REG.PWM_BBM_H_BBM_L, 0x00000A0A)
        self.board.write_register(self.mc.REG.PWM_SV_CHOP, 0x00000007)

    @abstractmethod
    def _ADCConfig(self):
        """Configure the ADC.
        """
        super()._ADCConfig()
        # ADC configuration
        self.board.write_register(self.mc.REG.ADC_I_SELECT, 0x18000100)
        self.board.write_register(self.mc.REG.dsADC_MCFG_B_MCFG_A, 0x00100010)
        self.board.write_register(self.mc.REG.dsADC_MCLK_A, 0x20000000)
        self.board.write_register(self.mc.REG.dsADC_MCLK_B, 0x20000000)
        self.board.write_register(self.mc.REG.dsADC_MDEC_B_MDEC_A, 0x014E014E)

    def _encoderConfig(self):
        """Configure the encoder.
        """
        super()._encoderConfig()
        # ABN encoder settings
        self.board.write_register(self.mc.REG.ABN_DECODER_MODE, 0x00001000)
        self.board.write_register(self.mc.REG.ABN_DECODER_PPR, 0x00009C40)
        self.board.write_register(self.mc.REG.ABN_DECODER_PHI_E_PHI_M_OFFSET, 0x00000000)

    @abstractmethod
    def _limitConfig(self):
        """Configure the limits.
        """
        super()._limitConfig()
        self.board.write_register(self.mc.REG.PID_TORQUE_FLUX_LIMITS, self.I_max)
        self.board.write_register(self.mc.REG.PID_VELOCITY_LIMIT, 6000)

    def _feedbackSelection(self):
        """Select feedback."""
        super()._feedbackSelection()
        # Position and velocity selection
        # mechanical rotation, from ABN encoder.
        self.board.write_register(self.mc.REG.VELOCITY_SELECTION, self.mc.ENUM.VELOCITY_PHI_M_ABN)
        self.board.write_register(self.mc.REG.POSITION_SELECTION, self.mc.ENUM.VELOCITY_PHI_M_ABN)

class GantryStepper(Stepper):
    """Specializes stepper into the gantry stepper, that is the motor that does the lateral movement."""

    def __init__(self, port, calibrated=False, I_max = 1) -> None:
        """Initializes an instance of GantryStepper.

        Args:
            port: The serial port of the motor controller.
            calibrated (bool, optional): Whether the motor is calibrated or not. Defaults to False.
            I_max: The maximum currnet. Defaults to 1 Ampere.
        """
        super().__init__(port, pulley_diameter=40, I_max=I_max)
        self._motorConfig()
        self._ADCConfig()
        self._encoderConfig()
        self._limitConfig()
        self._PIConfig()
        self._feedbackSelection()

        if not calibrated:
            self._homeAndCalibrate()
        else:
            self.setPositionMode()
            print("current position:", self.getPosition())
            print("setting position to 0")
            while(round(self.getPosition(),-2) !=0):
                self.setPosition(0)
                time.sleep(4)
            print("current position:", self.getPosition())
            if round(self.getPosition(), -2) != 0:
                # if position mode homing somehow didn't work we can try velocity homing
                self.setVelocityMode()
                self.setVelocity(-20)
                time.sleep(0.1)
                start = time.now()
                while(round(abs(self.getVelocity())) > 2 and time.now()-start < 4):
                    pass
                print("position homing failed, velocity homing yielded position", self.getPosition())

    def _ADCConfig(self):
        """Configure the ADC.
        """
        super()._ADCConfig()
        self.board.write_register(self.mc.REG.ADC_I0_SCALE_OFFSET, 0x01008224)
        self.board.write_register(self.mc.REG.ADC_I1_SCALE_OFFSET, 0x01008177)
    
    def _limitConfig(self):
        """Configure the movement limits.
        """
        super()._limitConfig()
        # Limits
        self.board.write_register(self.mc.REG.PID_POSITION_LIMIT_LOW, 0)
        # 650mm /40mm per revolution * 65536 pulses per revolution
        self.board.write_register(self.mc.REG.POSITION_LIMIT_HIGH, 1064960)

    def _PIConfig(self):
        """Configure the PI controller.
        """
        # PI settings
        self.board.write_register_field(self.mc.FIELD.PID_TORQUE_P, 639)
        self.board.write_register_field(self.mc.FIELD.PID_TORQUE_I, 14335)
        self.board.write_register_field(self.mc.FIELD.PID_FLUX_P, 639)
        self.board.write_register_field(self.mc.FIELD.PID_FLUX_I, 14335)
        self.board.write_register_field(self.mc.FIELD.PID_VELOCITY_P, 7423)
        self.board.write_register_field(self.mc.FIELD.PID_VELOCITY_I, 17407)
        self.board.write_register_field(self.mc.FIELD.PID_POSITION_P, 277)

    def _homeAndCalibrate(self):
        """Home and calibrate the lateral axis of the crane."""
        # ===== Open loop zero point =====
        # encoder calibration sets encoder to 0 but requires movement of the motor.
        # idea is to find the zero point in open loop mode, move away from it, zero the encoder, move back to zero point, set position to 0.
        # the last part of the idea didn't end up working and is now removed from the code.

        # Open loop settings

        self.board.write_register(self.mc.REG.OPENLOOP_MODE, 0x00000000)
        self.board.write_register(self.mc.REG.OPENLOOP_ACCELERATION, 0x0000003C)

        self.board.write_register(self.mc.REG.PHI_E_SELECTION, self.mc.ENUM.PHI_E_OPEN_LOOP)
        self.board.write_register(self.mc.REG.UQ_UD_EXT, 0x00000BB8)

        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, 0x00000008)
        self.board.write_register(self.mc.REG.OPENLOOP_VELOCITY_TARGET, -20)
        # takes 19 seconds at this speed. 

        start = time.time()
        now = start
        # print(now)
        # thought this might be needed if initial velocity causes code to think endpoint is reached.
        time.sleep(0.1)
        while((now - start) < 20 ):
            vel = self.board.read_register(self.mc.REG.PID_VELOCITY_ACTUAL, signed=True)
            # print(vel)
            if abs(vel) < 2:
                # velocity is zero or less, meaning endpoint is reached.
                break

        self.board.write_register(self.mc.REG.OPENLOOP_VELOCITY_TARGET, 0)
        self.board.write_register(self.mc.REG.UQ_UD_EXT, 0)

        # zero position reached, move away from it a tiny bit such that we can do encoder calibration.
        self.board.write_register(self.mc.REG.OPENLOOP_VELOCITY_TARGET, 20)
        self.board.write_register(self.mc.REG.UQ_UD_EXT, 0x00000BB8)
        time.sleep(0.8)
        self.board.write_register(self.mc.REG.OPENLOOP_VELOCITY_TARGET, 0)
        self.board.write_register(self.mc.REG.UQ_UD_EXT, 0x00000000)

            # ===== ABN encoder initialization =====

        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, self.mc.ENUM.MOTION_MODE_STOPPED)

        # Init encoder (mode 0)
        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, 0x00000008)
        self.board.write_register(self.mc.REG.ABN_DECODER_PHI_E_PHI_M_OFFSET, 0x00000000)
        self.board.write_register(self.mc.REG.PHI_E_SELECTION, 0x00000001)
        self.board.write_register(self.mc.REG.PHI_E_EXT, 0x00000000)
        self.board.write_register(self.mc.REG.UQ_UD_EXT, 0x00001388)
        time.sleep(4)
        self.board.write_register(self.mc.REG.ABN_DECODER_COUNT, 0x00000000)
        # reset position as well
        self.board.write_register(self.mc.REG.PID_POSITION_ACTUAL, 0)

        # Feedback selection
        self.board.write_register(self.mc.REG.PHI_E_SELECTION, 0x00000003)
        self.board.write_register(self.mc.REG.VELOCITY_SELECTION, 0x00000009)
        self.board.write_register(self.mc.REG.POSITION_SELECTION, self.mc.ENUM.VELOCITY_PHI_M_ABN)

        # Switch to torque mode
        # switch from open loop to this mode causes a little skip in the motors?
        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, self.mc.ENUM.MOTION_MODE_TORQUE)
        self.board.write_register_field(self.mc.FIELD.PID_TORQUE_TARGET, 0)
        time.sleep(1/40)
        # Note on the swith to torque mode: after the calibration I switch the controller to
        # torque mode and wait a bit for the target to settle.
        # I found that if I don't do this, the motor does a jerky movement when enabling velocity/position mode

    def _testMove(self):
        """Perform a test movement.
        """
        self.setPositionMode()
        # Rotate right
        self.board.write_register(self.mc.REG.PID_POSITION_TARGET, 400000)
        time.sleep(2)
        # print(self.board.read_register(self.mc.REG.PID_POSITION_ACTUAL))

        # Rotate left
        self.board.write_register(self.mc.REG.PID_POSITION_TARGET, 0)
        time.sleep(2)
        # print(self.board.read_register(self.mc.REG.PID_POSITION_ACTUAL))

        # Stop
        self.board.write_register(self.mc.REG.PID_TORQUE_FLUX_TARGET, 0x00000000)

class HoistStepper(Stepper):
    """Specializes stepper into the hoist stepper, that is the motor that does the hoisting movement."""

    def __init__(self, port, calibrated=False, I_max = 1) -> None:
        """Initializes an instance of GantryStepper.

        Args:
            port: The serial port of the motor controller.
            calibrated (bool, optional): Whether the motor is calibrated or not. Defaults to False.
            I_max: The maximum currnet. Defaults to 1 Ampere.
        """
        super().__init__(port, pulley_diameter=21*pi, I_max = I_max)
        self._motorConfig()
        self._ADCConfig()
        self._encoderConfig()
        self._limitConfig()
        self._PIConfig()
        self._feedbackSelection()

        if not calibrated:
            self._homeAndCalibrate()
        else:
            self.setPositionMode()
            # TODO: check this code again.
            #self.setPosition(458752)
            # time.sleep(4)
            # if round(self.getPosition(), -2) != round(458752, -2):
            #     # if position mode homing somehow didn't work we need to manually home and calibrate the hoist.
            #     self._homeAndCalibrate()
    
    def _ADCConfig(self):
        """Configure the ADC.
        """
        super()._ADCConfig()
        self.board.write_register(self.mc.REG.ADC_I0_SCALE_OFFSET, 0x0100819D)
        self.board.write_register(self.mc.REG.ADC_I1_SCALE_OFFSET, 0x0100821A)   

    def _limitConfig(self):
        """Configure the limits.
        """
        super()._limitConfig()
        self.board.write_register(self.mc.REG.PID_POSITION_LIMIT_LOW, 0)
        # self.board.write_register(self.mc.REG.POSITION_LIMIT_HIGH, 458752) # 7 rotations
        self.board.write_register(self.mc.REG.POSITION_LIMIT_HIGH, 458752) # 4 rotations
        self.board.write_register(self.mc.REG.PID_VELOCITY_LIMIT, 50)

    def _PIConfig(self):
        """Configure the PI controller.
        """
        # PI settings
        self.board.write_register_field(self.mc.FIELD.PID_TORQUE_P, 639)
        self.board.write_register_field(self.mc.FIELD.PID_TORQUE_I, 4223)
        self.board.write_register_field(self.mc.FIELD.PID_FLUX_P, 639)
        self.board.write_register_field(self.mc.FIELD.PID_FLUX_I, 4223)
        self.board.write_register_field(self.mc.FIELD.PID_VELOCITY_P, 3583)
        self.board.write_register_field(self.mc.FIELD.PID_VELOCITY_I, 1151)
        self.board.write_register_field(self.mc.FIELD.PID_POSITION_P, 359)

    def _homeAndCalibrate(self):
        """Home and calibrate the hoisting axis.
        """
        # ===== Open loop hoist lowering =====
        # lower hoist a tiny bit in open loop mode.
        # Open loop settings

        self.board.write_register(self.mc.REG.OPENLOOP_MODE, 0x00000000)
        self.board.write_register(self.mc.REG.OPENLOOP_ACCELERATION, 0x0000003C)

        self.board.write_register(self.mc.REG.PHI_E_SELECTION, self.mc.ENUM.PHI_E_OPEN_LOOP)
        self.board.write_register(self.mc.REG.UQ_UD_EXT, 0x00000BB8)

        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, 0x00000008)
        self.board.write_register(self.mc.REG.OPENLOOP_VELOCITY_TARGET, -20)
        time.sleep(2)
        #stop
        self.board.write_register(self.mc.REG.OPENLOOP_VELOCITY_TARGET, 0)
        self.board.write_register(self.mc.REG.UQ_UD_EXT, 0)

        # ===== ABN encoder initialization =====

        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, self.mc.ENUM.MOTION_MODE_STOPPED)

        # Init encoder (mode 0)
        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, 0x00000008)
        self.board.write_register(self.mc.REG.ABN_DECODER_PHI_E_PHI_M_OFFSET, 0x00000000)
        self.board.write_register(self.mc.REG.PHI_E_SELECTION, 0x00000001)
        self.board.write_register(self.mc.REG.PHI_E_EXT, 0x00000000)
        self.board.write_register(self.mc.REG.UQ_UD_EXT, 0x00001388)
        time.sleep(4)
        self.board.write_register(self.mc.REG.ABN_DECODER_COUNT, 0x00000000)
        # set position

        # Feedback selection
        self.board.write_register(self.mc.REG.PHI_E_SELECTION, 0x00000003)
        self.board.write_register(self.mc.REG.VELOCITY_SELECTION, 0x00000009)
        self.board.write_register(self.mc.REG.POSITION_SELECTION, self.mc.ENUM.VELOCITY_PHI_M_ABN)

        # # Switch to torque mode
        # switch from open loop to this mode causes a little skip in the motors?
        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, self.mc.ENUM.MOTION_MODE_TORQUE)
        self.board.write_register_field(self.mc.FIELD.PID_TORQUE_TARGET, 0)
        time.sleep(1/40)

        # encoder calibration ok, now for position calibration
        # user intervention is needed here.

        input("Hoist ready for zeroing, please manually put the hoist to the zero position and confirm with enter")
        self.board.write_register(self.mc.REG.PID_POSITION_ACTUAL, 458740)
        self.board.write_register(self.mc.REG.MODE_RAMP_MODE_MOTION, self.mc.ENUM.MOTION_MODE_POSITION)
        # assuming user has properly set actual position
        # top of container is at 150 cm, but center of mass is at 140
        # self.board.write_register(self.mc.REG.PID_POSITION_ACTUAL, int(130/21.22*65536))


    def _testMove(self):
        """Perform a test movement
        """
        self.setPositionMode()
        # Rotate right
        self.board.write_register(self.mc.REG.PID_POSITION_TARGET, 65536)
        time.sleep(2)
        # print(self.board.read_register(self.mc.REG.PID_POSITION_ACTUAL))

        # Rotate left
        self.board.write_register(self.mc.REG.PID_POSITION_TARGET, 0)
        time.sleep(2)
        # print(self.board.read_register(self.mc.REG.PID_POSITION_ACTUAL))

        # Stop
        self.board.write_register(self.mc.REG.PID_TORQUE_FLUX_TARGET, 0x00000000)