# iprofiler
Interactive code profiling widget for IPython + Jupyter Notebook.

Tested with Jupyter notebook server 4.1.0 and 4.2.0, Python 2.7 and 3.5, IPython 4.1 and IPython 4.2. May be compatible with earlier/later versions.

**This software is a work in progress and is not yet stable/release ready.**

## Dependencies
+ Cython
+ Ipython/Jupyter
+ Bokeh

## Installation
For a development installation (requires npm):

    $ git clone https://github.com/j-towns/iprofiler.git
    $ cd iprofiler/js
    $ npm install
    $ cd ..
    $ pip install -e .
    $ jupyter nbextension install --py --symlink --user iprofiler
    $ jupyter nbextension enable --py --user iprofiler
    $ jupyter nbextension enable --py --sys-prefix widgetsnbextension

## Usage
Use
```
%load_ext iprofiler
```
to import the iprofiler to your Jupyter notebook, then use the iprofile line magic
```
%iprofile [statement]
```
to profile a statement, or the cell magic `%%iprofile` to profile a cell.
