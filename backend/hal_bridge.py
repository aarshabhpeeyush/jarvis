"""HAL Bridge — Hardware Abstraction Layer connecting JARVIS to MQTT/WebSocket devices."""
import os
import json
import asyncio
import logging
from typing import Any

logger = logging.getLogger("hal_bridge")

MQTT_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USERNAME", "")
MQTT_PASS = os.getenv("MQTT_PASSWORD", "")

# ─── Tool Registry ────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, dict] = {
    "move_actuator": {
        "description": "Move a servo or linear actuator to a target position",
        "schema": {"target": "str", "angle": "float", "speed": "float"},
        "mqtt_topic": "hal/actuator/command",
    },
    "toggle_relay": {
        "description": "Toggle a relay or GPIO pin on/off",
        "schema": {"target": "str", "state": "bool"},
        "mqtt_topic": "hal/relay/command",
    },
    "read_telemetry": {
        "description": "Read sensor telemetry from a connected device",
        "schema": {"sensor_id": "str"},
        "mqtt_topic": "hal/telemetry/request",
    },
    "set_led": {
        "description": "Set LED strip color and brightness",
        "schema": {"target": "str", "color": "str", "brightness": "float"},
        "mqtt_topic": "hal/led/command",
    },
    "emergency_stop": {
        "description": "Immediately halt all actuators",
        "schema": {},
        "mqtt_topic": "hal/system/estop",
    },
}


class HALBridge:
    def __init__(self) -> None:
        self._mqtt_client = None
        self._connected = False
        self._telemetry_cache: dict[str, Any] = {}

    async def connect(self) -> bool:
        """Attempt MQTT connection. Returns True if successful."""
        try:
            import paho.mqtt.client as mqtt  # type: ignore

            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    self._connected = True
                    client.subscribe("hal/telemetry/response/#")
                    logger.info("HAL Bridge connected to MQTT broker")

            def on_message(client, userdata, msg):
                try:
                    payload = json.loads(msg.payload.decode())
                    sensor_id = payload.get("sensor_id", "unknown")
                    self._telemetry_cache[sensor_id] = payload
                except Exception:
                    pass

            self._mqtt_client = mqtt.Client()
            if MQTT_USER:
                self._mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
            self._mqtt_client.on_connect = on_connect
            self._mqtt_client.on_message = on_message
            self._mqtt_client.connect_async(MQTT_HOST, MQTT_PORT, 60)
            self._mqtt_client.loop_start()
            await asyncio.sleep(1)
            return self._connected
        except Exception as e:
            logger.warning(f"HAL Bridge MQTT unavailable (offline mode): {e}")
            return False

    async def dispatch(self, action: str, target: str = "", params: dict | None = None) -> dict:
        """Dispatch a command to the appropriate device via MQTT."""
        params = params or {}

        if action not in TOOL_REGISTRY:
            return {"success": False, "error": f"Unknown action: {action}"}

        tool = TOOL_REGISTRY[action]
        payload = {"action": action, "target": target, "params": params}
        topic = tool["mqtt_topic"]

        if self._connected and self._mqtt_client:
            self._mqtt_client.publish(topic, json.dumps(payload), qos=1)
            return {"success": True, "dispatched": payload, "topic": topic}
        else:
            # Offline mode — log the intended command
            logger.info(f"[OFFLINE] Would publish to {topic}: {payload}")
            return {"success": True, "offline": True, "dispatched": payload}

    def get_telemetry(self, sensor_id: str) -> dict:
        return self._telemetry_cache.get(sensor_id, {})

    def list_tools(self) -> dict:
        return {k: {"description": v["description"], "schema": v["schema"]}
                for k, v in TOOL_REGISTRY.items()}


hal = HALBridge()
