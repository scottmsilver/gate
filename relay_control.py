import RPi.GPIO as GPIO
import json
import os
import tempfile
import logging

# Import the GPIO manager singleton
from gpio_manager import manager as gpio_manager

# --- Global Configuration ---
RELAY_PINS_CONFIG = {
    1: 22, # Relay 1 -> GPIO 22
    2: 23, # Relay 2 -> GPIO 23
    3: 24, # Relay 3 -> GPIO 24
    4: 25, # Relay 4 -> GPIO 25
}
DEFAULT_STATE_FILE = "relay_state.json"
DEFAULT_LOG_FILE = "relay_control.log"

# Low level trigger configuration
RELAY_ON_STATE = GPIO.LOW
RELAY_OFF_STATE = GPIO.HIGH

# --- Core Logic Class ---
class RelayController:
    """Manages relay hardware, state persistence, and logging."""

    def __init__(self, relay_pins, state_file=DEFAULT_STATE_FILE, logger_name='RelayController'):
        self.relay_pins = relay_pins
        self.state_file = state_file
        self.logger = logging.getLogger(logger_name)
        self.relay_states = {relay_num: False for relay_num in self.relay_pins} # Holds internal logical state
        self._is_setup = False

    def _load_state(self):
        """Loads relay states from the state file if it exists."""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    loaded_states_str_keys = json.load(f)
                    loaded_states = {int(k): v for k, v in loaded_states_str_keys.items()}

                    if set(loaded_states.keys()) == set(self.relay_pins.keys()):
                        self.relay_states.update(loaded_states)
                        self.logger.info(f"Loaded state from {self.state_file}: {self.relay_states}")
                    else:
                        self.logger.warning(f"State file {self.state_file} keys mismatch config. Using defaults.")
            except (json.JSONDecodeError, IOError, ValueError) as e:
                self.logger.error(f"Error loading state from {self.state_file}: {e}. Using defaults.", exc_info=True)
                self.relay_states = {relay_num: False for relay_num in self.relay_pins} # Reset
            except Exception as e:
                self.logger.exception(f"Unexpected error loading state: {e}. Using defaults.")
                self.relay_states = {relay_num: False for relay_num in self.relay_pins} # Reset
        else:
            self.logger.info(f"State file {self.state_file} not found. Initializing defaults.")

    def _save_state(self):
        """Saves the current relay states atomically to the state file."""
        temp_file_path = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(self.state_file),
                                            prefix=os.path.basename(self.state_file) + '.tmp',
                                            delete=False) as tf:
                temp_file_path = tf.name
                json.dump(self.relay_states, tf, indent=4)
                tf.flush()
                os.fsync(tf.fileno())
            os.rename(temp_file_path, self.state_file)
            self.logger.debug(f"Atomically saved state to {self.state_file}")
        except (IOError, OSError, json.JSONDecodeError) as e:
            self.logger.error(f"Error saving state atomically: {e}", exc_info=True)
            if temp_file_path and os.path.exists(temp_file_path):
                try: os.remove(temp_file_path)
                except OSError as remove_err: self.logger.error(f"Error removing temp state file: {remove_err}", exc_info=True)
        except Exception as e:
            self.logger.exception(f"Unexpected error saving state: {e}")
            if temp_file_path and os.path.exists(temp_file_path):
                try: os.remove(temp_file_path)
                except OSError as remove_err: self.logger.error(f"Error removing temp state file: {remove_err}", exc_info=True)

    def setup(self):
        """Initializes GPIO, loads state, and applies initial pin states."""
        self.logger.info("Performing controller setup...")
        # Rely on the manager being initialized by the application entry point
        # Ensure GPIOManager is initialized (will raise error if not or conflicts)
        # The mode/warnings setting should happen ONCE in the main app.
        # We assume it's done before this controller's setup is called.
        # gpio_manager.initialize() # DON'T initialize here, do it in main app script
        
        self._load_state() # Load logical state
        self.logger.info("Setting up and applying initial pin states via GPIO Manager...")
        for relay_num, pin in self.relay_pins.items():
            # Setup pin using the manager
            gpio_manager.setup_pin(pin, GPIO.OUT)
            # Get logical state
            current_state = self.relay_states.get(relay_num, False)
            # Determine target GPIO state (LOW=ON, HIGH=OFF)
            target_gpio_state = RELAY_ON_STATE if current_state else RELAY_OFF_STATE
            # Set initial output using the manager
            gpio_manager.set_output(pin, target_gpio_state)
            self.logger.debug(f"  Relay {relay_num} (GPIO {pin}) initially set to {'ON' if current_state else 'OFF'}")
        self._is_setup = True
        self.logger.info("Controller setup complete.")
        return True

    def cleanup(self):
        """Cleans up GPIO resources if setup was successful."""
        # This controller NO LONGER performs GPIO.cleanup().
        # The main application using the GPIOManager is responsible for calling manager.cleanup_all()
        # We might want to release pins from the manager here if needed, but often not necessary.
        self.logger.info("Controller cleanup phase. GPIO hardware cleanup deferred to GPIOManager.")
        # Example: If we wanted to mark pins as no longer used by this controller:
        # if self._is_setup:
        #    for pin in self.relay_pins.values():
        #        try: gpio_manager.release_pin(pin)
        #        except Exception as e: self.logger.warning(f"Error releasing pin {pin}: {e}")
        
        self._is_setup = False # Mark controller as logically cleaned up

    def get_relay_state(self, relay_num):
        """Gets the current state of a specific relay."""
        if relay_num not in self.relay_pins:
            self.logger.warning(f"Attempted to get state for invalid relay: {relay_num}")
            return None # Or raise error
        return self.relay_states.get(relay_num, False)

    def get_all_states(self):
        """Gets the current state of all relays."""
        return self.relay_states.copy() # Return a copy

    def set_relay(self, relay_num, state):
        """Sets a specific relay to the desired state (True=ON, False=OFF)."""
        if not self._is_setup:
            self.logger.error("Cannot set relay: Controller not set up.")
            return False
        pin = self.relay_pins.get(relay_num)
        if pin is None:
             self.logger.warning(f"Attempted to set invalid relay number: {relay_num}")
             return False

        target_state_bool = bool(state) # Ensure boolean
        target_gpio_state = RELAY_ON_STATE if target_state_bool else RELAY_OFF_STATE
        
        try:
            # Use the manager to set the output
            gpio_manager.set_output(pin, target_gpio_state)
            # Update internal logical state
            self.relay_states[relay_num] = target_state_bool
            self.logger.info(f"Set Relay {relay_num} (GPIO {pin}) to {'ON' if target_state_bool else 'OFF'}")
            self._save_state() # Persist the change
            return True
        except Exception as e:
            self.logger.error(f"Failed to set Relay {relay_num} (GPIO {pin}): {e}", exc_info=True)
            return False

    def toggle_relay(self, relay_num):
        """Toggles the state of the specified relay."""
        current_state = self.get_relay_state(relay_num)
        if current_state is None:
            return False # Invalid relay number
        return self.set_relay(relay_num, not current_state)
