#!/usr/bin/env python3
import os
import sys
import uuid
import subprocess


def main():
    # Expect: first arg is pytest executable or module, followed by its args
    if len(sys.argv) < 2:
        print("SUSPECT_JUNIT_WRAPPER_ERROR: missing pytest command", file=sys.stderr)
        return 2
    pytest_cmd = sys.argv[1]
    pytest_args = sys.argv[2:]

    # Ensure output dir
    out_dir = os.path.abspath(os.path.join(os.getcwd(), ".suspect.mbfl"))
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        pass

    # Unique junit path
    junit_path = os.path.join(out_dir, f"mutant-{uuid.uuid4().hex}.xml")
    # Announce path for the adapter to pick up
    print(f"SUSPECT_JUNIT_XML: {junit_path}")
    sys.stdout.flush()

    # Build and run the pytest command with junit
    cmd = [pytest_cmd] + pytest_args + [f"--junitxml={junit_path}"]
    try:
        proc = subprocess.run(cmd)
        return proc.returncode
    except FileNotFoundError:
        # Try running as module if executable not found
        try:
            cmd = [sys.executable, "-m", "pytest"] + pytest_args + [f"--junitxml={junit_path}"]
            proc = subprocess.run(cmd)
            return proc.returncode
        except Exception as e:
            print(f"SUSPECT_JUNIT_WRAPPER_ERROR: {e}", file=sys.stderr)
            return 2
    except Exception as e:
        print(f"SUSPECT_JUNIT_WRAPPER_ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
