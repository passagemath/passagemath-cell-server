import uuid, random
import zmq
from zmq.eventloop.zmqstream import ZMQStream
from IPython.zmq.session import Session
from zmq import ssh
import paramiko
import os

class TrustedMultiKernelManager(object):
    """ A class for managing multiple kernels on the trusted side. """
    def __init__(self, computers = None):
        self._kernels = {} #kernel_id: {"comp_id": comp_id, "connection": {"key": hmac_key, "hb_port": hb, "iopub_port": iopub, "shell_port": shell, "stdin_port": stdin}}
        self._comps = {} #comp_id: {"host:"", "port": ssh_port, "kernels": {}, "max": #, "beat_interval": Float, "first_beat": Float, "resource_limits": {resource: limit}}
        self._clients = {} #comp_id: {"socket": zmq req socket object, "ssh": paramiko client}
        self._sessions = {} # kernel_id: Session
        self.context = zmq.Context()

        if computers is not None:
            for comp in computers:
                self.add_computer(comp)

    def get_kernel_ids(self, comp = None):
        """ A function for obtaining kernel ids of a particular computer.

        :arg str comp: the id of the computer whose kernels you desire
        :returns: kernel ids of a computer if its id is given or all kernel ids if no id is given
        :rtype: list
        """
        ids = []
        if comp is not None and comp in self._comps:
            ids = self._comps[comp]["kernels"].keys()
        elif comp is not None and comp not in self._comps:
            pass
        else:
            ids = self._kernels.keys()
        return ids

    def get_hb_info(self, kernel_id):
        """ Returns basic heartbeat information for a given kernel. 

        :arg str kernel_id: the id of the kernel whose heartbeat information you desire
        :returns: a tuple containing the kernel's beat interval and time until first beat
        :rtype: tuple
        """
        
        comp_id = self._kernels[kernel_id]["comp_id"]
        comp = self._comps[comp_id]
        return (comp["beat_interval"], comp["first_beat"])

    def add_computer(self, config):
        """ Adds a tracked computer. 

        :arg dict config: configuration dictionary of the computer to be added
        :returns: computer id assigned to added computer
        :rtype: string
        """
        defaults = {"max": 10, "beat_interval": 3.0, "first_beat": 5.0, "kernels": {}}
        comp_id = str(uuid.uuid4())
        cfg = dict(defaults.items() + config.items())

        req = self.context.socket(zmq.REQ)

        client = self._setup_ssh_connection(cfg["host"], cfg["username"])
        logfile = cfg.get("log_file")
        if logfile is None:
            logfile = os.devnull
        code = "%s '%s/receiver.py' '%s'"%(cfg['python'], os.getcwd(), logfile)
        print "executing %s"%code
        ssh_stdin, ssh_stdout, ssh_stderr = client.exec_command(code)
        stdout_channel = ssh_stdout.channel

        # Wait for untrusted side to respond with the bound port using paramiko channels
        # Another option would be to have a short-lived ZMQ socket bound on the trusted
        # side and have the untrusted side connect to that and send the port
        failure = True
        from time import sleep
        for i in xrange(10):
            if stdout_channel.recv_ready():
                port = stdout_channel.recv(1024)
                failure = False
                break;
            sleep(2)
            
        retval = None
        if failure:
            print "Computer %s did not respond, connecting failed!"%comp_id

        else:
            addr = "tcp://%s:%s"%(cfg["host"], port)
            req.connect(addr)
            
            req.send("handshake")
            response = req.recv()

            if(response == "handshake"):
                self._clients[comp_id] = {"socket": req, "ssh": client}
                self._comps[comp_id] = cfg
                print "ZMQ Connection with computer %s at port %s established." %(comp_id, port)
            else:
                print "ZMQ Connection with computer %s at port %s failed!" %(comp_id, port)

            retval = comp_id

        return retval

    def _setup_ssh_connection(self, host, username):
        """ Returns a paramiko SSH client connected to the given host. 

        :arg str host: host to SSH to
        :arg str username: username to SSH to
        :returns: a paramiko SSH client connected to the host and username given
        """
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(host, username=username)
        return ssh_client


    def purge_kernels(self, comp_id):
        """ Kills all kernels on a given computer. 

            :arg str comp_id: the id of the computer whose kernels you want to purge
        """
        req = self._clients[comp_id]["socket"]
        req.send_pyobj({"type": "purge_kernels"})
        print req.recv_pyobj()
        for i in self._comps[comp_id]["kernels"].keys():
            del self._kernels[i]
        self._comps[comp_id]["kernels"] = {}

    def shutdown(self):
        """ Ends all kernel processes on all computers. """
        for comp_id in self._comps.keys():
            self.remove_computer(comp_id)

    def remove_computer(self, comp_id):
        """ Removes a tracked computer. 

        :arg str comp_id: the id of the computer that you want to remove
        """
        ssh_client = self._clients[comp_id]["ssh"]
        req = self._clients[comp_id]["socket"]
        req.send_pyobj({"type": "remove_computer"})
        print req.recv_pyobj()
        for i in self._comps[comp_id]["kernels"].keys():
            del self._kernels[i]
        ssh_client.close()
        del self._comps[comp_id]

    def restart_kernel(self, kernel_id):
        """ Restarts a given kernel.

        :arg str kernel_id: the id of the kernel you want restarted
        """
        comp_id = self._kernels[kernel_id]["comp_id"]
        req = self._clients[comp_id]["socket"]
        req.send_pyobj({"type":"restart_kernel",
                        "content":{"kernel_id":kernel_id}})
        response = req.recv_pyobj()
        print response

    def interrupt_kernel(self, kernel_id):
        """ Interrupts a given kernel. 

        :arg str kernel_id: the id of the kernel you want interrupted
        """
        comp_id = self._kernels[kernel_id]["comp_id"]
        req = self._clients[comp_id]["socket"]
        req.send_pyobj({"type":"interrupt_kernel",
                        "content": {"kernel_id": kernel_id}})

        reply = req.recv_pyobj()

        if reply["type"] == "success":
            print "Kernel %s interrupted."%kernel_id
        else:
            print "Kernel %s not interrupted!"%kernel_id

    def new_session(self):
        """ Starts a new kernel on an open computer. 

        :returns: kernel id assigned to the newly created kernel
        :rtype: string
        """
        comp_id = self._find_open_computer()
        req = self._clients[comp_id]["socket"]
        resource_limits = self._comps[comp_id].get("resource_limits")
        req.send_pyobj({"type":"start_kernel", "content": {"resource_limits": resource_limits}})
        reply = req.recv_pyobj()
        if reply["type"] == "success":
            reply_content = reply["content"]
            kernel_id = reply_content["kernel_id"]
            kernel_connection = reply_content["connection"]
            self._kernels[kernel_id] = {"comp_id": comp_id, "connection": kernel_connection}
            self._comps[comp_id]["kernels"][kernel_id] = None
            print "CONNECTION FILE ::: ", kernel_connection
            self._sessions[kernel_id] = Session(key=kernel_connection["key"], debug=True)
            return kernel_id
        else:
            return False

    def end_session(self, kernel_id):
        """ Kills an existing kernel on a given computer.

        :arg str kernel_id: the id of the kernel you want to kill
        """
        comp_id = self._kernels[kernel_id]["comp_id"]

        req = self._clients[comp_id]["socket"]
        req.send_pyobj({"type":"kill_kernel",
                        "content": {"kernel_id": kernel_id}})
        print "Killing Kernel ::: %s at %s"%(kernel_id, (comp_id))
        response = req.recv_pyobj()
        
        if (response["type"] == "error"):
            print "Error ending kernel!"
        else:
            del self._kernels[kernel_id]
            del self._comps[comp_id]["kernels"][kernel_id]
        
    def _find_open_computer(self):
        """ Randomly searches through computers in _comps to find one that can start a new kernel.

        :returns: the comp_id of a computer with room to start a new kernel
        :rtype: string
        """ 
        
        ids = self._comps.keys()
        random.shuffle(ids)
        found_id = None
        done = False
        index = 0        

        while (index < len(ids) and not done):
            found_id = ids[index]
            if len(self._comps[found_id]["kernels"].keys()) < self._comps[found_id]["max"]:
                done = True
            else:
                index += 1
        if done:
            return found_id
        else:
            raise IOError("Could not find open computer. There are %d computers available."%len(ids))

    def _create_connected_stream(self, cfg, port, socket_type):
        sock = self.context.socket(socket_type)
        addr = "tcp://%s:%i" % (cfg["host"], port)
        print "Connecting to: %s" % addr
        sock.connect(addr)
        return ZMQStream(sock)
    
    def create_iopub_stream(self, kernel_id):
        """ Create iopub 0MQ stream between given kernel and the server.

        
        """
        comp_id = self._kernels[kernel_id]["comp_id"]
        cfg = self._comps[comp_id]
        connection = self._kernels[kernel_id]["connection"]
        iopub_stream = self._create_connected_stream(cfg, connection["iopub_port"], zmq.SUB)
        iopub_stream.socket.setsockopt(zmq.SUBSCRIBE, b"")
        return iopub_stream

    def create_shell_stream(self, kernel_id):
        """ Create shell 0MQ stream between given kernel and the server.gi

        
        """
        comp_id = self._kernels[kernel_id]["comp_id"]
        cfg = self._comps[comp_id]
        connection = self._kernels[kernel_id]["connection"]
        shell_stream = self._create_connected_stream(cfg, connection["shell_port"], zmq.DEALER)
        return shell_stream

    def create_hb_stream(self, kernel_id):
        """ Create heartbeat 0MQ stream between given kernel and the server.

        
        """
        comp_id = self._kernels[kernel_id]["comp_id"]
        cfg = self._comps[comp_id]
        connection = self._kernels[kernel_id]["connection"]
        hb_stream = self._create_connected_stream(cfg, connection["hb_port"], zmq.REQ)
        return hb_stream



if __name__ == "__main__":
    try:
        import misc
        config = misc.Config()

        initial_comps = config.get_config("computers")

        t = TrustedMultiKernelManager(computers = initial_comps)
        for i in xrange(5):
            t.new_session()

        vals = t._comps.values()
        for i in xrange(len(vals)):
            print "\nComputer #%d has kernels ::: "%i, vals[i]["kernels"].keys()

        print "\nList of all kernel ids ::: " + str(t.get_kernel_ids())
        
        y = t.get_kernel_ids()
        x = t._comps.keys()

        t.remove_computer(x[0])
            
        vals = t._comps.values()
        for i in xrange(len(vals)):
            print "\nComputer #%d has kernels ::: "%i, vals[i]["kernels"].keys()

        print "\nList of all kernel ids ::: " + str(t.get_kernel_ids())
    except:
        # print "errorrrr"
        raise
    finally:
        #for the moment to ensure all receivers are killed...
        for i in t._comps.keys():
           t.remove_computer(i)
