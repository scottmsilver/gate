import RPi.GPIO as GPIO
import logging
import threading

class GPIOManager:
    """
    Manages global RPi.GPIO settings (mode, warnings) and cleanup 
    to prevent conflicts between different modules using GPIO.
    """
    _instance = None
    _lock = threading.Lock()
    _initialized = False
    _mode_set = None
    _warnings_set = False # Default for RPi.GPIO is True

    def __new__(cls, *args, **kwargs):
        # Basic singleton implementation
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._logger = logging.getLogger("GPIOManager") # Corrected quotes
                cls._instance._registered_pins = set() # Track pins actively managed
                cls._instance._cleaned_up = False
            return cls._instance

    def initialize(self, mode=GPIO.BCM, warnings=False):
        """Initializes GPIO mode and warnings, if not already done."""
        with self._lock:
            if self._cleaned_up:
                self._logger.error("Cannot initialize GPIO, already cleaned up.")
                raise RuntimeError("GPIOManager already cleaned up.")
                
            if self._initialized:
                # Verify consistency if called again
                if self._mode_set != mode:
                    self._logger.error(f"GPIO mode conflict: Already set to {self._mode_set}, requested {mode}")
                    raise RuntimeError(f"GPIO mode conflict: Already set to {self._mode_set}, requested {mode}")
                if self._warnings_set != warnings:
                    self._logger.warning(f"GPIO warnings conflict: Already set to {self._warnings_set}, requested {warnings}")
                    # GPIO.setwarnings(warnings) 
                    # self._warnings_set = warnings
                return # Already initialized correctly

            try:
                self._logger.info(f"Initializing GPIO: Mode={mode}, Warnings={warnings}")
                GPIO.setmode(mode)
                GPIO.setwarnings(warnings)
                self._mode_set = mode
                self._warnings_set = warnings
                self._initialized = True
                self._logger.info("GPIO initialized successfully.")
            except Exception as e:
                self._logger.error(f"Failed to initialize GPIO: {e}", exc_info=True)
                raise # Re-raise to indicate failure

    def setup_pin(self, pin, direction, initial=None, pull_up_down=None):
        """Sets up a specific GPIO pin, registering it with the manager."""
        with self._lock:
            if not self._initialized:
                self._logger.error("Cannot setup pin: GPIOManager not initialized.")
                raise RuntimeError("GPIOManager not initialized.")
            if self._cleaned_up:
                self._logger.error(f"Cannot setup pin {pin}: GPIOManager already cleaned up.")
                raise RuntimeError("GPIOManager already cleaned up.")

            try:
                kwargs = {}
                if initial is not None:
                    kwargs['initial'] = initial
                if pull_up_down is not None:
                    kwargs['pull_up_down'] = pull_up_down

                self._logger.debug(f"Setting up pin {pin}: Direction={direction}, Options={kwargs}")
                GPIO.setup(pin, direction, **kwargs)
                self._registered_pins.add(pin)
            except Exception as e:
                self._logger.error(f"Failed to setup pin {pin}: {e}", exc_info=True)
                raise

    def set_output(self, pin, value):
        """Sets the output value of a pin."""
        with self._lock:
            if pin not in self._registered_pins:
                self._logger.warning(f"Attempting to set output on unregistered or cleaned pin {pin}")
                # raise RuntimeError(f"Pin {pin} not registered with GPIOManager")
            if self._cleaned_up:
                 self._logger.error(f"Cannot set output for pin {pin}: GPIOManager already cleaned up.")
                 raise RuntimeError("GPIOManager already cleaned up.")
            try:
                GPIO.output(pin, value)
            except Exception as e:
                self._logger.error(f"Failed to set output for pin {pin}: {e}", exc_info=True)
                raise
                
    def read_input(self, pin):
        """Reads the input value of a pin."""
        with self._lock:
            if pin not in self._registered_pins:
                 self._logger.warning(f"Attempting to read input from unregistered or cleaned pin {pin}")
                 # raise RuntimeError(f"Pin {pin} not registered with GPIOManager")
            if self._cleaned_up:
                 self._logger.error(f"Cannot read input for pin {pin}: GPIOManager already cleaned up.")
                 raise RuntimeError("GPIOManager already cleaned up.")
            try:
                 return GPIO.input(pin)
            except Exception as e:
                 self._logger.error(f"Failed to read input for pin {pin}: {e}", exc_info=True)
                 raise

    def release_pin(self, pin):
        """Optional: Method to explicitly unregister a pin if needed."""
        with self._lock:
             if pin in self._registered_pins:
                 self._logger.debug(f"Releasing pin {pin} from active management.")
                 self._registered_pins.discard(pin)
                 # Note: This does NOT call GPIO.cleanup(pin).

    def cleanup_all(self):
        """Performs global GPIO cleanup. Should only be called once on app exit."""
        with self._lock:
            if not self._initialized:
                self._logger.warning("Skipping cleanup: GPIO was never initialized.")
                return
            if self._cleaned_up:
                self._logger.warning("Skipping cleanup: Already performed.")
                return
                
            self._logger.info("Performing global GPIO cleanup...")
            try:
                GPIO.cleanup()
                self._cleaned_up = True
                self._initialized = False # Reset state
                self._registered_pins.clear()
                self._logger.info("Global GPIO cleanup complete.")
            except Exception as e:
                self._logger.error(f"Error during GPIO cleanup: {e}", exc_info=True)
                # Continue even if cleanup fails

# Create a default instance for easy import
manager = GPIOManager()
