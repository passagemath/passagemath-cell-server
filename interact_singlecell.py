_INTERACTS={}

__single_cell_timeout__=0

from functools import wraps

def decorator_defaults(func):
    """
    This function allows a decorator to have default arguments.

    Normally, a decorator can be called with or without arguments.
    However, the two cases call for different types of return values.
    If a decorator is called with no parentheses, it should be run
    directly on the function.  However, if a decorator is called with
    parentheses (i.e., arguments), then it should return a function
    that is then in turn called with the defined function as an
    argument.

    This decorator allows us to have these default arguments without
    worrying about the return type.

    EXAMPLES::
    
        sage: from sage.misc.decorators import decorator_defaults
        sage: @decorator_defaults
        ... def my_decorator(f,*args,**kwds):
        ...     print kwds
        ...     print args
        ...     print f.__name__
        ...       
        sage: @my_decorator
        ... def my_fun(a,b):
        ...     return a,b
        ...  
        {}
        ()
        my_fun
        sage: @my_decorator(3,4,c=1,d=2)
        ... def my_fun(a,b):
        ...     return a,b
        ...   
        {'c': 1, 'd': 2}
        (3, 4)
        my_fun
    """
    from inspect import isfunction
    @wraps(func)
    def my_wrap(*args,**kwargs):
        if len(kwargs)==0 and len(args)==1 and isfunction(args[0]):
            # call without parentheses
            return func(*args)
        else:
            def _(f):
                return func(f, *args, **kwargs)
            return _
    return my_wrap

@decorator_defaults
def interact(f, controls=[]):
    """
    A decorator that creates an interact.

    Each control can be given as an :class:`.InteractControl` object
    or a value, defined in :func:`.automatic_control`, that will be
    interpreted as the parameters for some control.

    The decorator can be used in several ways::

        @interact([name1, (name2, control2), (name3, control3)])
        def f(**kwargs):
            ...

        @interact
        def f(name1, name2=control2, name3=control3):
            ...


    The two ways can also be combined::

        @interact([name1, (name2, control2)])
        def f(name3, name4=control4, name5=control5):
            ...

    In each example, ``name1``, with no associated control,
    will default to a text box.

    :arg function f: the function to make into an interact
    :arg list controls: a list of tuples of the form ``("name",control)``
    :returns: the original function
    :rtype: function
    """
    global _INTERACTS

    if isinstance(controls,(list,tuple)):
        controls=list(controls)
        for i,name in enumerate(controls):
            if isinstance(name, str):
                controls[i]=(name, None)
            elif not isinstance(name[0], str):
                raise ValueError("interact control must have a string name, but %s isn't a string"%(name[0],))

    import inspect
    (args, varargs, varkw, defaults) = inspect.getargspec(f)
    if defaults is None:
        defaults=[]
    n=len(args)-len(defaults)
    
    controls=zip(args,[None]*n+list(defaults))+controls

    names=[n for n,_ in controls]
    controls=[automatic_control(c) for _,c in controls]

    from sys import _sage_messages as MESSAGE, maxint
    from random import randrange

    # UUID would be better, but we can't use it because of a
    # bug in Python 2.6 on Mac OS X (http://bugs.python.org/issue8621)
    function_id=str(randrange(maxint))

    def adapted_f(**kwargs):
        MESSAGE.push_output_id(function_id)
        # remap parameters
        for k,v in kwargs.items():
            kwargs[k]=controls[names.index(k)].adapter(v)
        returned=f(**kwargs)
        MESSAGE.pop_output_id()
        return returned

    _INTERACTS[function_id]=adapted_f
    MESSAGE.message_queue.message('interact_prepare',
                                  {'interact_id':function_id,
                                   'controls':dict(zip(names,[c.message() for c in controls])),
                                   'layout':names})
    global __single_cell_timeout__
    __single_cell_timeout__=60
    adapted_f(**dict(zip(names,[c.default for c in controls])))
    return f

class InteractControl:
    """
    Base class for all interact controls.
    """
    def __init__(self, *args, **kwargs):
        self.args=args
        self.kwargs=kwargs

    def adapter(self, v):
        """
        Get the value of the interact in a form that can be passed to
        the inner function

        :arg v: a value as passed from the client
        :returns: the interpretation of that value in the context of
            this control (by default, the value is not changed)
        """
        return v

    def message(self):
        """
        Get a control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        raise NotImplementedError

class Checkbox(InteractControl):
    """
    A checkbox control

    :arg bool default: ``True`` if the checkbox is checked by default
    :arg bool raw: ``True`` if the value should be treated as "unquoted"
        (raw), so it can be used in control structures. There are few
        conceivable situations in which raw should be set to ``False``,
        but it is available.
    :arg str label: the label of the control
    """

    def __init__(self, default=True, raw=True, label=""):
        self.default=default
        self.raw=raw
        self.label=label

    def message(self):
        """
        Get a checkbox control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type':'checkbox',
                'default':self.default,
                'raw':self.raw,
                'label':self.label}

class InputBox(InteractControl):
    """
    An input box control

    :arg default: default value of the input box
    :arg int width: character width of the input box
    :arg bool raw: ``True`` if the value should be treated as "unquoted"
        (raw), so it can be used in control structures; ``False`` if the
        value should be treated as a string
    :arg str label: the label of the control
    """

    def __init__(self, default="", width="", raw=False, label=""):
        self.default=default
        self.width=width
        self.raw=raw
        self.label=label

    def message(self):
        """
        Get an input box control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type':'input_box',
                'default':self.default,
                'width':self.width,
                'raw':self.raw,
                'label':self.label}

class InputGrid(InteractControl):
    """
    An input grid control

    :arg int nrows: number of rows in the grid
    :arg int ncols: number of columns in the grid
    :arg int width: character width of each input box
    :arg default: default values of the control. A multi-dimensional
        list specifies the values of individual inputs; a single value
        sets the same value to all inputs
    :arg bool raw: ``True`` if the value should be treated as "unquoted"
        (raw), so it can be used in control structures; ``False`` if the
        value should be treated as a string
    :arg str label: the label of the control
    """

    def __init__(self, nrows=1, ncols=1, width="", default=0, raw=True, label=""):
        self.nrows = nrows
        self.ncols = ncols
        self.width = width
        if not isinstance(default, list):
            self.default = [[default for _ in range(self.ncols)] for _ in range(self.nrows)]
        else:
            self.default = default
        self.raw = raw
        self.label = label

    def message(self):
        """
        Get an input box control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type': 'input_grid',
                'nrows': self.nrows,
                'ncols': self.ncols,
                'default': self.default,
                'width':self.width,
                'raw': self.raw,
                'label': self.label}

class Selector(InteractControl):
    """
    A selector interact control

    :arg int default: initially selected index of the list of values
    :arg list values: list of values (string, number, and/or boolean) from
        which the user can select. A value can also be represented as a tuple
        of the form ``(value, label)``, where the value is the name of the
        variable and the label is the text displayed to the user.
    :arg bool buttons: ``True`` if the control should be rendered as a grid
        of buttons; ``False`` for a dropdown list. If ``False``, ``ncols``,
        ``nrows``, and ``width`` will be ignored.
    :arg int ncols: number of columns of buttons
    :arg int nrows: number of rows of buttons
    :arg str width: CSS width of buttons
    :arg bool raw: ``True`` if the selected value should be treated as
        "unquoted" (raw); ``False`` if the value should be treated as a string.
        Note that this applies to the values of the selector, not the labels.
    :arg str label: the label of the control
    """

    def __init__(self, default=0, values=[0], buttons=False, nrows=None, ncols=None, width="", raw=False, label=""):
        self.default=default
        self.values=values[:]
        self.buttons=buttons
        self.nrows=nrows
        self.ncols=ncols
        self.width=width
        self.raw=raw
        self.label=label
        
        # Assign selector labels and values.
        self.value_labels=[str(v[1]) if isinstance(v,tuple) and
                           len(v)==2 else str(v) for v in values]
        
        # Ensure that default index is always in the correct range.
        if default < 0 or default >= len(values):
            self.default = 0

        # If using buttons rather than dropdown,
        # check/set rows and columns for layout.
        if self.buttons:
            if self.nrows is None:
                if self.ncols is not None:
                    self.nrows = len(self.values) / self.ncols
                    if self.ncols * self.nrows < len(self.values):
                        self.nrows += 1
                else:
                    self.nrows = 1
            elif self.nrows <= 0:
                    self.nrows = 1

            if self.ncols is None:
                self.ncols = len(self.values) / self.nrows
                if self.ncols * self.nrows < len(self.values):
                    self.ncols += 1

    def message(self):
        """
        Get a selector control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type': 'selector',
                'values': range(len(self.values)),
                'value_labels': self.value_labels,
                'default': self.default,
                'buttons': self.buttons,
                'nrows': self.nrows,
                'ncols': self.ncols,
                'width': self.width,
                'raw': self.raw,
                'label':self.label}
                
    def adapter(self, v):
        return self.values[int(v)]

class Slider(InteractControl):
    """
    A slider interact control

    :arg int default: initial value of the slider; if ``None``, the
        slider defaults to its minimum
    :arg tuple interval: range of the slider, in the form ``(min, max)``
    :arg int step: step size for the slider
    :arg bool raw: ``True`` if the value should be treated as "unquoted"
        (raw), so it can be used in control structures; ``False`` if the
        value should be treated as a string
    :arg str label: the label of the control
    """

    def __init__(self, default=None, interval=(0,100), step=1, raw=True, label=""):
        self.default = int(default if default is not None else interval[0])
        self.interval = [int(i) for i in interval]
        self.step=step
        self.raw=raw
        self.label=label

    def message(self):
        """
        Get a slider control configuration message for an
        ``interact_prepare`` message

        :returns: configuration message
        :rtype: dict
        """
        return {'control_type':'slider',
                'default':self.default,
                'range':self.interval,
                'step':self.step,
                'raw':self.raw,
                'label':self.label}

def automatic_control(control):
    """
    Guesses the desired interact control from the syntax of the parameter.
    
    :arg control: Parameter value.
    
    :returns: An InteractControl object.
    :rtype: InteractControl
    
    
    """
    from numbers import Number
    label = ""
    default_value = 0
    
    # Checks for interact controls that are verbosely defined
    if isinstance(control, InteractControl):
        return control
    
    # Checks for labels and control values
    for _ in range(2):
        if isinstance(control, tuple) and len(control) == 2 and isinstance(control[0], str):
            label, control = control
        if isinstance(control, tuple) and len(control) == 2 and isinstance(control[1], (tuple, list)):
            default_value, control = control

    if isinstance(control, str):
        C = input_box(default = control, label = label)
    elif isinstance(control, bool):
        C = checkbox(default = control, label = label, raw = True)
    elif isinstance(control, Number):
        C = input_box(default = control, label = label, raw = True)
    elif isinstance(control, list):
        C = selector(buttons = len(control) <= 5, default = default_value, label = label, values = control, raw = False)
    elif isinstance (control, tuple):
        if len(control) == 2:
            C = slider(default = control[0], interval = (control[0], control[1]), label = label)
        elif len(control) == 3:
            C = slider(default = default_value, interval = (control[0], control[1]), step = control[2], label = label)
        else:
            C = slider(list(control), default = default_value, label = label)
    else:
        C = input_box(default = control, label=label)
    
    return C


# Aliases for backwards compatibility
slider=Slider
selector=Selector
input_box=InputBox
input_grid=InputGrid
checkbox=Checkbox
