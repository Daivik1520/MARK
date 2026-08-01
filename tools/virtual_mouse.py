"""
MARK — Virtual Mouse Tool
Provides virtual mouse control for system screen cursor & IoT floorplan interactive canvas.
Supports relative movement, D-pad directional steps, trackpad gestures, and IoT device clicks.
"""

import math
from tools.ghost_cursor import move_mouse, click_at, scroll_screen
from tools.iot_controller import get_iot_state_dict, control_iot_device

_VIRTUAL_MOUSE_STATE = {
    "x": 500,
    "y": 300,
    "canvas_w": 650,
    "canvas_h": 450,
    "mode": "desktop",  # "desktop" or "iot_canvas"
    "last_targeted_iot": None
}


def get_virtual_mouse_state():
    """Get current Virtual Mouse state."""
    return _VIRTUAL_MOUSE_STATE.copy()


def move_virtual_mouse(x: int, y: int, relative: bool = False, mode: str = None) -> str:
    """
    Move the Virtual Mouse cursor to absolute or relative coordinates.
    
    Args:
        x: X coordinate or X offset
        y: Y coordinate or Y offset
        relative: True if (x, y) are deltas to add to current position
        mode: "desktop" (macOS cursor) or "iot_canvas" (Virtual IoT floorplan overlay)
    """
    global _VIRTUAL_MOUSE_STATE
    
    if mode:
        _VIRTUAL_MOUSE_STATE["mode"] = mode
        
    try:
        x, y = int(x), int(y)
    except (ValueError, TypeError):
        return "❌ Invalid coordinates. Use integers."

    if relative:
        _VIRTUAL_MOUSE_STATE["x"] += x
        _VIRTUAL_MOUSE_STATE["y"] += y
    else:
        _VIRTUAL_MOUSE_STATE["x"] = x
        _VIRTUAL_MOUSE_STATE["y"] = y

    # Clamping
    _VIRTUAL_MOUSE_STATE["x"] = max(0, min(_VIRTUAL_MOUSE_STATE["x"], 1920))
    _VIRTUAL_MOUSE_STATE["y"] = max(0, min(_VIRTUAL_MOUSE_STATE["y"], 1080))
    
    curr_x = _VIRTUAL_MOUSE_STATE["x"]
    curr_y = _VIRTUAL_MOUSE_STATE["y"]
    curr_mode = _VIRTUAL_MOUSE_STATE["mode"]

    # Desktop mode dispatch
    if curr_mode == "desktop":
        os_res = move_mouse(curr_x, curr_y)
        return f"🖱️ Virtual Mouse (Desktop) moved to ({curr_x}, {curr_y})"

    # IoT Canvas mode dispatch & collision check
    targeted = _check_iot_collision(curr_x, curr_y)
    _VIRTUAL_MOUSE_STATE["last_targeted_iot"] = targeted
    
    target_str = f" → Hovering over 💡 '{targeted['name']}'" if targeted else ""
    return f"🖱️ Virtual Mouse (IoT Canvas) moved to ({curr_x}, {curr_y}){target_str}"


def virtual_mouse_dpad(direction: str, step: int = 50) -> str:
    """
    Move Virtual Mouse using D-pad directional controls.
    
    Args:
        direction: "up", "down", "left", "right", "up-left", "up-right", "down-left", "down-right"
        step: Movement distance in pixels (default 50px)
    """
    dir_clean = direction.lower().strip()
    dx, dy = 0, 0
    
    if "up" in dir_clean:
        dy -= step
    if "down" in dir_clean:
        dy += step
    if "left" in dir_clean:
        dx -= step
    if "right" in dir_clean:
        dx += step
        
    if dx == 0 and dy == 0:
        return f"❌ Invalid direction '{direction}'. Use up, down, left, right."

    return move_virtual_mouse(dx, dy, relative=True)


def virtual_mouse_click(button: str = "left") -> str:
    """
    Perform a Virtual Mouse click at current cursor location.
    If hovering over an IoT device on the canvas, toggles that device!
    Otherwise clicks on macOS desktop if mode is desktop.
    """
    global _VIRTUAL_MOUSE_STATE
    curr_x = _VIRTUAL_MOUSE_STATE["x"]
    curr_y = _VIRTUAL_MOUSE_STATE["y"]
    curr_mode = _VIRTUAL_MOUSE_STATE["mode"]
    
    if curr_mode == "iot_canvas":
        targeted = _check_iot_collision(curr_x, curr_y)
        if targeted:
            res = control_iot_device(targeted["id"], "toggle")
            return f"🖱️ Virtual Mouse Clicked on IoT Device '{targeted['name']}'! {res}"
        return f"🖱️ Virtual Mouse Clicked at IoT Canvas ({curr_x}, {curr_y}) (No device at position)"
        
    # Desktop mode
    click_res = click_at(curr_x, curr_y, button=button)
    return f"🖱️ Virtual Mouse Clicked Desktop at ({curr_x}, {curr_y}): {click_res}"


def virtual_mouse_scroll(direction: str = "down", amount: str = "3") -> str:
    """Scroll using Virtual Mouse."""
    return scroll_screen(direction=direction, amount=amount)


def _check_iot_collision(x: int, y: int, radius: int = 40):
    """Check if Virtual Mouse cursor collides with any IoT device on canvas grid."""
    devices = get_iot_state_dict()
    for d_id, dev in devices.items():
        pos = dev.get("pos", {"x": 0, "y": 0})
        dist = math.hypot(x - pos["x"], y - pos["y"])
        if dist <= radius:
            return dev
    return None
