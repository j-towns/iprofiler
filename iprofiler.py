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

from bokeh.charts import Bar
from bokeh.embed import notebook_div
from bokeh.charts.attributes import CatAttr
import bokeh.models.widgets.tables as bokeh_tables
from bokeh.models import ColumnDataSource
from bokeh.util.notebook import load_notebook
from bokeh.io import show, vform

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

        If CELL_MAGIC then also merge the entries for the cell (which are
        seperated by line into individual code objects...)
        """
        if context == "LINE_MAGIC":
            junk_calls = self.roots
            tree = self.cprofile_tree
            junk_calls.append(tree[junk_calls[0]]['calls'].keys()[0])
            junk_calls.append(tree[junk_calls[-1]]['calls'].keys()[0])
            for junk_call in junk_calls:
                del self.cprofile_tree[junk_call]

        if context == "CELL_MAGIC":
            # Find the root nodes that we want
            new_roots = []
            for function in self.cprofile_tree:
                try:
                    if "<ipython-input" in function.co_filename:
                        new_roots += self.cprofile_tree[function]['calls']
                except AttributeError:
                    pass

            # Populate a new tree with everything below roots in the original
            # tree.
            new_cprofile_tree = {}
            def populate_new_tree(roots):
                for root in roots:
                    if root not in new_cprofile_tree:
                        new_cprofile_tree[root] = self.cprofile_tree[root]
                        populate_new_tree(self.cprofile_tree[root]['calls'])

            populate_new_tree(new_roots)
            self.cprofile_tree = new_cprofile_tree
            self.roots = new_roots

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
        if fun is None:
            # Generate summary page
            calls = self.cprofile_tree.keys()
        else:
            calls = [function for function in self.cprofile_tree[fun]['calls']]

        names = list()
        for call in calls:
            try:
                names.append(str(call.co_name))
            except AttributeError:
                names.append(str(call))

        # List of tuples containing:
        # (id number, name, totaltime, inlinetime, cprofile_key)
        calls = zip(range(len(calls)), names,
                    (self.cprofile_tree[x]['totaltime'] for x in calls),
                    (self.cprofile_tree[x]['inlinetime'] for x in calls),
                    calls)

        self.id_dict = {"function" + str(id): cprofile_key for
                        (id, name, time, inlinetime, cprofile_key) in calls}
        self.n_table_elements = len(calls)

        # Sort by total time (descending)
        calls.sort(key=lambda x: x[2])
        calls.reverse()

        # Generate bokeh table
        try:
            ids, names, times, inlinetimes = zip(*calls)[:-1]
        except ValueError:
            return
        table_data = dict(ids=ids, names=names, times=times,
                          inlinetimes=inlinetimes)
        table_data = ColumnDataSource(table_data)

        time_formatter = bokeh_tables.NumberFormatter(format='0,0.000')
        name_formatter = bokeh_tables.HTMLTemplateFormatter(
        template='<a id="function<%= ids %>"><%- names %></a>'
        )

        columns = [
        bokeh_tables.TableColumn(title="Function",
                                 field="names",
                                 formatter=name_formatter),
        bokeh_tables.TableColumn(title="Total time (s)",
                                 field="times",
                                 formatter=time_formatter,
                                 default_sort="descending"),
        bokeh_tables.TableColumn(title="Inline time (s)",
                                 field="inlinetimes",
                                 formatter=time_formatter,
                                 default_sort="descending")
        ]

        bokeh_table = bokeh_tables.DataTable(source=table_data,
                                             columns=columns,
                                             # Would be nice if width could
                                             # be automatic but this appears
                                             # to be broken in firefox and
                                             # chrome.
                                             width=620,
                                             height='auto',
                                             selectable=False)

        self.html_value += notebook_div(bokeh_table)

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

        if filename.endswith(('.pyc', '.pyo')):
            filename = openpy.source_from_cache(filename)
        if ".egg/" in filename:
            add_zipped_file_to_linecache(filename)

        raw_code = ""
        linenos = range(firstlineno, ltimings[-2][0] + 1)

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
    ulinecache.linecache.cache[filename] = (None, None,
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
        template = '<span style=\'color: Red\'>{:06.2f}</span> {:>7} {:>4} {}'
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
    @line_cell_magic
    def iprofile(self, line, cell=None):
        import _iline_profiler
        import cProfile
        cprofiler = cProfile.Profile()
        lprofiler = _iline_profiler.LineProfiler()

        if cell is None:
            # LINE MAGIC
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
        else:
            lprofiler.enable()
            cprofiler.enable()
            self.shell.run_cell(cell)
            cprofiler.disable()
            lprofiler.disable()

            lprofile = lprofiler.get_stats()
            cprofile = cprofiler.getstats()

            iprofile = IProfile(cprofile, lprofile, context='CELL_MAGIC')

            # Note this name *could* clash with a user defined name...
            # Should find a better solution
            self.shell.user_ns['_IPROFILE'] = iprofile
            self.shell.run_cell('_IPROFILE')

def load_ipython_extension(shell):
    # Initiate bokeh
    load_notebook(hide_banner=True)
    shell.register_magics(IProfilerMagics)
    cell = """%%javascript
require(["base/js/utils"], function(utils){
    utils.load_extensions('iprofiler');
});"""
    shell.run_cell(cell)
