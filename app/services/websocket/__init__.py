"""
WebSocket-enabled service variants live in this package.

HTTP-based implementations remain under `app.services.voice` and
`app.services.voice2`. These modules mirror their public interfaces but
switch the transport to WebSocket so callers can opt in without touching
the originals.
"""

