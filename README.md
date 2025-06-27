This is passagemath-cell-server - a Sage computation web service.

It is a fork of SageMathCell, which has a mailing list at https://groups.google.com/forum/#!forum/sage-cell

# Security Warning

If you are going to run a world accessible SageMathCell server, you must understand security implications and should be able to implement reasonable precautions.

The worker account (which is your own one by default) will be able to execute arbitrary code, which may be malicious. Make **sure** that you are securing the account properly. Working with a professional IT person is a very good idea here. Since the untrusted accounts can be on any computer, one way to isolate these accounts is to host them in a virtual machine that can be reset if the machine is compromised.


# Simple Installation

We assume that you have access to the Internet and can install any needed dependencies. If you need to know more precisely what tools are needed, please consult the scripts for building virtual machine images in [contrib/vm](contrib/vm).
In particular, system packages installed in the base container are listed [here](https://github.com/sagemath/sagecell/blob/master/contrib/vm/container_manager.py#L58).


1.  Install requirejs:

    ```bash
    sudo apt-get install npm
    # On Debian based systems we need to make an alias
    sudo ln -s /usr/bin/nodejs /usr/bin/node
    ```

2.  Clone and create a virtual environment for passagemath-cell-server:

    ```bash
    git clone https://github.com/passagemath/passagemath-cell-server.git
    cd passagemath-cell-server
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -v -e .
    ```

3.  Build SageMathCell:

    ```
    sage -sh -c make
    ```

To build just the Javascript components, from the `passagemath-cell-server` directory run

```bash
make static/embedded_sagecell.js
```


# Configuration

1.  Go into the `passagemath-cell-server` directory (you are there in the end of the above instructions).
2.  `cp templates/tos_default.html static/tos.html`
3.  Copy `config_default.py` to `config.py`. (Or fill `config.py` only with entries that you wish to change from default values.)
4.  Edit `config.py` according to your needs. Of particular interest are `host` and `username` entries of the `provider_info` dictionary: you should be able to SSH to `username@host` *without typing in a password*. For example, by default, it assumes you can do `ssh localhost` without typing in a password. Unless you are running a private and **firewalled** server for youself, you’ll want to change this to a more restrictive account; otherwise **anyone will be able to execute any code under your username**. You can set up a passwordless account using SSH: type “ssh passwordless login” into Google to find lots of guides for doing this, like http://www.debian-administration.org/articles/152. You may also wish to adjust `db_config["uri"]` (make the database files readable *only* by the trusted account).
5.  You may want to adjust `log.py` to suit your needs and/or adjust system configuration. By default logging is done via syslog which handles multiple processes better than plain files.
6.  Start the server via

    ```bash
    sage-cell-server [-p <PORT_NUMBER>]
    ```

    where the default `<PORT_NUMBER>` is `8888` and go to `http://localhost:<PORT_NUMBER>` to use the Sage Cell server.

    When you want to shut down the server, press `Ctrl-C` in the same terminal.


# Javascript Development

Javascript source files are compiled using [Webpack](https://webpack.js.org/). Sagecell depends on source files copied
from the Jupyter notebook project. To start development navigate to the `sagecell` source directory and run

```bash
npm install
npm run build:deps
```

After this, all dependencies will be located in the `build/vendor` directory. You can now run

```bash
npm run build
```

to build `build/embedded_sagecell.js`

or

```bash
npm run watch
```

to build `build/embedded_sagecell.js` and watch files for changes. If a file is changed, `embedded_sagecell.js` will be automatically
rebuilt.

# License

See the [LICENSE.txt](LICENSE.txt) file for terms and conditions for usage and a
DISCLAIMER OF ALL WARRANTIES.

# Browser Compatibility

SageMathCell is designed to be compatible with recent versions of:

* Chrome
* Firefox
* Internet Explorer
* Opera
* Safari

If you notice issues with any of these browsers, please let us know.
