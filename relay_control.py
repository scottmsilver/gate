import curses
import RPi.GPIO as GPIO
import time
import sys
import traceback
import json
import os
import tempfile
import logging

# --- Global Flags ---
gpio_setup_successful = False # Track if GPIO setup completed

# --- Logging Configuration ---
LOG_FILE = "relay_control.log"
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE), 
        # logging.StreamHandler() 
    ]
)
logger = logging.getLogger(__name__) 

# --- Configuration ---
# Map relay numbers (1-4) to BCM GPIO pin numbers
RELAY_PINS = {
    1: 22, # Relay 1 connected to GPIO 22
    2: 23, # Relay 2 connected to GPIO 23
    3: 24, # Relay 3 connected to GPIO 24
    4: 25, # Relay 4 connected to GPIO 25
}

# Low level trigger: GPIO.LOW turns the relay ON, GPIO.HIGH turns it OFF.
RELAY_ON_STATE = GPIO.LOW
RELAY_OFF_STATE = GPIO.HIGH

# State file path
STATE_FILE = "relay_state.json"

# Dictionary to keep track of the current state of each relay (True = ON, False = OFF)
# Initialize with defaults, will be overwritten by load_state if file exists
relay_states = {relay_num: False for relay_num in RELAY_PINS}

def load_state():
    """Loads relay states from the state file if it exists."""
    global relay_states
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                loaded_states_str_keys = json.load(f)
                # Convert string keys from JSON back to integers
                loaded_states = {int(k): v for k, v in loaded_states_str_keys.items()}

                # Validate loaded state keys match current config
                if set(loaded_states.keys()) == set(RELAY_PINS.keys()):
                    relay_states.update(loaded_states)
                    logger.info(f"Loaded state from {STATE_FILE}: {relay_states}")
                else:
                    logger.warning(f"State file {STATE_FILE} keys mismatch config. Using defaults.")
                    # Optionally: delete or rename the invalid state file here
        except (json.JSONDecodeError, IOError, ValueError) as e:
            logger.error(f"Error loading state from {STATE_FILE}: {e}. Using default states.", exc_info=True)
            # Reset to default states in case partial load occurred or file was corrupt
            relay_states = {relay_num: False for relay_num in RELAY_PINS}
        except Exception as e:
            logger.exception(f"Unexpected error loading state: {e}. Using default states.")
            relay_states = {relay_num: False for relay_num in RELAY_PINS}
    else:
        logger.info(f"State file {STATE_FILE} not found. Initializing with default OFF states.")

def save_state():
    """Saves the current relay states atomically to the state file."""
    temp_file_path = None
    try:
        # Create a temporary file in the same directory to ensure atomic rename works
        # across filesystems (though usually not an issue in this context)
        # delete=False is important so we can rename it later
        with tempfile.NamedTemporaryFile(mode='w', dir=os.path.dirname(STATE_FILE), 
                                        prefix=os.path.basename(STATE_FILE) + '.tmp', 
                                        delete=False) as tf:
            temp_file_path = tf.name
            json.dump(relay_states, tf, indent=4)
            # Ensure data is written to the OS buffer
            tf.flush()
            # Ensure data is written from OS buffer to disk
            os.fsync(tf.fileno())
        
        # Atomically replace the old state file with the new one
        os.rename(temp_file_path, STATE_FILE)
        logger.debug(f"Atomically saved state to {STATE_FILE}") 

    except (IOError, OSError, json.JSONDecodeError) as e:
        logger.error(f"Error saving state atomically to {STATE_FILE}: {e}", exc_info=True)
        # Clean up the temporary file if it still exists after an error
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError as remove_err:
                logger.error(f"Error removing temporary state file {temp_file_path}: {remove_err}", exc_info=True)
    except Exception as e:
        logger.exception(f"Unexpected error saving state: {e}")
        # Clean up the temporary file if it still exists after an error
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError as remove_err:
                logger.error(f"Error removing temporary state file {temp_file_path}: {remove_err}", exc_info=True)

def setup_gpio():
    """Initializes GPIO pins for relay control, loading previous state."""
    global gpio_setup_successful # Declare intent to modify global flag
    # Load state from file first
    load_state()

    try:
        GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering scheme
        GPIO.setwarnings(False) # Disable GPIO warnings

        logger.info("Applying loaded/default states to GPIO pins...")
        for relay_num, pin in RELAY_PINS.items():
            GPIO.setup(pin, GPIO.OUT)
            # Set pin state based on loaded/default state
            current_state = relay_states.get(relay_num, False) # Default to False if somehow missing
            target_gpio_state = RELAY_ON_STATE if current_state else RELAY_OFF_STATE
            GPIO.output(pin, target_gpio_state)
            logger.debug(f"  Relay {relay_num} (GPIO {pin}) set to {'ON' if current_state else 'OFF'}") 

        logger.info("GPIO setup complete.")
        gpio_setup_successful = True # Set flag on successful completion

    except Exception as e:
        # GPIO setup can fail if permissions are insufficient or not on RPi
        logger.error(f"Error setting up GPIO: {e}", exc_info=True)
        logger.error("Ensure you are running on a Raspberry Pi and have necessary permissions (e.g., run with 'sudo').")
        raise # Re-raise the exception to be caught later

def cleanup_gpio():
    """Resets GPIO pins to default state."""
    logger.info("Cleaning up GPIO...")
    # Note: We do NOT save state on cleanup, as cleanup often implies shutdown
    # or error, and we want the state saved during normal operation.
    GPIO.cleanup()
    logger.info("GPIO cleanup complete.")

def set_relay(relay_num, state):
    """
    Sets a specific relay to the desired state and saves the new state.

    Args:
        relay_num (int): The number of the relay (1-4).
        state (bool): True to turn the relay ON, False to turn it OFF.
    """
    if relay_num not in RELAY_PINS:
        # Log error or notify user in curses window if possible
        return

    pin = RELAY_PINS[relay_num]
    target_state = RELAY_ON_STATE if state else RELAY_OFF_STATE
    GPIO.output(pin, target_state)
    relay_states[relay_num] = state
    logger.info(f"Set Relay {relay_num} (GPIO {RELAY_PINS[relay_num]}) to {'ON' if state else 'OFF'}")
    save_state() # Save the state immediately after changing it

def toggle_relay(relay_num):
    """Toggles the state of the specified relay."""
    if relay_num in relay_states:
        current_state = relay_states[relay_num]
        set_relay(relay_num, not current_state)

def draw_interface(stdscr):
    """Draws the relay control interface using curses."""
    stdscr.clear()
    h, w = stdscr.getmaxyx() # Get screen dimensions

    # --- Title ---
    title = "Raspberry Pi Relay Control"
    if w > len(title):
        stdscr.addstr(0, w // 2 - len(title) // 2, title, curses.A_BOLD)

    # --- Instructions ---
    instructions = "Toggle: [1-4] | Quit: [q]"
    if h > 2 and w > len(instructions):
        stdscr.addstr(2, 1, instructions)

    # --- Relay Status ---
    y_offset = 4
    for relay_num in sorted(RELAY_PINS.keys()):
        if h > (y_offset + relay_num -1) and w > 20: # Check if space allows
            pin = RELAY_PINS[relay_num]
            state_str = "ON" if relay_states[relay_num] else "OFF"
            color = curses.color_pair(1) if relay_states[relay_num] else curses.color_pair(2)
            status_line = f"Relay {relay_num} (GPIO {pin}): "
            stdscr.addstr(y_offset + relay_num - 1, 2, status_line)
            stdscr.addstr(state_str, color | curses.A_BOLD)

    # --- Footer/Status Bar (Optional) ---
    # status_message = "Status: OK"
    # if h > 1 and w > len(status_message):
    #    stdscr.addstr(h - 1, 1, status_message)

    stdscr.refresh()

def main_loop(stdscr):
    """Main application loop handling input and updates."""
    # Curses settings
    curses.curs_set(0)    # Hide the cursor
    stdscr.nodelay(True) # Make getch non-blocking
    stdscr.timeout(200)  # Refresh screen roughly 5 times/sec (or on input)

    # Initialize colors (if terminal supports it)
    if curses.has_colors():
        curses.start_color()
        # Pair 1: Green text for ON state
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        # Pair 2: Red text for OFF state
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)

    while True:
        try:
            draw_interface(stdscr)
            key = stdscr.getch() # Get user input, non-blocking

            if key == ord('q') or key == ord('Q'):
                break # Exit loop
            elif ord('1') <= key <= ord('4'):
                relay_num_to_toggle = int(chr(key))
                toggle_relay(relay_num_to_toggle)
            elif key == curses.KEY_RESIZE:
                # Handle terminal resize gracefully
                # curses.resize_term(*stdscr.getmaxyx()) # May not work reliably everywhere
                stdscr.clear() # Force redraw on next loop iteration

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received, exiting.")
            break # Allow Ctrl+C to exit gracefully
        except Exception as e:
             # Log unexpected errors if possible, then break
             logger.exception("An error occurred during the main loop:")
             curses.endwin() # Ensure terminal is restored
             # print("An error occurred during the main loop:", file=sys.stderr)
             # traceback.print_exc()
             raise # Re-raise after ending curses

def run_relay_control():
    """Sets up GPIO, runs the curses UI, and handles cleanup."""
    logger.info("Starting Relay Control Application")
    global gpio_setup_successful # Access the global flag
    gpio_setup_successful = False # Ensure it's False at the start of each run

    try:
        # Attempt GPIO setup first
        setup_gpio()

        # Run the curses application using wrapper for safe terminal handling
        curses.wrapper(main_loop)

    except ImportError as e:
        logger.critical("RPi.GPIO library not found. Please install it: 'pip install RPi.GPIO'", exc_info=True)
        # print("Error: RPi.GPIO library not found.", file=sys.stderr)
        # print("Please install it: 'pip install RPi.GPIO'", file=sys.stderr)
    except RuntimeError as e:
        # RPi.GPIO often raises RuntimeError for permission issues or non-RPi hardware
        logger.critical(f"Runtime Error during GPIO setup/access: {e}", exc_info=True)
        logger.critical("Ensure you are running on a Raspberry Pi with correct permissions.")
        # print(f"Runtime Error: {e}", file=sys.stderr)
        # print("Ensure you are running on a Raspberry Pi with correct permissions.", file=sys.stderr)
    except Exception as e:
        # Catch any other unexpected errors during setup or curses init
        logger.exception(f"An unexpected error occurred during initialization or shutdown: {e}")
        # print(f"An unexpected error occurred: {e}", file=sys.stderr)
        # traceback.print_exc()
    finally:
        # Attempt GPIO cleanup regardless of how the program exits
        # Check if GPIO setup was marked as successful
        if gpio_setup_successful:
             cleanup_gpio()
        else:
             logger.warning("Skipping GPIO cleanup as setup did not complete successfully.")
        logger.info("Relay Control Application Finished.")

if __name__ == "__main__":
    run_relay_control()
