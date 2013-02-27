$(function() {
var canvas = $('#mycanvas');
var divnum = 0;
var celltemplate = {
    hide: ['sagemode', 'files']
};

canvas.click(function(e) {
    if (e.target !== this) {
        return;
    }
    var id = 'cell-'+divnum;
    var newcell = $('<div class="cell" id="'+id+'"></div>')
        .offset({top: e.offsetY, left: e.offsetX})
        .appendTo(canvas);
    // for some reason (a race condition?) the draggable and resizable methods don't work immediately
    setTimeout(function() {
        newcell.draggable({cancel: '.sagecell_commands,.CodeMirror,textarea'});
        //newcell.draggable({snap: canvas, grid: [50,50], cancel: '.sagecell_commands,.CodeMirror'});

        // Here are some not-so-successful attempts at resizability.
            //.resizable({ snap: canvas, grid: [50,50]});
        /*      resize: function() {
                    var codemirror=$(this).find(".CodeMirror-scroll");
                    codemirror.height($(this).height());
                    //codemirror.width($(this).find('.CodeMirror').width());
                    $(this).find('.CodeMirror')[0].CodeMirror.refresh();
                    }
        */

    },400);

    if (e.shiftKey) {
        newcell.addClass('markdowncell');
        (function() { 
            var data;
            newcell.text("Double-click to edit");
            newcell.editable(function(value, settings) {
                data = value;
                renderedHtml = converter.makeHtml(value);
                $(this).data('cellcanvas_renderedHtml', renderedHtml) 
                setTimeout(function() {MathJax.Hub.Queue(["Typeset",MathJax.Hub,id]);}, 100);
                return(renderedHtml);
            }, {type: 'markdown', rows: 7, columns: 30,
                onblur: 'ignore',
                indicator: 'Saving...',
                submit: 'Save',
                event: "dblclick",
                tooltip: "Double-click to edit",
                placeholder: "Double-click to edit",
                data: function(value, settings){return data;},
               });
            newcell.dblclick();
        })();
    } else {
        newcell.addClass('interactivesagecell');
        sagecell.makeSagecell({
            inputLocation: '#'+id,
            template: celltemplate,
        });
    }
    divnum += 1;
});

    var scripttag = function ( config ) {
        // We can't use the jquery .append to load javascript because then the script tag disappears.
        // See http://stackoverflow.com/questions/610995/jquery-cant-append-script-element.
        var script = document.createElement( 'script' );
        if (config.type!==undefined) {
            script.type = config.type;
        } else {
            script.type="text/javascript";
        }
        if (config.src!==undefined) { script.src = config.src; }
        if (config.text!==undefined) {script.text = config.text;}
        return script;
    };

    window.encodepage = function() {
        var savehead;
        var savebody;

        savehead = $(document.createElement('div'));
        savehead[0].appendChild(scripttag({src: "http://aleph.sagemath.org/static/jquery.min.js"}));
        savehead[0].appendChild(scripttag({src: "http://aleph.sagemath.org/embedded_sagecell.js"}));
        savehead[0].appendChild(scripttag({text: "var celltemplate = "+JSON.stringify(celltemplate)+";"}));
        $('head style[title=cellcanvas]').clone().appendTo(savehead);

        savebody = $(document.createElement('div'));
        var cellsInit = "";
        var codecell;
        canvas.find('.interactivesagecell').each(function() {
            // We clone so we get all the css, the id, etc.
            codecell = $(this).clone().empty().appendTo(savebody);
            codecell[0].appendChild(scripttag({type: 'text/x-sage', text: $(this).find('.sagecell_commands').val()}));
            cellsInit += "sagecell.makeSagecell({inputLocation: '#"+this.id+"', template:celltemplate});\n";
        });
        canvas.find('.markdowncell').each(function() {
            var newcell = $(this).clone().empty().appendTo(savebody);
            var renderedHtml;
            var text = $(this).find("form textarea").val();

            if (text === undefined) {
                // Must be saved cell.  Get the pre-rendered text.
                renderedHtml = $(this).data('cellcanvas_renderedHtml');
            } else {
                renderedHtml = converter.makeHtml(text);
            }
            newcell.html(renderedHtml);
        });
        savebody[0].appendChild(scripttag({text: "$(function() {sagecell.init(function() {"+cellsInit+"})})"}));
        html = "<html><head>"+savehead.html()+"</head><body>"+savebody.html()+"</body></html>"
        return html
    }

    $('#freezepage').click(function (event){
        var w = window.open();
        w.document.write(encodepage());
        w.document.close();
        event.preventDefault();
    });
    
});

// From http://stackoverflow.com/questions/9687358/does-a-pagedown-plugin-exist-for-jeditable
var converter = Markdown.getSanitizingConverter();

$.editable.addInputType('markdown', {
    element: function(settings, original) {
        var editorId = original.id.substring(original.id.lastIndexOf("-"));
        var textarea = $('<textarea />');
        if (settings.rows) {
            textarea.attr('rows', settings.rows);
        } else {
            textarea.height(settings.height);
        }
        if (settings.cols) {
            textarea.attr('cols', settings.cols);
        } else {
            textarea.width(settings.width);
        }

        textarea.attr('id', 'wmd-input' + editorId);

         var panel = $('<div class="wmd-panel'+editorId+'" />');
        panel.append('<div id="wmd-button-bar' + editorId + '" />');
        panel.append(textarea);
        panel.append('<div id="wmd-preview' + editorId + '" />');

        $(this).append(panel);
        return (textarea);
    },
    plugin: function(settings, original) {
        var editorId = original.id.substring(original.id.lastIndexOf("-"));
        var editor = new Markdown.Editor(converter, editorId);
        editor.hooks.chain("onPreviewRefresh", function () {
            MathJax.Hub.Queue(["Typeset",MathJax.Hub,original.id]);
        });
        editor.run();
    }
});


// TODO: Use TinyMCE??? http://www.appelsiini.net/jeditable, http://stackoverflow.com/questions/5580713/make-tinymce-work-properly-with-jeditable

/* To download, we can use html5: http://codebits.glennjones.net/downloadattr/downloadattr.htm

or we can use flash: http://pixelgraphics.us/downloadify/test.html

http://stackoverflow.com/questions/3749231/download-file-using-javascript-jquery

http://webreflection.blogspot.com/2011/08/html5-how-to-create-downloads-on-fly.html

Right now, I'll use base64 data: urls.  In the future, supporting the file Blob api would be better.  But lots of browsers don't quite support that just yet.

*/
