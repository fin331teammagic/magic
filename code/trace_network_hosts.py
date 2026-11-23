"""Run a Python script and report every hostname it looks up.

Used to check that the EDSL scorer sends requests only to Anthropic's API
and never to Expected Parrot's servers (course lead's instruction,
2026-11-19). Hostname lookups made by Python's socket module are logged;
the list prints to stderr when the script ends.

    python code/trace_network_hosts.py code/score_transcripts_edsl.py <scorer args>
"""
import runpy
import socket
import sys

seen = []
_getaddrinfo = socket.getaddrinfo


def _logged_getaddrinfo(host, *args, **kwargs):
    if host not in seen:
        seen.append(host)
    return _getaddrinfo(host, *args, **kwargs)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    socket.getaddrinfo = _logged_getaddrinfo
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    try:
        runpy.run_path(script, run_name="__main__")
    except SystemExit:
        pass
    finally:
        hosts = [h.decode() if isinstance(h, bytes) else str(h) for h in seen]
        print("HOSTS CONTACTED: " + (", ".join(hosts) or "none"), file=sys.stderr)


if __name__ == "__main__":
    main()
