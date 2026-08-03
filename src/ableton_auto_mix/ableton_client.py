"""AbletonOSC client wrapper for talking to Ableton Live."""

from __future__ import annotations

import logging
from typing import Any

from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

logger = logging.getLogger(__name__)

DEFAULT_SEND_PORT = 11000
DEFAULT_RECV_PORT = 11001
DEFAULT_HOST = "127.0.0.1"

# OscMessage -> response mapping: the OSC server pushes state into this
# shared dict keyed by a request token we append to each command.
STATE = {}


class AbletonClient:
    """Minimal client for the AbletonOSC control surface.

    Requires Ableton Live running with the AbletonOSC Remote Script
    enabled (Options -> Preferences -> Link/Tempo/MIDI -> Control Surface).
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        send_port: int = DEFAULT_SEND_PORT,
        recv_port: int = DEFAULT_RECV_PORT,
    ) -> None:
        self.host = host
        self.send_port = send_port
        self.recv_port = recv_port
        self._client = udp_client.SimpleUDPClient(host, send_port)
        self._server: ThreadingOSCServer | None = None

    # ---------------------------------------------------------------- setup
    def connect(self) -> None:
        dispatcher = Dispatcher()
        dispatcher.set_default_handler(self._on_message)
        self._server = ThreadingOSCServer((self.host, self.recv_port), dispatcher)
        self._server.daemon_threads = True
        self._server.serve_forever()

    def disconnect(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server = None

    def _on_message(self, address: str, *args: Any) -> None:
        STATE[address] = args

    # ------------------------------------------------------------- commands
    def send(self, address: str, *args: Any) -> None:
        self._client.send_message(address, args)

    def request(self, address: str, *args: Any, timeout: float = 2.0) -> list[Any]:
        """Send a command and wait for the matching /reply/... message."""
        self.send(address, *args)
        target = address.replace("/live/", "/reply/live/")
        deadline = None
        if timeout:
            deadline = __import__("time").time() + timeout
        while True:
            if target in STATE:
                return STATE.pop(target)
            if deadline and __import__("time").time() > deadline:
                raise TimeoutError(f"No reply from Ableton for {address}")
            __import__("time").sleep(0.05)

    # ------------------------------------------------------------ shortcuts
    def ping(self) -> bool:
        try:
            self.send("/live/start/transport")
            return True
        except Exception:
            return False

    def get_tempo(self) -> float:
        return float(self.request("/live/song/get/tempo")[0])

    def set_tempo(self, bpm: float) -> None:
        self.send("/live/song/set/tempo", bpm)

    def get_track_names(self) -> list[str]:
        n = int(self.request("/live/song/get/num_tracks")[0])
        names = []
        for i in range(n):
            names.append(str(self.request(f"/live/track/get/name", i)[0]))
        return names

    def get_track_info(self, index: int) -> dict[str, Any]:
        return {
            "index": index,
            "name": str(self.request(f"/live/track/get/name", index)[0]),
            "volume": float(self.request(f"/live/track/get/volume", index)[0]),
            "pan": float(self.request(f"/live/track/get/pan", index)[0]),
            "mute": bool(self.request(f"/live/track/get/mute", index)[0]),
            "solo": bool(self.request(f"/live/track/get/solo", index)[0]),
        }

    def set_track_volume(self, index: int, db: float) -> None:
        self.send(f"/live/track/set/volume", index, db)

    def set_track_pan(self, index: int, pan: float) -> None:
        self.send(f"/live/track/set/pan", index, pan)

    def set_track_mute(self, index: int, muted: bool) -> None:
        self.send(f"/live/track/set/mute", index, int(muted))

    def set_track_solo(self, index: int, solo: bool) -> None:
        self.send(f"/live/track/set/solo", index, int(solo))


_client: AbletonClient | None = None


def get_client() -> AbletonClient:
    global _client
    if _client is None:
        _client = AbletonClient()
        _client.connect()
    return _client


def close_client() -> None:
    global _client
    if _client is not None:
        _client.disconnect()
        _client = None
