"""Shared helpers used by both L2 sequencer implementations.

Kept as a plain package (not installed) so the Docker image and the mocked
pytest environment can both import it by adding the repository root to
``sys.path``. Nothing in here imports ``web3`` directly: tests replace the
``web3`` module with a mock, so hashing uses the independent ``eth_utils``
and ``eth_abi`` libraries instead.
"""
