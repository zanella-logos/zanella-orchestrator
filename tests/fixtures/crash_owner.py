from pathlib import Path
import sys
import time

from rpa_control_center.windows import ProcessTree

with ProcessTree([sys.executable, "-c", "import time; time.sleep(60)"], str(Path.cwd())) as tree:
    Path(sys.argv[1]).write_text(str(tree.pid))
    time.sleep(60)
