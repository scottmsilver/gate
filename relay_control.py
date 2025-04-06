import curses
import RPi.GPIO as GPIO
import time
import sys
import traceback

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

# Dictionary to keep track of the current state of each relay (True = ON, False = OFF)
relay_states = {relay_num: False for relay_num in RELAY_PINS}
# --- End Configuration ---

def setup_gpio():
    """Initializes GPIO pins for relay control."""
    try:
        GPIO.setmode(GPIO.BCM)  # Use Broadcom pin numbering scheme
        GPIO.setwarnings(False) # Disable GPIO warnings
        for relay_num, pin in RELAY_PINS.items():
            GPIO.setup(pin, GPIO.OUT)
            # Set initial state to OFF
            GPIO.output(pin, RELAY_OFF_STATE)
            relay_states[relay_num] = False
        print("GPIO setup complete.")
    except Exception as e:
        # GPIO setup can fail if permissions are insufficient or not on RPi
        print(f"Error setting up GPIO: {e}", file=sys.stderr)
        print("Ensure you are running on a Raspberry Pi and have necessary permissions (e.g., run with 'sudo' or user in 'gpio' group).", file=sys.stderr)
        raise # Re-raise the exception to be caught later

def cleanup_gpio():
    """Resets GPIO pins to default state."""
    print("\nCleaning up GPIO...")
    GPIO.cleanup()
    print("GPIO cleanup complete.")

def set_relay(relay_num, state):
    """
    Sets a specific relay to the desired state.

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
            break # Allow Ctrl+C to exit gracefully
        except Exception as e:
             # Log unexpected errors if possible, then break
             # In a real app, might log to a file
             # For now, just break the loop
             # Consider printing traceback outside curses wrapper
             curses.endwin() # Ensure terminal is restored
             print("An error occurred during the main loop:", file=sys.stderr)
             traceback.print_exc()
             raise # Re-raise after ending curses

def run_relay_control():
    """Sets up GPIO, runs the curses UI, and handles cleanup."""
    try:
        # Attempt GPIO setup first
        setup_gpio()

        # Run the curses application using wrapper for safe terminal handling
        curses.wrapper(main_loop)

    except ImportError:
        print("Error: RPi.GPIO library not found.", file=sys.stderr)
        print("Please install it: 'uv pip install RPi.GPIO'", file=sys.stderr)
    except RuntimeError as e:
        # RPi.GPIO often raises RuntimeError for permission issues or non-RPi hardware
        print(f"Runtime Error: {e}", file=sys.stderr)
        print("Ensure you are running on a Raspberry Pi with correct permissions.", file=sys.stderr)
    except Exception as e:
        # Catch any other unexpected errors during setup or curses init
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        traceback.print_exc()
    finally:
        # Attempt GPIO cleanup regardless of how the program exits
        # Check if GPIO module was successfully imported and mode set
        if 'GPIO' in sys.modules and GPIO.getmode() is not None:
             cleanup_gpio()
        else:
             print("Skipping GPIO cleanup as it wasn't initialized properly.")
        print("Application finished.")

if __name__ == "__main__":
    run_relay_control()
