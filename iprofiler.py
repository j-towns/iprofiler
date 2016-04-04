import html
from IPython.utils import openpy
from IPython.utils import ulinecache
from IPython.core.magic import (Magics, magics_class, line_magic,
                                cell_magic, line_cell_magic)
from ipywidgets import DOMWidget
from traitlets import Unicode, Int
from ipywidgets.widgets.widget import CallbackDispatcher, register

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

import zipfile
import sys


# Python 2/3 compatibility utils
# ===========================================================
PY3 = sys.version_info[0] == 3

# exec (from https://bitbucket.org/gutworth/six/):
if PY3:
    import builtins
    exec_ = getattr(builtins, "exec")
    del builtins
else:
    def exec_(_code_, _globs_=None, _locs_=None):
        """Execute code in a namespace."""
        if _globs_ is None:
            frame = sys._getframe(1)
            _globs_ = frame.f_globals
            if _locs_ is None:
                _locs_ = frame.f_locals
            del frame
        elif _locs_ is None:
            _locs_ = _globs_
        exec("""exec _code_ in _globs_, _locs_""")

# ============================================================

class IProfile(DOMWidget):
    def __init__(self, cprofile, lprofile=None, context=None, *args, **kwargs):
        self.generate_cprofile_tree(cprofile, context)
        self.lprofile = lprofile
        self.generate_content()
        self.value = str(self.html_value)
        self.on_msg(self.handle_on_msg)

        super(IProfile, self).__init__(value=self.value)

    def generate_cprofile_tree(self, cprofile, context=None):
        self.cprofile_tree = {}
        for entry in cprofile:
            function = entry[0]
            calls_raw = entry[5]
            calls = {}
            if calls_raw is not None:
                for call in calls_raw:
                    calls[call[0]] = {'callcount': call[1],
                                      'reccallcount': call[2],
                                      'totaltime': call[3],
                                      'inlinetime': call[4]}

            self.cprofile_tree[function] = {'callcount': entry[1],
                                            'reccallcount': entry[2],
                                            'totaltime': entry[3],
                                            'inlinetime': entry[4],
                                            'calls': calls}

        # Find root nodes
        callcounts = dict([(function, 0) for function in self.cprofile_tree])
        for function in self.cprofile_tree:
            for call in self.cprofile_tree[function]['calls']:
                callcounts[call] += 1

        self.roots = []
        for (i, n) in callcounts.iteritems():
            if n == 0:
                self.roots.append(i)

        self.delete_top_level(context)

    def delete_top_level(self, context=None):
        """
        Delete the top level calls which are not part of the user's code.
        """
        if context is "LINE_MAGIC":
            junk_calls = self.roots
            tree = self.cprofile_tree
            junk_calls.append(tree[junk_calls[0]]['calls'].keys()[0])
            junk_calls.append(tree[junk_calls[-1]]['calls'].keys()[0])
            for junk_call in junk_calls:
                del self.cprofile_tree[junk_call]

    _view_name = Unicode('IProfileView').tag(sync=True)

    # This trait is the actual html displayed in the widget
    value = Unicode().tag(sync=True)

    # Number of elements in table (used by front end to generate click events)
    n_table_elements = Int(0).tag(sync=True)

    # Dictionary mapping html id's to function names
    id_dict = {}

    def generate_content(self, fun=None):
        """Generate profile page for function fun. If fun=None then generate
        a summary page."""
        self.html_value = html.HTML()
        self.generate_heading(fun)
        self.generate_table(fun)
        if self.lprofile is not None and fun is not None:
            self.generate_lprofile(fun)

    def generate_heading(self, fun):
        """Generate a heading for the top of the iprofile."""
        if fun is None:
            self.html_value.h3("Summary")
            return

        try:
            heading = "{} (Calls: {}, Time: {})"
            heading = heading.format(fun.co_name,
                                     self.cprofile_tree[fun]['callcount'],
                                     self.cprofile_tree[fun]['totaltime'])
            self.html_value.h3(heading)
            self.html_value.p("From: " + fun.co_filename)
        except AttributeError:
            self.html_value.h3(fun)

    def generate_table(self, fun):
        """
        Generate a table displaying the functions called by fun and their
        respective running times.
        """
        table = self.html_value.table()
        h = table.thead().tr()
        h.th("Function")
        h.th("Total time (seconds)")
        if fun is None:
            args = self.cprofile_tree.keys()
        else:
            args = [function for function in self.cprofile_tree[fun]['calls']]
        # Sort by total time (descending)
        args.sort(key=lambda x: self.cprofile_tree[x]['totaltime'])
        args.reverse()

        for i in range(len(args)):
            arg = args[i]
            r = table.tr()
            # Function name
            try:
                name = arg.co_name
            except AttributeError:
                name = arg
            r.td.a(name, id="function" + str(i))

            # Total time spent in function
            r.td(str(self.cprofile_tree[arg]['totaltime']))
            self.n_table_elements += 1
            self.id_dict["function" + str(i)] = arg

    def generate_lprofile(self, fun):
        """
        Generate div containing profiled source code with timings of each line,
        taken from iline_profiler.
        """
        try:
            filename = fun.co_filename
            firstlineno = fun.co_firstlineno
            name = fun.co_name
        except AttributeError:
            return

        ltimings_key = (filename, firstlineno, name)

        try:
            ltimings = self.lprofile.timings[ltimings_key]
        except KeyError:
            return

        # Currently the correct filename is stored at the end of ltimings.
        # This is a work-around to fix cProfiler giving useless filenames for
        # zipped packages.
        filename = ltimings[-1]
        del ltimings[-1]
        print filename
        if filename.endswith(('.pyc', '.pyo')):
            filename = openpy.source_from_cache(filename)
        if ".egg/" in filename:
            add_zipped_file_to_linecache(filename)

        raw_code = ""
        linenos = range(firstlineno, ltimings[-1][0] + 1)

        for lineno in linenos:
            raw_code += ulinecache.getline(filename, lineno)

        formatter = LProfileFormatter(firstlineno, ltimings, noclasses=True)
        self.html_value += highlight(raw_code, PythonLexer(), formatter)

    def handle_on_msg(self, _, content, buffers):
        """
        Handler for click (and potentially other) events from the user.
        """
        clicked_fun = self.id_dict[content]
        self.generate_content(clicked_fun)

        self.value = str(self.html_value)

def add_zipped_file_to_linecache(filename):
    (zipped_filename, extension, inner) = filename.partition('.egg/')
    zipped_filename += extension[:-1]
    assert zipfile.is_zipfile(zipped_filename)
    zipped_file = zipfile.ZipFile(zipped_filename)
    ulinecache.cache[filename] = (None, None,
                                 zipped_file.open(inner, 'r').readlines())
    zipped_file.close()


class LProfileFormatter(HtmlFormatter):

    def __init__(self, firstlineno, ltimings, *args, **kwargs):
        self.lineno = firstlineno
        self.ltimings = ltimings
        super(LProfileFormatter, self).__init__(*args, **kwargs)

    def wrap(self, source, outfile):
        return super(LProfileFormatter,
                     self).wrap(self._wrap_code(source), outfile)

    def _wrap_code(self, source):
        head_template = '{} {} {}'
        no_time_template = '{:6} {:7} {:>4} {}'
        template = '{:06.2f} {:>7} {:>4} {}'
        time = '<span style=\'color: Red; font-weight: bold\'>Time</span>   '
        yield 0, head_template.format(time, ' Calls',
                                      ' <strong>Code</strong>\n')
        # j keeps track of position within ltimings
        j = 0
        for i, line in source:
            lineno = self.lineno
            if j < len(self.ltimings) and lineno == self.ltimings[j][0]:
                lcalls = self.ltimings[j][1]
                ltime = self.ltimings[j][2] * 1e-6
                yield i, template.format(ltime, lcalls, lineno, line)
                j += 1
            else:
                yield i, no_time_template.format('', '', lineno, line)
            self.lineno += 1

@magics_class
class IProfilerMagics(Magics):
    @line_magic
    def iprofile(self, line):
        import _iline_profiler
        import cProfile
        cprofiler = cProfile.Profile()
        lprofiler = _iline_profiler.LineProfiler()

        global_ns = self.shell.user_global_ns
        local_ns = self.shell.user_ns

        lprofiler.enable()
        cprofiler.enable()
        exec_(line, global_ns, local_ns)
        cprofiler.disable()
        lprofiler.disable()

        lprofile = lprofiler.get_stats()
        cprofile = cprofiler.getstats()

        iprofile = IProfile(cprofile, lprofile, context="LINE_MAGIC")

        # Note this name *could* clash with a user defined name...
        # Should find a better solution
        self.shell.user_ns['_IPROFILE'] = iprofile
        self.shell.run_cell('_IPROFILE')


def load_ipython_extension(shell):
    shell.register_magics(IProfilerMagics)
    cell = """%%javascript
require(["base/js/utils"], function(utils){
    utils.load_extensions('iprofiler');
});"""
    shell.run_cell(cell)
