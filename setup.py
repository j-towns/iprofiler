#!/usr/bin/env python

# Monkey-patch distutils
import setuptools

import os
from warnings import warn

from distutils.core import setup, Extension, Command
from distutils.command.build_py import build_py
import distutils


def install_js(command, strict=False):
    """
    Decorator for installing iprofiler.js
    """
    class DecoratedCommand(command):
        def run(self):
            import notebook.nbextensions
            notebook.nbextensions.install_nbextension('./js/iprofiler',
                                                      user=True)
            command.run(self)
            update_package_data(self.distribution)
    return DecoratedCommand

def update_package_data(distribution):
    """update package_data to catch changes during setup"""
    build_py = distribution.get_command_obj('build_py')
    # distribution.package_data = find_package_data()
    # re-init build_py options which load package_data
    build_py.finalize_options()

cmdclass={'build_py': install_js(build_py)}
try:
    from Cython.Distutils import build_ext
    cmdclass['build_ext'] = build_ext
    line_profiler_source = 'line_profiler/_iline_profiler.pyx'
except ImportError:
    line_profiler_source = 'line_profiler/_iline_profiler.c'
    if not os.path.exists(line_profiler_source):
        raise distutils.errors.DistutilsError("""\
You need Cython to build the line_profiler.""")
    else:
        raise ("Could not import Cython. "
             "Using the available pre-generated C file.")

setup(name='IProfiler',
      version='0.1',
      description='Interactive code profiler for IPython + Jupyter',
      author='James Townsend',
      author_email='jamiehntownsend@gmail.com',
      url='https://github.com/j-towns/iprofiler',
      install_requires=['cython', 'bokeh'],
      ext_modules=[
          Extension('_iline_profiler',
                    sources=[line_profiler_source, 'line_profiler/timers.c', 'line_profiler/unset_trace.c'],
                    depends=['python25.pxd'],
          ),
      ],
      py_modules=['iprofiler'],
      cmdclass=cmdclass
     )
