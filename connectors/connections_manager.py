# connections_manager.py
"""
connections_manager.py
----------------------
Manages hypervisor connections and sessions

Holds in-memory session/connections to various hypervisors.

Creates connections to hypervisors and VMs as needed.
    Connections are proxy objects to hypervisors/VMs.
Reuses existing sessions when possible.

"""

import uuid
from common.app_setup import setup_logging
from typing import Protocol

from connectors.hypervisor_interface import HypervisorSessionProtocol
from connectors.mock_hypervisor_connector import MockvisorSession

######################### Sessions #########################


## the manager is this module itself

# variable to hold active sessions:

_active_sessions: dict[tuple[str, str], 'HypervisorSessionProtocol'] = {}
# key: (hostURL, user) tuple
# value: HypervisorSessionProtocol instance
# This allows unique sessions per (hostURL, user) pair.

# create a session. If a matching session already exists, return it.
def get_session(hypervisor_type: str, host_URL: str, user: str, password: str) -> HypervisorSessionProtocol:
    """
    Get or create a hypervisor session for the given parameters.
    Reuses existing sessions if one matches the (hostURL, user) pair.
    """
    global _active_sessions
    key = (host_URL, user)
    if key in _active_sessions:
        return _active_sessions[key]
        # by now, we do not erase sessions, even dead ones

    # else:
    # Create a new session based on hypervisor_type
    if hypervisor_type == "mock_hypervisor":
        session = MockvisorSession(host_URL, user, password)
    # Add other hypervisor types here as needed
    else:
        raise ValueError(f"Unsupported hypervisor type: {hypervisor_type}")
    
    session.connect()
    _active_sessions[key] = session
    return session