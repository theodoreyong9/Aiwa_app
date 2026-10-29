"""The brain keeps its files in the home folder: the tests get one of their own, before anything is imported."""
import os
import tempfile

os.environ["HOME"] = tempfile.mkdtemp(prefix="aiwa-home-")
os.environ["AIWA_TEST"] = "1"
