"""
Flask web server for frontend
"""

from flask import Flask, request, render_template, redirect, url_for, jsonify, send_file, json
from time import time, sleep
from functools import wraps
from util import log
import uuid
import zmq
from ip_receiver import IPReceiver
from werkzeug import secure_filename

app = Flask(__name__)
app.allowed_extensions = set(['txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'])

# is it safe to have global variables here?
db=None
fs=None
xreq=None
messages=[]
sysargs=None

def print_exception(f):
    """
    This decorator prints any exceptions that occur to the webbrowser.  This printing works even for uwsgi and nginx.
    """
    import traceback
    @wraps(f)
    def wrapper(*args, **kwds):
        try:
            return f(*args, **kwds)
        except:
            return "<pre>%s</pre>"%traceback.format_exc()
    return wrapper

def get_db(f):
    """
    This decorator gets the database and passes it into the function as the first argument.
    """
    import misc
    @wraps(f)
    def wrapper(*args, **kwds):
        global db
        global fs
        global sysargs
        if sysargs is None:
            # Fake a sysargs object for a default
            # this is for when we don't call this file directly
            class A: pass
            sysargs=A()
            sysargs.db='mongo'

        if db is None or fs is None:
            db,fs=misc.select_db(sysargs)
        args = (db,fs) + args
        return f(*args, **kwds)
    return wrapper

@app.route("/")
def root():
    return render_template('ipython_root.html')

def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.',1)[1] in app.allowed_extensions

@app.route("/eval", methods=['GET','POST'])
@get_db
def evaluate(db,fs):
    if request.method == "POST":
         if request.values.get("message") is not None:
            log('Received Request: %s'%(request.values['message'],))
            message=json.loads(request.values['message'])
            session_id=message['header']['session']
            db.new_input_message(message)
            # TODO: computation_id -> session_id
            return jsonify(computation_id=session_id)
         else:
            session_id = request.form.get("session_id")
            files = []
            parent_header = "parent_header"
            for file in request.files.getlist("file"):
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    fs.create_file(file, filename=filename, cell_id=session_id)
                    files.append(filename)
            message = {"parent_header": {},
                   "header": {"msg_id": request.form.get("msg_id"),
                              "username": "",
                              "session": session_id
                              },
                   "msg_type": "execute_request",
                   "content": {"code": request.form.get("commands"),
                               "silent": False,
                               "files": files,
                               "user_variables": [],
                               "user_expressions": {}
                               }
                   }
            log("Received Request: %s"%(message))
            db.new_input_message(message)
            return ""
    return ""

@app.route("/answers")
@print_exception
@get_db
def answers(db,fs):
    results = db.get_evaluated_cells()
    return render_template('answers.html', results=results)

@app.route("/output_poll")
@print_exception
@get_db
def output_poll(db,fs):
    """
    Return the output of a computation id (passed in the request)

    If a computation id has output, then return to browser. If no
    output is entered, then return nothing.
    """
    computation_id=request.values['computation_id']
    sequence=int(request.values.get('sequence',0))
    results = db.get_messages(id=computation_id,sequence=sequence)
    log("Retrieved messages: %s"%(results,))
    if results is not None and len(results)>0:
        return jsonify(content=results)
    return jsonify([])

@app.route("/output_long_poll")
@print_exception
@get_db
def output_long_poll(db,fs):
    """
    Implements long-polling to return answers.

    If a computation id has output, then return to browser. Otherwise,
    poll the database periodically to check to see if the computation id
    is done.  Return after a certain number of seconds whether or not
    it is done.

    This currently blocks (calls sleep), so is not very useful.
    """
    default_timeout=2 #seconds
    poll_interval=.1 #seconds
    end_time=float(request.values.get('timeout', default_timeout))+time()
    computation_id=request.values['computation_id']
    while time()<end_time:
        results = db.get_evaluated_cells(id=computation_id)
        if results is not None and len(results)>0:
            return jsonify({'output':results['output']})
        sleep(poll_interval)
    return jsonify([])

from flask import Response, abort
import mimetypes
@app.route("/files/<cell_id>/<filename>")
@get_db
def cellFile(db,fs,cell_id,filename):
    """Returns a file generated by a cell from the filesystem."""
    # We can't use send_file because that will try to access the file
    # on the local filesystem (see the code to send_file).
    # So we have to do the work of send_file ourselves.
    #return send_file(fs.get_file(cell_id,filename), attachment_filename=filename)

    mimetype=mimetypes.guess_type(filename)[0]
    if mimetype is None:
        mimetype = 'application/octet-stream'
    f=fs.get_file(cell_id=cell_id, filename=filename)
    if f is not None:
        return Response(f, content_type=mimetype)
    else:
        abort(404)

@app.route("/complete")
@get_db
def tabComplete(db,fs):
    """
    Perform tab completion using IPython
    """
    global xreq
    if xreq==None:
        xreq=IPReceiver(zmq.XREQ,db.get_ipython_port("xreq"))
    header={"msg_id":str(uuid.uuid4())}
    code=request.values["code"]
    xreq.socket.send_json({"header":header, "msg_type":"complete_request", "content": { \
                "text":"", "line":code, "block":code, "cursor_pos":request.values["pos"]}})
    return jsonify({"completions":xreq.getMessages(header,True)[0]["content"]["matches"]})


if __name__ == "__main__":
    # We don't use argparse because Sage has an old version of python.  This will probably be upgraded
    # sometime in the summer of 2011, and then we can move this to use argparse.
    from optparse import OptionParser
    parser = OptionParser(description="The web server component of the notebook")
    parser.add_option("--db", choices=["mongo","sqlite","sqlalchemy"], default="mongo", help="Database to use")
    parser.add_option("-q", action="store_true", dest="quiet", help="Turn off most logging")
    (sysargs, args) = parser.parse_args()

    if sysargs.quiet:
        util.LOGGING=False


    app.run(port=8080, debug=True)
