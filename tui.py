import curses
import logging
from functools import partial
import sys
import traceback

# Import the controller and configuration from the library file
from relay_control import RelayController, RELAY_PINS_CONFIG, DEFAULT_STATE_FILE, DEFAULT_LOG_FILE

# Note: This file assumes it will be run via curses.wrapper
# and receive a configured RelayController instance.

def draw_interface(stdscr, controller):
    """Draws the relay control interface using curses."""
    stdscr.clear()
    h, w = stdscr.getmaxyx()

    title = "Raspberry Pi Relay Control (TUI)" # Updated title slightly
    if w > len(title): stdscr.addstr(0, w // 2 - len(title) // 2, title, curses.A_BOLD)

    instructions = "Toggle: [1-4] | Quit: [q]"
    if h > 2 and w > len(instructions): stdscr.addstr(2, 1, instructions)

    y_offset = 4
    # Access relay info via the controller instance
    relay_pins = controller.relay_pins 
    all_states = controller.get_all_states()

    for relay_num in sorted(relay_pins.keys()):
        if h > (y_offset + relay_num - 1) and w > 20:
            pin = relay_pins[relay_num]
            is_on = all_states.get(relay_num, False)
            state_str = "ON" if is_on else "OFF"
            # Color pairs defined in main_curses_loop
            color = curses.color_pair(1) if is_on else curses.color_pair(2)
            status_line = f"Relay {relay_num} (GPIO {pin}): "
            stdscr.addstr(y_offset + relay_num - 1, 2, status_line)
            stdscr.addstr(state_str, color | curses.A_BOLD)

    stdscr.refresh()

def main_curses_loop(stdscr, controller):
    """Main curses application loop handling input and updates."""
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(200)

    if curses.has_colors():
        curses.start_color()
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)

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

# --- Main Execution Block (Entry point) ---

if __name__ == "__main__":
    setup_logging() # Configure logging first
    main_logger = logging.getLogger(__name__)
    main_logger.info("Starting Relay Control TUI Application")

    # Create the controller instance using imported config
    controller = RelayController(
        relay_pins=RELAY_PINS_CONFIG, 
        state_file=DEFAULT_STATE_FILE
        # logger_name can be customized if needed, defaults to 'RelayController'
    )

    # Attempt to set up the controller (GPIO, initial state)
    if not controller.setup():
        main_logger.critical("Controller setup failed. Check logs and permissions. Exiting.")
        sys.exit(1) # Exit if core setup fails

    # Run the TUI itself
    try:
        run_tui(controller)
    except Exception as e:
        # Catch errors specific to the TUI run phase
        main_logger.exception("An unexpected error occurred during TUI execution.")
    finally:
        # Ensure controller cleanup ALWAYS happens
        controller.cleanup()
        main_logger.info("Relay Control TUI Application Finished.")
