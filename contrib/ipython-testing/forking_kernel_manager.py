import uuid
import zmq
import os
import signal
import tempfile
import json
import random
import sys
import interact
from IPython.zmq.ipkernel import IPKernelApp
from IPython.config.loader import Config
from multiprocessing import Process, Pipe
import logging
import sage
import sage.all
from sage.misc.interpreter import SageInputSplitter
from IPython.core.inputsplitter import IPythonInputSplitter


class SageIPythonInputSplitter(SageInputSplitter, IPythonInputSplitter):
    """
    This class merely exists so that the IPKernelApp.kernel.shell class does not complain.  It requires
    a subclass of IPythonInputSplitter, but SageInputSplitter is a subclass of InputSplitter instead.
    """
    pass

class ForkingKernelManager(object):
    def __init__(self):
        self.kernels = {}

    def fork_kernel(self, sage_dict, config, pipe):
        logging.basicConfig(filename='LOG',format=str(uuid.uuid4()).split('-')[0]+': %(asctime)s %(message)s',level=logging.DEBUG)
        ka = IPKernelApp.instance(config=config)
        ka.initialize([])
        # this should really be handled in the config, not set separately.
        ka.kernel.shell.input_splitter = SageIPythonInputSplitter()
        user_ns = ka.kernel.shell.user_ns
        user_ns.update(sage_dict)
        user_ns.update(interact.classes)
        sage_code = """
sage.misc.session.init()

# Ensure unique random state after forking
set_random_seed()
"""
        exec sage_code in user_ns
        if "sys" in user_ns:
            user_ns["sys"]._interacts = interact.interacts
        else:
            sys._interacts = interact.interacts
            user_ns["sys"] = sys
        user_ns["interact"] = interact.interact_func(ka.session, ka.iopub_socket)
        pipe.send({"ip": ka.ip, "key": ka.session.key, "shell_port": ka.shell_port,
                "stdin_port": ka.stdin_port, "hb_port": ka.hb_port, "iopub_port": ka.iopub_port})
        pipe.close()
        ka.start()

    def start_kernel(self, sage_dict=None, kernel_id=None, config=None):
        if sage_dict is None:
            sage_dict = {}
        if kernel_id is None:
            kernel_id = str(uuid.uuid4())
        if config is None:
            config = Config()
        p, q = Pipe()
        proc = Process(target=self.fork_kernel, args=(sage_dict, config, q))
        proc.start()
        connection = p.recv()
        p.close()
        self.kernels[kernel_id] = (proc, connection)
        return {"kernel_id": kernel_id, "connection": connection}

    def send_signal(self, kernel_id, signal):
        """Send a signal to a running kernel."""
        if kernel_id in self.kernels:
            try:
                os.kill(self.kernels[kernel_id][0].pid, signal)
                self.kernels[kernel_id][0].join()
            except OSError, e:
                # On Unix, we may get an ESRCH error if the process has already
                # terminated. Ignore it.
                from errno import ESRCH
                if e.errno != ESRCH:
                    raise

    def kill_kernel(self, kernel_id):
        """Kill a running kernel."""
        try:
            self.send_signal(kernel_id, signal.SIGTERM)
            del self.kernels[kernel_id]
            return True
        except:
            return False

    def interrupt_kernel(self, kernel_id):
        """Interrupt a running kernel."""
        try:
            self.send_signal(kernel_id, signal.SIGINT)
            return True
        except:
            return False

    def restart_kernel(self, sage_dict, kernel_id):
        ports = self.kernels[kernel_id][1]
        self.kill_kernel(kernel_id)
        return self.start_kernel(sage_dict, kernel_id, Config({"IPKernelApp": ports}))

if __name__ == "__main__":
    a = ForkingKernelManager()
    x=a.start_kernel()
    y=a.start_kernel()
    import time
    time.sleep(5)
    a.kill_kernel(x["kernel_id"])
    a.kill_kernel(y["kernel_id"])
