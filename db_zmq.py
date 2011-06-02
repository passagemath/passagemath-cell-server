"""
The MongoDB database has the following structure:

  - code table
     - device -- the device id for the process.  This is -1 if no device has been assigned yet.
     - input -- the code to execute.
  - messages: a series of messages in ipython format
  - ipython: a table to keep track of ipython ports for tab completion.  Usable when there is a single long-running ipython dedicated session for each computation.
  - sessions: a table listing, for each session, which device is assigned to the session

"""

import db
import zmq
from uuid import uuid4

def db_method(method_name, kwarg_keys):
    def f(self, **kwargs):
        msg={'header': {'msg_id': str(uuid4())},
                          'msg_type': method_name,
                          'content': dict([(kw,kwargs[kw]) for kw in kwarg_keys])}
        print "Sent: ",msg
        self.c.send_json(msg)
        # wait for output back
        output=self.c.recv_pyobj()
        print "Received: ",output
        return output
    return f

class DB(db.DB):
    def __init__(self, *args, **kwds):
        #TODO: use authentication keys
        self.context=kwds['context']
        self.req=self.context.socket(zmq.REQ)
        print "ZMQ connecting to ",kwds['socket']
        self.req.connect(kwds['socket'])
        db.DB.__init__(self, self.req)
        print "Started ZMQ DB"
        
    new_input_message = db_method('new_input_message', ['msg'])
    get_input_messages = db_method('get_input_messages', ['device', 'limit'])
    close_session = db_method('close_session', ['device', 'session'])
    get_messages = db_method('get_messages', ['id','sequence'])
    add_messages = db_method('add_messages', ['id', 'messages'])

    def set_ipython_ports(self, kernel):
        self.c.ipython.remove()
        self.c.ipython.insert({"pid":kernel[0].pid, "xreq":kernel[1], "sub":kernel[2], "rep":kernel[3]})
    
    def get_ipython_port(self, channel):
        return self.c.ipython.find().next()[channel]

