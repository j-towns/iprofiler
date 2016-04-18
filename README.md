# iprofiler
Interactive code profiling widget for IPython + Jupyter Notebook.

Only tested with Jupyter notebook server 4.1.0 and 4.2.0, Python 2.7.10, IPython 4.1.2, may be compatible with earlier/later versions.

Appears to be broken for Python 3 because of the html module. Will find a work-around ASAP.

## Dependencies
+ Ipython/Jupyter
+ html module (see [here](https://pypi.python.org/pypi/html/1.16))

## Installation
`pip install --user git+https://github.com/j-towns/iprofiler`

## Usage
Once installed using the above command, use
`%load_ext iprofiler`
to import the iprofiler to your notebook, then use the iprofile line magic
`%iprofile [statement]`
to profile a statement.
