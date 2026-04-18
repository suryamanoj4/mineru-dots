#!/usr/bin/env python
"""Legacy mineru CLI entrypoint forwarding to vparse."""

from vparse.cli.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
