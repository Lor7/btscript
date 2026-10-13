import os, sys, tempfile, pytest

# Ensure root directory and runtimes/python are on pythonpath for tests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "btscript", "runtimes", "python")))

from btscript.parser import Parser

@pytest.fixture
def parse_src():
    def _parse(code: str):
        with tempfile.NamedTemporaryFile("w", suffix=".tree", delete=False) as f:
            f.write(code)
            path = f.name
        try:
            p = Parser(path)
            return p.parse_file()
        finally:
            if os.path.exists(path):
                os.remove(path)
    return _parse
