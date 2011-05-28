// Options to document the functions:
// YUIDocs
// Sphinx: http://docs.cubicweb.org/annexes/docstrings-conventions.html#
// jsdoc->sphinx: http://code.google.com/p/jsdoc-toolkit-rst-template/
// recommendation to use jsdoc http://groups.google.com/group/sphinx-dev/browse_thread/thread/defa96cdc0dfc584
// sphinx javascript domain: http://sphinx.pocoo.org/domains.html#the-javascript-domain


// Set up the editor and evaluate button
$(function() {
    editor=CodeMirror.fromTextArea(document.getElementById("commands"),{
	mode:"python",
	indentUnit:4,
	tabMode:"shift",
	lineNumbers:true,
	matchBrackets:true});
    editor.setValue("")
    editor.focus();
    
    $('#command_form').submit(function() {
	var session = new Session('#output');
	$('#computation_id').append('<div>'+session.session_id+'</div>');
	msg=session.sendMsg(editor.getValue());
	return false;
    });
});


// Create UUID4-compliant ID
// Taken from stackoverflow answer here: http://stackoverflow.com/questions/105034/how-to-create-a-guid-uuid-in-javascript
function uuid4() {
    uuid = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx';
    return uuid.replace(/[xy]/g, function(c) {
	var r = Math.random()*16|0, v = c == 'x' ? r : (r&0x3|0x8);
	return v.toString(16);
    });
}

// makeClass - By John Resig (MIT Licensed)
// see http://ejohn.org/blog/simple-class-instantiation/
function makeClass(){
  return function(args){
    if ( this instanceof arguments.callee ) {
      if ( typeof this.init == "function" )
        this.init.apply( this, args.callee ? args : arguments );
    } else
      return new arguments.callee( arguments );
  };
}


/**************************************************************
* 
* Colorize Tracebacks
* 
**************************************************************/
colorCodes={"30":"black",
	    "31":"red",
	    "32":"green",
	    "33":"goldenrod",
	    "34":"blue",
	    "35":"purple",
	    "36":"darkcyan",
	    "37":"gray"};

function colorize(text) {
    text=text.split("\u001b[");
    result="";
    for(i in text) {
	if(text[i]=="")
	    continue;
	color=text[i].substr(0,text[i].indexOf("m")).split(";");
	if(color.length==2) {
	    result+="<span style=\"color:"+colorCodes[color[1]];
	    if(color[0]==1)
		result+="; font-weight:bold";
	    result+="\">"+text[i].substr(text[i].indexOf("m")+1)+"</span>";
	} else
	    result+=text[i].substr(text[i].indexOf("m")+1);
    }
    return result;
}

/**************************************************************
* 
* Session Class
* 
**************************************************************/

var Session = makeClass();
Session.prototype.init = function (output) {
    this.session_id = uuid4();
    this.sequence = 0;
    this.poll_interval = 400;
    $(output).append('<div id="session-'+this.session_id+'" class="session_output"><div class="session_title">Session '+this.session_id+'</div></div>');
    this.session_output=$('#session-'+this.session_id);
}

Session.prototype.sendMsg = function(code) {
    var msg_id=uuid4()
    var msg = {"parent_header": {},
		   "header": {"msg_id": msg_id,
			  "username": "",
			  "session": this.session_id},
		   "msg_type": "execute_request",
		   "content": {"code": code,
			   "silent": false,
			   "user_variables": [],
			   "user_expressions": {}}
	      };
    /* We need to make a proxy object; see
       http://api.jquery.com/bind/#comment-74776862 or
       http://bitstructures.com/2007/11/javascript-method-callbacks
       for why. If we don't do the proxy, then "this" in the
       send_computation_success function will *not* refer to the
       session object. */
    $.post($URL.evaluate, {message: JSON.stringify(msg)}, dataType="json")
	.success($.proxy( this, 'send_computation_success' ), "json")
	.error(function(jqXHR, textStatus, errorThrown) {
	    console.log(jqXHR); 
	    console.log(textStatus); 
	    console.log(errorThrown);
	});
    this.session_output.append('<div id="'+msg_id+'"></div>');
    return msg_id
}

Session.prototype.output = function(msg_id) {
    return $('#'+msg_id);
}

Session.prototype.send_computation_success = function(data, textStatus, jqXHR) {
    if (data.computation_id!==this.session_id) {
	alert("Session id returned and session id sent don't match up");
    }
    this.get_output();
}

Session.prototype.get_output = function() {
    // TODO: instead of each individual request querying the server, we should have a global
    // TODO: object querying the server. When a message is sent, we should just add the computation
    // TODO: to the global object to query about.
    $.getJSON($URL.output_poll, {computation_id: this.session_id, sequence: this.sequence},
	      $.proxy(this, 'get_output_success'));
}

Session.prototype.get_output_success = function(data, textStatus, jqXHR) {
    var id=this.session_id;
    var done = false;

    if(data!==undefined && data.content!==undefined) {
        var content = data.content;
	for (var i = 0; i < content.length; i++) {
            var msg=content[i];
	    var parent_id=msg.parent_header.msg_id;
	    var output=this.output(parent_id)
            if(msg.sequence!==this.sequence) {
                //TODO: Make a big warning sign
                console.log('sequence is out of order; I think it should be '+sequence+', but server claims it is '+msg.sequence);
            }
            this.sequence+=1;
            // Handle each stream type.  This should probably be separated out into different functions.
	    switch(msg.msg_type) {
		//TODO: if two stdout/stderr messages happen consecutively, consolidate them in the same pre
	    case 'stream': 
                output.append("<pre class='"+msg.content.name+"'>"+msg.content.data+"</pre>");
		break;

	    case 'pyout':
                output.append("<pre class='pyout'>"+msg.content.data['text/plain']+"</pre>");
		break;

	    case 'display_data':
                if(msg.content.data['image/svg+xml']!==undefined) {
                    output.append('<object id="svgImage" type="image/svg+xml">'+msg.content.data['image/svg+xml']+'</object>');
                } else if(msg.content.data['text/html']!==undefined) {
		    output.append('<div>'+msg.content.data['text/html']+'</div>');
		}
		break;

	    case 'pyerr':
		output.append("<pre>"+colorize(msg.content.traceback.join("\n")
						     .replace(/&/g,"&amp;")
						     .replace(/</g,"&lt;")+"</pre>"));
		break;
	    case 'execute_reply':
		if(msg.content.status==="error") {
		    // copied from the pyerr case
		    output.append("<pre>"+colorize(msg.content.traceback.join("\n")
							 .replace(/&/g,"&amp;")
							 .replace(/</g,"&lt;")+"</pre>"));
		}
		this.poll_interval=2000;
		break;

	    case 'extension':
		var user_msg=msg.content;
		switch(user_msg.msg_type) {
		case "files":
		    var html="<div>\n";
		    for(var j=0; j<user_msg.files.length; j++)
			//TODO: escape filenames and id
			html+="<a href=\"/files/"+id+"/"+user_msg.files[j]+"\">"
			    +user_msg.files[j]+"</a><br>\n";
		    output.append(html);
		    break;
		case "session_end":
		    this.session_output.append("<div class='done'>Session "+id+ " done</div>");
		    done=true;
		    break;
		case "interact_start":
		    interact_id = uuid4()
		    var div_id = "interact-" + interact_id;
		    console.log(interact_id);
		    output.append("<div id='"+div_id+"'></div>");
		    var interact = new InteractCell("#" + div_id, {
			'interact_id': interact_id,
			'layout': user_msg.content.layout,
			'controls': user_msg.content.controls,
			'function_code': user_msg.content.function_code,
			'session': this});
		    break;
		case "interact_end":
		    break;
		}
		break;
	    }

	    // Append the message to the div of messages
	    // use .text() so that strings are automatically escaped
	    $('#messages').append(document.createElement('div'))
		.children().last().text(JSON.stringify(msg));
        }
    }
    if(!done) {
        // poll again after a bit
        setTimeout($.proxy(this, 'get_output'), this.poll_interval);
    }
}

/**************************************************************
* 
* InteractCell Class
* 
**************************************************************/


var InteractCell = makeClass();
InteractCell.prototype.init = function (selector, data) {
    this.element = $(selector);
    this.element.data("interact", this);
    this.interact_id = data.interact_id
    this.function_code = data.function_code;
    this.controls = data.controls;
    this.layout = data.layout;
    this.session = data.session;
    console.log('interact session:');
    console.log(this.session);

    this.renderCanvas();

    // bind some variables for the function below.
    interact=this
    $(".urn_uuid_" + this.interact_id).live("change", function(){
        var changes = interact.getChanges();
        var code = interact.function_code + "(";
        for (var i in changes) {
	    code = code + i + "='" +  changes[i].replace(/'/g, "\\'") + "',";
        }
        code = code + ")";
	// TODO: make the output actually be written inside of the interact div
	interact.session.sendMsg(code);
    });
    //TODO: unbind the change handler when the session is done
    
}

InteractCell.prototype.getChanges = function() {
    id = "#urn_uuid_" + this.interact_id;
    var params = {};
    for (var i in this.controls){
	switch(this.controls[i].control_type) {
	case "html":
	   // for text box: this.params[i] = $(id + "-" + i).val();
	    break;
	case "input_box":
	    params[i] = $(id + "-" + i).val();
	    break;
	}
    }
    return params;
}

InteractCell.prototype.renderCanvas = function() {
    // TODO: use this.layout to lay out the controls
    id = "urn_uuid_" + this.interact_id;
    for (var i in this.controls) {
	switch(this.controls[i].control_type) {
	case "html":
	    var html_code = this.controls[i].html;
	    html_code = html_code.replace("$"+i+"$", this.controls[i].default);
	    html_code = html_code.replace("$id$", id);
	    this.element.append(html_code);
	    break;
	case "input_box":
	    this.element.append("<input type='text' value =" + "'" + this.controls[i].default +  "' class = " + id + " id = " + id + "-" + i + "></input>");
	    break;
	}
    }
}

