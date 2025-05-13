import socket
import msgpack

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(
    msgpack.packb({"sat_name": "ISS (ZARYA)", "action": "subscribe"}),
    ("localhost", 9999),
)
while True:
    data, _ = sock.recvfrom(1024)
    state = msgpack.unpackb(data)
    print(f"Received: {state}")
