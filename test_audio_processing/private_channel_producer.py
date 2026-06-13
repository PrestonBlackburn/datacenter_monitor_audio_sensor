import meshtastic.serial_interface
from pubsub import pub
from meshtastic.mesh_interface import MeshInterface
from datetime import datetime
from typing import Any, Optional
import time

TEST_CHANNEL_INDEX = 1
_TZ_NAME = time.tzname[time.localtime().tm_isdst > 0]
PRODUCER_DEVICE = '/dev/ttyACM0' #pico pi
CONSUMER_DEVICE = '/dev/ttyUSB1' #pico pi

def on_ack(packet: dict[str, Any], interface: Any) -> None:
    portnum = packet.get("decoded", {}).get("portnum")
    from_id = packet.get("fromId", "unknown")
    channel = packet.get("channel", 0)
    print(f"packet received: portnum={portnum} from={from_id} channel={channel}")

def send_message(device_name: str, message: str, channel_index: int = TEST_CHANNEL_INDEX) -> int:
    pub.subscribe(on_ack, "meshtastic.receive")
    iface = None
    try:
        iface = meshtastic.serial_interface.SerialInterface(device_name)
        iface.sendText(message, channelIndex=channel_index, wantAck=True)
        print(f"Queued on channel {channel_index}: {message}")
        time.sleep(10)  # stay open long enough to transmit and receive ACK
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        print(f"Error: {exc}")
        return 1
    finally:
        if iface:
            iface.close()
    return 0
    

if __name__ == "__main__":
    message = "test local 2"
    send_message(PRODUCER_DEVICE, message)