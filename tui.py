import curses
import logging
from functools import partial
import sys
import traceback
import time

# Import the controller and configuration from the library file
from relay_control import RelayController, RELAY_PINS_CONFIG, DEFAULT_STATE_FILE, DEFAULT_LOG_FILE
import RPi.GPIO as GPIO # Keep for constants if needed

# Import the manager
from gpio_manager import manager as gpio_manager

# Note: This file assumes it will be run via curses.wrapper
# and receive a configured RelayController instance.

def draw_interface(stdscr, controller):
    """Draws the relay control interface using curses."""
    stdscr.clear()
    h, w = stdscr.getmaxyx()

    title = "Raspberry Pi Relay Control (TUI)" # Updated title slightly
    if w > len(title): stdscr.addstr(0, w // 2 - len(title) // 2, title, curses.A_BOLD)

    instructions = "Toggle: [1-4] | Momentary (2s): [a-d] | Quit: [q]"
    if h > 2 and w > len(instructions): stdscr.addstr(2, 1, instructions)

    y_offset = 4
    # Access relay info via the controller instance
    relay_pins = controller.relay_pins 
    all_states = controller.get_all_states()

    # Initialize color pairs if possible
    if curses.has_colors():
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK) # ON
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)   # OFF
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK) # PULSING
    COLOR_ON = curses.color_pair(1) if curses.has_colors() else curses.A_REVERSE
    COLOR_OFF = curses.color_pair(2) if curses.has_colors() else curses.A_NORMAL
    COLOR_PULSING = curses.color_pair(3) | curses.A_BOLD if curses.has_colors() else curses.A_BLINK

    for relay_num in sorted(relay_pins.keys()):
        if h > (y_offset + relay_num - 1) and w > 20:
            pin = relay_pins[relay_num]
            state_str = f"Relay {relay_num} (GPIO {pin}): "

            # Check pulsing state first
            if controller.is_pulsing(relay_num):
                status = "PULSING"
                color = COLOR_PULSING
            else:
                # Get persistent state if not pulsing
                state = controller.get_relay_state(relay_num)
                if state:
                    status = "ON"
                    color = COLOR_ON
                else:
                    status = "OFF"
                    color = COLOR_OFF

            # Draw relay status line
            stdscr.addstr(y_offset + relay_num - 1, 2, state_str)
            stdscr.addstr(status, color | curses.A_BOLD)

    stdscr.refresh()

def main_curses_loop(stdscr, controller):
    """Main curses application loop handling input and updates."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(200)

    logger = logging.getLogger(__name__) # Use logger from the main script's config

    while True:
        try:
            draw_interface(stdscr, controller)
            key = stdscr.getch()

            if key == ord('q') or key == ord('Q'):
                logger.info("Quit key pressed, exiting UI loop.")
                break
            elif ord('1') <= key <= ord('4'):
                relay_num_to_toggle = int(chr(key))
                success = controller.toggle_relay(relay_num_to_toggle)
                if not success:
                    logger.warning(f"Failed to toggle relay {relay_num_to_toggle}")
            elif key == ord('a'):
                logger.debug("Momentary key 'a' pressed for Relay 1.")
                controller.pulse_relay(1)
            elif key == ord('b'):
                logger.debug("Momentary key 'b' pressed for Relay 2.")
                controller.pulse_relay(2)
            elif key == ord('c'):
                logger.debug("Momentary key 'c' pressed for Relay 3.")
                controller.pulse_relay(3)
            elif key == ord('d'):
                logger.debug("Momentary key 'd' pressed for Relay 4.")
                controller.pulse_relay(4)
            elif key == curses.KEY_RESIZE:
                stdscr.clear()

        except KeyboardInterrupt:
            logger.info("KeyboardInterrupt received, exiting UI loop.")
            break
        except Exception as e:
            logger.exception("An error occurred during the curses UI loop:")
            raise # Re-raise so curses.wrapper handles cleanup

def run_tui(controller):
    """Initializes and runs the curses TUI."""
    logger = logging.getLogger(__name__)
    try:
        # Use functools.partial to pass the controller instance to the curses loop function
        curses.wrapper(partial(main_curses_loop, controller=controller))
    except curses.error as e:
        logger.exception("Curses error occurred. Is the terminal compatible?")
        print(f"Curses Error: {e}\nIs your terminal compatible (e.g., TERM=xterm)?", file=sys.stderr)
    except Exception as e:
        logger.exception("An unexpected error occurred during curses wrapper execution.")
        # Attempt to print to stderr as curses might be unavailable
        print(f"Unexpected Error during TUI execution: {e}", file=sys.stderr)
        traceback.print_exc() # Print traceback for more details

# --- Logging Setup (Moved here from relay_control.py) ---

def setup_logging(log_file=DEFAULT_LOG_FILE, level=logging.INFO):
    """Configures global logging for the application."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            # logging.StreamHandler() # Uncomment for console output
        ]
    )
    # Log the configuration attempt
    logging.getLogger(__name__).info(f"Logging configured. Level: {logging.getLevelName(level)}, File: {log_file}")

def main():
    """Main application entry point."""
    logger = logging.getLogger(__name__)
    setup_logging() # Setup logging first
    logger.info("Starting Relay Control TUI Application")

    try:
        # Initialize the GPIO Manager FIRST (after logging is set up)
        logger.info("Initializing GPIO Manager...")
        gpio_manager.initialize() # Use default BCM mode and warnings=False
        logger.info("GPIO Manager initialized.")

        # Now create and setup the controller
        controller = RelayController(relay_pins=RELAY_PINS_CONFIG, state_file=DEFAULT_STATE_FILE)
        logger.info("Setting up Relay Controller...")
        if not controller.setup():
            logger.error("Failed to setup relay controller. Exiting.")
            sys.exit(1) # Exit if setup fails
        logger.info("Relay Controller setup complete.")

        # Run the curses TUI wrapper via main()
        logger.info("Starting Curses TUI wrapper...")
        run_tui(controller)

    except Exception as e:
        # Basic fallback logging if main setup fails early
        print(f"Unhandled exception before full logger setup: {e}")
        print(traceback.format_exc())
        # Fallback cleanup if manager might have been initialized
        try:
            gpio_manager.cleanup_all()
        except Exception as cleanup_e:
            print(f"Error during fallback cleanup: {cleanup_e}")
        sys.exit(1)

    finally:
        # Cleanup is now handled within main's finally block
        logger.info("Performing application cleanup...")
        if 'controller' in locals() and controller is not None:
            controller.cleanup() 
        logger.info("Performing global GPIO cleanup via manager...")
        gpio_manager.cleanup_all()
        logger.info("Application finished.")

if __name__ == "__main__":
    main()
