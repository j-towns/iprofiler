# iprofiler
Interactive code profiling widget for IPython + Jupyter Notebook.

Tested with Jupyter notebook server 4.1.0 and 4.2.0, Python 2.7 and 3.5, IPython 4.1.2. May be compatible with earlier/later versions.

## Dependencies
+ Cython
+ Ipython/Jupyter
+ Bokeh

## Installation
`pip install --user git+https://github.com/j-towns/iprofiler`

## Usage
Once installed using the above command, use
`%load_ext iprofiler`
to import the iprofiler to your notebook, then use the iprofile line magic
`%iprofile [statement]`
to profile a statement, or the cell magic `%%iprofile` to profile a cell.
