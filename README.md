# Raspberry Pi Relay Control

This project provides a simple curses-based TUI (Text User Interface) to control an Elegoo 4-relay module connected to a Raspberry Pi's GPIO pins. It allows users to toggle relays on and off interactively.

The script maintains the state of the relays persistently using a JSON file (`relay_state.json`), ensuring that the relays return to their last known state upon script restart or system reboot. Logging is directed to `relay_control.log`.

## Hardware Setup

*   **Raspberry Pi:** Developed on a Raspberry Pi 4B.
*   **Relay Module:** Elegoo 4-channel Relay Module.
*   **Wiring:**
    *   Relay 1 <-> GPIO 22 (Pin 13)
    *   Relay 2 <-> GPIO 23 (Pin 16)
    *   Relay 3 <-> GPIO 24 (Pin 18)
    *   Relay 4 <-> GPIO 25 (Pin 22)
*   **Trigger Mode:** Low-Level Trigger (Setting GPIO pin LOW turns the relay ON).

## Setup

1.  **Clone/Copy:** Get the project files (`relay_control.py`, `requirements.txt`, `.gitignore`).
2.  **Create Virtual Environment:**
    ```bash
    python3 -m venv .venv
    ```
3.  **Install Dependencies:** The project uses `uv` for package management. Make sure `uv` is installed and accessible (see `uv` documentation if needed: [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)).
    ```bash
    # Activate the environment (optional but recommended)
    source .venv/bin/activate 
    
    # Install using uv (ensure uv is in PATH or use full path e.g., $HOME/.local/bin/uv)
    uv pip install -r requirements.txt 
    ```
    *Alternatively, if not using `uv` or `uv` is unavailable:*
    ```bash
    # Activate the environment
    source .venv/bin/activate 
    
    # Install using standard pip
    pip install -r requirements.txt
    ```

## Usage

The script requires root privileges to access GPIO pins.

1.  **Navigate to Project Directory:**
    ```bash
    cd /path/to/gate 
    ```
2.  **Run the Script:**
    ```bash
    # Make sure virtual environment is active or use the full path to python
    sudo .venv/bin/python relay_control.py
    ```
3.  **Interface:**
    *   Press keys `1`, `2`, `3`, or `4` to toggle the corresponding relay.
    *   The status (ON/OFF) will update in the interface.
    *   Press `q` to quit the application.

## State and Logging

*   **State:** The current state of the relays is saved in `relay_state.json`.
*   **Logs:** Detailed operation logs and errors are saved in `relay_control.log`.
