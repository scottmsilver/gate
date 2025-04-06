import RPi.GPIO as GPIO
import json
import os
import tempfile
import logging

# --- Global Configuration (can be moved or passed differently if needed) ---
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
        self.relay_states = {relay_num: False for relay_num in self.relay_pins}
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
        if self._is_setup:
            self.logger.warning("Setup already completed.")
            return True
        
        self.logger.info("Performing controller setup...")
        self._load_state() # Load state before setting up GPIO
        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            self.logger.info("Applying initial GPIO pin states...")
            for relay_num, pin in self.relay_pins.items():
                GPIO.setup(pin, GPIO.OUT)
                current_state = self.relay_states.get(relay_num, False)
                target_gpio_state = RELAY_ON_STATE if current_state else RELAY_OFF_STATE
                GPIO.output(pin, target_gpio_state)
                self.logger.debug(f"  Relay {relay_num} (GPIO {pin}) initially set to {'ON' if current_state else 'OFF'}")
            self._is_setup = True
            self.logger.info("Controller setup complete.")
            return True
        except Exception as e:
            self.logger.error(f"GPIO setup failed: {e}", exc_info=True)
            self.logger.error("Ensure running on RPi with permissions (sudo?).")
            self._is_setup = False
            return False # Indicate failure

    def cleanup(self):
        """Cleans up GPIO resources if setup was successful."""
        if self._is_setup:
            self.logger.info("Cleaning up GPIO...")
            GPIO.cleanup()
            self.logger.info("GPIO cleanup complete.")
            self._is_setup = False # Mark as cleaned up
        else:
            self.logger.warning("Skipping cleanup as GPIO was not successfully setup.")

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
        if relay_num not in self.relay_pins:
            self.logger.warning(f"Attempted to set invalid relay: {relay_num}")
            return False

        pin = self.relay_pins[relay_num]
        target_state_bool = bool(state) # Ensure boolean
        target_gpio_state = RELAY_ON_STATE if target_state_bool else RELAY_OFF_STATE
        
        try:
            GPIO.output(pin, target_gpio_state)
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
