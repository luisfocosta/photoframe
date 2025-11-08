import sys
import subprocess
# import ctypes
import logging

def sleep_now():
    """
    Puts the Windows host to sleep using the Windows API.

    Raises:
        RuntimeError: If the script is not running on Windows
        OSError: If there's an error calling the Windows API
    """
    if sys.platform != "win32":
        raise RuntimeError("This script only runs on Windows.")

    try:
        subprocess.run(
            ["rundll32.exe", "powrprof.dll,SetSuspendState", "Sleep"],
            shell=False,
            check=True,
        )
        # # Load the PowrProf.dll library
        # powrprof = ctypes.WinDLL("PowrProf.dll")

        # # Prototype: BOOLEAN SetSuspendState(BOOLEAN Hibernate, BOOLEAN ForceCritical, BOOLEAN DisableWakeEvent);
        # powrprof.SetSuspendState.argtypes = (ctypes.c_bool, ctypes.c_bool, ctypes.c_bool)
        # powrprof.SetSuspendState.restype = ctypes.c_bool

        # # Call: (Hibernate=False, ForceCritical=False, DisableWakeEvent=False)
        # # Hibernate=False means sleep (not hibernate)
        # # ForceCritical=False means don't force critical processes
        # # DisableWakeEvent=False means allow wake events
        # ok = powrprof.SetSuspendState(False, False, False)

        # if not ok:
        #     logging.warning("SetSuspendState returned False - sleep may not have been initiated")
        #     return False

    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to load PowrProf.dll or call SetSuspendState: {e}")
        raise OSError(f"Error putting system to sleep: {e}")
    except Exception as e:
        logging.error(f"Unexpected error in sleep_now(): {e}")
        raise
