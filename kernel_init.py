import codecs
import sys
import time

import ipykernel.jsonutil

import misc


def threejs(p, **kwds):
    from warnings import warn
    warn("""
    threejs(graphic_object, **keywords)
is now equivalent to
    graphic_object.show(viewer='threejs', **kwds)
and will be completely removed in future versions""",
         DeprecationWarning, 2)
    kwds["viewer"] = "threejs"
    p.show(**kwds)
    

def initialize(kernel):
    
    def new_files(root="./"):
        import os
        import sys
        new_files = []
        for top, dirs, files in os.walk(root):
            for dir in dirs:
                if dir.endswith(".jmol"):
                    dirs.remove(dir)
            for name in files:
                path = os.path.join(top, name)
                if path.startswith("./"):
                    path = path[2:]
                mtime = os.stat(path).st_mtime
                if (path == "sagemathcell.py"
                    or path in sys._sage_.sent_files
                    and sys._sage_.sent_files[path] >= mtime):
                    continue
                if (path.startswith("Rplot")
                    and path[-4:] in [".bmp", "jpeg", ".png", ".svg"]):
                    misc.display_file(path, "text/image-filename")
                    continue
                if path == "octave.png":
                    misc.display_file(path, "text/image-filename")
                    continue
                new_files.append(path)
                sys._sage_.sent_files[path] = mtime
        ip = user_ns["get_ipython"]()
        ip.payload_manager.write_payload({"new_files": new_files})
        return ""
    
    class TempClass(object):
        pass

    _sage_ = TempClass()
    _sage_.display_message = misc.display_message
    _sage_.stream_message = misc.stream_message
    _sage_.reset_kernel_timeout = misc.reset_kernel_timeout
    _sage_.javascript = misc.javascript
    _sage_.new_files = new_files
    _sage_.sent_files = {}
    _sage_.threejs = threejs
    

    def handler_wrapper(key, handler):
        from functools import wraps
        
        @wraps(handler)
        def f(stream, ident, parent, *args, **kwargs):
            md = kernel.init_metadata(parent)
            kernel._publish_status("busy", "shell", parent)
            # Set the parent message of the display hook and out streams.
            kernel.shell.set_parent(parent)
            try:
                reply = {
                    "result": handler(stream, ident, parent, *args, **kwargs),
                    "status": "ok",
                    # TODO: this should be refactored probably to use existing
                    # IPython code
                    "user_expressions": kernel.shell.user_expressions(
                        parent["content"].get("user_expressions", {}))
                    }
            except:
                kernel.log.debug("handler exception for %s", key)
                etype, evalue, tb = sys.exc_info()
                reply = {
                    "ename": etype.__name__,  # needed by finish_metadata
                    "status": "error",
                    "user_expressions": {}
                    }
                import traceback
                tb_list = traceback.format_exception(etype, evalue, tb)
                kernel.shell._showtraceback(etype, evalue, tb_list)

            # Payloads should be retrieved regardless of outcome, so we can both
            # recover partial output (that could have been generated early in a
            # block, before an error) and clear the payload system always.
            reply['payload'] = kernel.shell.payload_manager.read_payload()
            # Be agressive about clearing the payload because we don't want
            # it to sit in memory until the next execute_request comes in.
            kernel.shell.payload_manager.clear_payload()
            # Flush output before sending the reply.
            sys.stdout.flush()
            sys.stderr.flush()
            # FIXME: on rare occasions, the flush doesn't seem to make it to the
            # clients... This seems to mitigate the problem, but we definitely
            # need to better understand what's going on.
            if kernel._execute_sleep:
                time.sleep(kernel._execute_sleep)

            reply = ipykernel.jsonutil.json_clean(reply)
            md = kernel.finish_metadata(parent, md, reply)
            reply_msg = kernel.session.send(
                stream, key + '_reply', reply, parent, metadata=md, ident=ident)
            kernel.log.debug("handler reply for %s %s", key, reply_msg)
            kernel._publish_status("idle", "shell", parent)
        return f
        
    def register_handler(key, handler):
        if key not in [
                'apply_request',
                'complete_request',
                'connect_request',
                'execute_request',
                'history_request',
                'object_info_request',
                'shutdown_request',
                ]:
            kernel.shell_handlers[key] = handler_wrapper(key, handler)
            
    _sage_.register_handler = register_handler
    
    def send_message(stream, msg_type, content, parent, **kwargs):
        kernel.session.send(
            stream, msg_type, content=content, parent=parent, **kwargs)
            
    _sage_.send_message = send_message

    # Enable Sage types to be sent via session messages
    from zmq.utils import jsonapi
    kernel.session.pack = lambda x: jsonapi.dumps(x, default=misc.sage_json)

    sys._sage_ = _sage_
    user_ns = kernel.shell.user_module.__dict__
    #ka.kernel.shell.user_ns = ka.kernel.shell.Completer.namespace = user_ns
    sys._sage_.namespace = user_ns
    # TODO: maybe we don't want to cut down the flush interval?
    sys.stdout.flush_interval = sys.stderr.flush_interval = 0.0
    def clear(changed=None):
        sys._sage_.display_message({
            "application/sage-clear": {"changed": changed},
            "text/plain": "Clear display"
        })
    sys._sage_.clear = clear
    kernel.shell.extension_manager.load_extension('sage.repl.ipython_extension')
    import sage
    user_ns["sage"] = sage
    sage_code = """
# Ensure unique random state after forking
set_random_seed()
import numpy.random
numpy.random.seed()
from sage.repl.rich_output import get_display_manager
from backend_cell import BackendCell
get_display_manager().switch_backend(BackendCell(), shell=get_ipython())
"""
    exec(sage_code, user_ns)
        
    from IPython.core import oinspect
    from sage.misc.sagedoc import my_getsource
    oinspect.getsource = my_getsource
    
    import interact_sagecell
    import interact_compatibility
    import dynamic
    import exercise
    # overwrite Sage's interact command with our own
    user_ns.update(interact_sagecell.imports)
    user_ns.update(interact_compatibility.imports)
    user_ns.update(dynamic.imports)
    user_ns.update(exercise.imports)
    user_ns['threejs'] = sys._sage_.threejs
    sys._sage_.update_interact = interact_sagecell.update_interact
    
    # In order to show the correct code line when a (deprecation) warning
    # is triggered, we change the main module name and save user code to
    # a file with the same name.
    sys.argv = ['sagemathcell.py']
    old_execute = kernel.do_execute
    
    def new_execute(code, *args, **kwds):
        with codecs.open('sagemathcell.py', 'w', encoding='utf-8') as f:
            f.write(code)
        return old_execute(code, *args, **kwds)
        
    kernel.do_execute = new_execute

