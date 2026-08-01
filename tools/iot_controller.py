"""
MARK — IoT Controller
Manages Smart Devices (Lights, Plugs, Thermostats, TVs, ESP32 nodes)
Supports voice control, interactive floorplan targeting, and optional HTTP webhooks.
"""

import json
import os
import requests

IOT_STORE_PATH = os.path.join(os.path.dirname(__file__), "iot_devices.json")

# Default IoT Device Schema
DEFAULT_DEVICES = {
    "living_room_light": {
        "id": "living_room_light",
        "name": "Living Room Light",
        "type": "light",
        "state": "on",
        "brightness": 80,
        "color": "#ffaa00",
        "location": "Living Room",
        "pos": {"x": 180, "y": 120},
        "webhook_url": ""
    },
    "bedroom_light": {
        "id": "bedroom_light",
        "name": "Bedroom Light",
        "type": "light",
        "state": "off",
        "brightness": 60,
        "color": "#4a90e2",
        "location": "Bedroom",
        "pos": {"x": 480, "y": 120},
        "webhook_url": ""
    },
    "smart_plug": {
        "id": "smart_plug",
        "name": "Desk Power Plug",
        "type": "plug",
        "state": "on",
        "power_w": 45,
        "location": "Office",
        "pos": {"x": 180, "y": 320},
        "webhook_url": ""
    },
    "thermostat": {
        "id": "thermostat",
        "name": "Main AC Thermostat",
        "type": "thermostat",
        "state": "on",
        "target_temp": 72,
        "current_temp": 71,
        "mode": "cool",
        "location": "Hallway",
        "pos": {"x": 480, "y": 320},
        "webhook_url": ""
    },
    "smart_tv": {
        "id": "smart_tv",
        "name": "Living Room TV",
        "type": "tv",
        "state": "off",
        "volume": 25,
        "location": "Living Room",
        "pos": {"x": 330, "y": 220},
        "webhook_url": ""
    }
}


def _load_devices():
    """Load IoT device states from JSON file or default."""
    if os.path.exists(IOT_STORE_PATH):
        try:
            with open(IOT_STORE_PATH, "r") as f:
                return json.load(f)
        except Exception:
            pass
    _save_devices(DEFAULT_DEVICES)
    return DEFAULT_DEVICES.copy()


def _save_devices(devices):
    """Persist IoT device states."""
    try:
        with open(IOT_STORE_PATH, "w") as f:
            json.dump(devices, f, indent=2)
    except Exception as e:
        print(f"Error saving IoT state: {e}")


def list_iot_devices(location=None):
    """
    List all registered IoT smart devices.
    
    Args:
        location: Optional filter by location (e.g. "Living Room", "Bedroom")
    """
    devices = _load_devices()
    res = []
    for d_id, dev in devices.items():
        if location and location.lower() not in dev["location"].lower():
            continue
        
        status_str = f"[{dev['state'].upper()}]"
        details = []
        if dev["type"] == "light" and dev["state"] == "on":
            details.append(f"brightness: {dev.get('brightness', 100)}%")
        elif dev["type"] == "thermostat":
            details.append(f"temp: {dev.get('target_temp')}°F ({dev.get('mode', 'cool')})")
        elif dev["type"] == "plug":
            details.append(f"power: {dev.get('power_w', 0)}W")
            
        detail_txt = f" ({', '.join(details)})" if details else ""
        res.append(f"💡 {dev['name']} ({dev['location']}): {status_str}{detail_txt}")
        
    if not res:
        return "📱 No IoT devices found matching query."
    return "\n".join(res)


def control_iot_device(device_query: str, action: str, value: str = None) -> str:
    """
    Control an IoT device state (toggle, turn on, turn off, set brightness, set temp, etc.).
    
    Args:
        device_query: Device name or ID (e.g. "living room light", "thermostat", "plug")
        action: "on", "off", "toggle", "brightness", "temp", "color"
        value: Numerical or string parameter (e.g. "80" for brightness, "72" for temp)
    """
    devices = _load_devices()
    matched_id = None
    query_lower = device_query.lower().strip()
    
    # Matching logic
    for d_id, dev in devices.items():
        if query_lower == d_id or query_lower in dev["name"].lower() or query_lower in dev["type"].lower():
            matched_id = d_id
            break
            
    if not matched_id:
        # Fuzzy fallback
        for d_id, dev in devices.items():
            if any(w in dev["name"].lower() for w in query_lower.split()):
                matched_id = d_id
                break
                
    if not matched_id:
        return f"❌ IoT device matching '{device_query}' not found. Say 'list iot devices' to see available units."
        
    dev = devices[matched_id]
    act = action.lower().strip()
    
    if act in ("on", "enable", "turn on", "start"):
        dev["state"] = "on"
        msg = f"⚡ Turned ON {dev['name']}."
    elif act in ("off", "disable", "turn off", "stop"):
        dev["state"] = "off"
        msg = f"🔌 Turned OFF {dev['name']}."
    elif act in ("toggle", "switch"):
        dev["state"] = "off" if dev["state"] == "on" else "on"
        msg = f"🔄 Toggled {dev['name']} to {dev['state'].upper()}."
    elif act in ("brightness", "dim", "level"):
        try:
            val_int = int(str(value).replace("%", "").strip())
            val_int = max(0, min(100, val_int))
            dev["brightness"] = val_int
            dev["state"] = "on" if val_int > 0 else "off"
            msg = f"💡 Set {dev['name']} brightness to {val_int}%."
        except Exception:
            return f"❌ Invalid brightness value '{value}'. Expected 0-100."
    elif act in ("temp", "temperature"):
        try:
            val_temp = int(str(value).replace("°", "").replace("f", "").strip())
            dev["target_temp"] = val_temp
            dev["state"] = "on"
            msg = f"🌡️ Set {dev['name']} target temperature to {val_temp}°F."
        except Exception:
            return f"❌ Invalid temperature value '{value}'."
    elif act in ("color", "rgb"):
        if value:
            dev["color"] = value
            msg = f"🎨 Set {dev['name']} color to {value}."
        else:
            return "❌ Color value required."
    else:
        return f"❌ Unknown action '{action}' for IoT device."

    # Save state
    devices[matched_id] = dev
    _save_devices(devices)

    # Webhook optional dispatch
    if dev.get("webhook_url"):
        try:
            requests.post(dev["webhook_url"], json=dev, timeout=2)
        except Exception as e:
            print(f"IoT Webhook failed for {dev['name']}: {e}")

    return msg


def add_iot_device(name: str, dev_type: str, location: str = "General", x: int = 250, y: int = 200, webhook_url: str = "") -> str:
    """Register a new IoT device."""
    devices = _load_devices()
    d_id = name.lower().replace(" ", "_")
    devices[d_id] = {
        "id": d_id,
        "name": name,
        "type": dev_type.lower(),
        "state": "off",
        "brightness": 100 if dev_type.lower() == "light" else None,
        "location": location,
        "pos": {"x": int(x), "y": int(y)},
        "webhook_url": webhook_url
    }
    _save_devices(devices)
    return f"✨ Registered new IoT device: '{name}' ({dev_type}) at {location}."


def get_iot_state_dict():
    """Return dictionary of all IoT devices for live UI rendering."""
    return _load_devices()
