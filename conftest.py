# conftest.py
# Prevents web3's pytest_ethereum plugin from loading
# which conflicts with eth_typing in this environment
collect_ignore_glob = []

def pytest_configure(config):
    """Block web3's incompatible pytest plugin."""
    pass