from dirbalak.server import githubwebeventlistener
import logging
import threading
import atexit
import signal
import os
import sys
import select
import subprocess


class SpawnGithubWebEventListener(threading.Thread):
    def __init__(self, callback, port=60004, downgradeUID=10000, downgradeGID=10000):
        self._callback = callback
        self._port = port
        self._downgradeUID = downgradeUID
        self._downgradeGID = downgradeGID
        threading.Thread.__init__(self)
        self._readPipe, self._writePipe = os.pipe()
        self._read = os.fdopen(self._readPipe)
        self._childPid = os.fork()
        if self._childPid == 0:
            self._child()
            sys.exit()
        logging.info("forked github webevent listener at pid %(pid)s", dict(pid=self._childPid))
        atexit.register(self._exit)
        self.daemon = True
        threading.Thread.start(self)

    def _child(self):
        try:
            os.setgid(self._downgradeGID)
            os.setuid(self._downgradeUID)
            sys.stdout = os.fdopen(self._writePipe, "w")
            githubwebeventlistener.main(self._port)
        except:
            import traceback
            open("/tmp/stack", "w").write(traceback.format_exc())
            raise

    def run(self):
        read = os.fdopen(self._readPipe, "r")
        try:
            while True:
                ready, unused, unused = select.select([read], [], [], 30)
                if read in ready:
                    repo = read.readline().strip()
                    if repo == '':
                        raise Exception("EOF reading from github web event listener")
                    self._callback(repo.strip())
                else:
                    output = subprocess.check_output(
                        ['netstat', '-n', '-t', '-l'], stderr=subprocess.STDOUT, close_fds=True)
                    if (":%d" % self._port) not in output:
                        logging.error("TCP server on port '%(port)d' was not found" % dict(port=self._port))
                        raise Exception("TCP server on port '%d' was not found" % self._port)
        except:
            logging.exception("Child event listener died, commiting suicide")
            try:
                os.kill(self._childPid, signal.SIGKILL)
            except:
                logging.exception("Unable to kill child")
            os.kill(os.getpid(), signal.SIGTERM)
            raise

    def _exit(self):
        os.kill(self._childPid, signal.SIGKILL)

if __name__ == "__main__":
    import time

    def printCallback(repo):
        print repo
    SpawnGithubWebEventListener(printCallback)
    time.sleep(1000)
