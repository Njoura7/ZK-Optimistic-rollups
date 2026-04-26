
import sys

# IMPORTANT: Each test file (test_zk_sequencer.py and test_optimistic_sequencer.py)
# manages its own sys.path to load from l2-zk/ and l2-optimistic/ respectively.
# The conftest should NOT add the root directory, as this can cause pytest to find
# both sequencer.py files and cause import conflicts.
#
# Instead, we only clean up cached modules to prevent cross-test pollution:

# Remove any sequencer module cached from a previous test
sys.modules.pop("sequencer", None)
sys.modules.pop("opt_sequencer", None)
sys.modules.pop("zk_sequencer", None)


