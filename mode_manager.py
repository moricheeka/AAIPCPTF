# -*- coding: utf-8 -*-
"""
AAIPCPTF Mode-Selector helper.
Detects tokens like 'mode:pause' in user input
and updates metadata["mode_state"] accordingly.
"""
def handle_mode(user_msg: str, metadata: dict) -> bool:
    if 'mode:' not in user_msg:
        return False
    token = user_msg.split('mode:')[1].split()[0].strip()
    if token in {"pause", "resume", "stop", "stop_forget", "restart"}:
        metadata["mode_state"] = token
        return True
        
        # OPTIONAL default branch – ignore a harmless “on” click
    if token == "on":
        return True            # nothing to update, but treat as handled

    return False
