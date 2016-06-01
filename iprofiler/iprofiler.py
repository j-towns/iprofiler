from IPython.utils import openpy
from IPython.utils import ulinecache
from IPython.core import display
from IPython.core.magic import (Magics, magics_class, line_magic,
                                cell_magic, line_cell_magic)

from ipywidgets import DOMWidget
from traitlets import Unicode, Int

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

import zipfile
import sys

from bokeh.embed import notebook_div
import bokeh.models.widgets.tables as bokeh_tables
from bokeh.models import ColumnDataSource
from bokeh.util.notebook import load_notebook
import bokeh.io as bokeh_io
import bokeh.util as bokeh_util
from bokeh.io import show, hplot, output_notebook
from bokeh.io import push_notebook

# Python 2/3 compatibility utils
# ===========================================================
PY3 = sys.version_info[0] == 3

# exec (from https://bitbucket.org/gutworth/six/):
if PY3:
    import builtins
    exec_ = getattr(builtins, "exec")
    del builtins
    from html import escape as html_escape
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
    from cgi import escape as html_escape

# ============================================================


class IProfile(DOMWidget):
    def __init__(self, cprofile, lprofile=None, context=None, *args, **kwargs):
        self.generate_cprofile_tree(cprofile, context)
        self.lprofile = lprofile

        # Two lists used for the back and forward buttons. Backward includes
        # the currently displayed function.
        self.backward = [None]
        self.forward = []

        # Dictionary mapping html id's to function names
        self.id_dict = {}
        self.init_bokeh_table_data()
        self.generate_content()
        self.on_msg(self.handle_on_msg)
        super(IProfile, self).__init__()

    def init_bokeh_table_data(self):
        table_data = dict(ids=[], names=[], times=[],
                          inlinetimes=[],
                          plot_inline_times=[],
                          plot_extra_times=[])
        self.table_data = ColumnDataSource(table_data)

    def generate_cprofile_tree(self, cprofile, context=None):
        """
        Generate a dict based on the output of the cProfiler.
        """
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
        for i in callcounts:
            if callcounts[i] == 0:
                self.roots.append(i)

        self.delete_top_level(context)

    def delete_top_level(self, context=None):
        """
        Delete the top level calls which are not part of the user's code.

        TODO: If CELL_MAGIC then also merge the entries for the cell (which are
        seperated by line into individual code objects...)
        """
        if context == "LINE_MAGIC":
            # Find the root nodes that we want
            new_roots = []
            for function in self.cprofile_tree:
                try:
                    if function.co_name == "<module>":
                        new_roots += self.cprofile_tree[function]['calls']
                except AttributeError:
                    pass

            # Remove function from new_roots if its child is already in
            # new_roots
            new_roots = [r for r in new_roots if (type(r) == str or
                                                  r.co_name != "<module>")]
            for i in range(len(new_roots)):
                function = new_roots[i]
                try:
                    if function.co_name == "<module>":
                        del new_roots[i]
                except AttributeError:
                    pass

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
    _view_module = Unicode('iprofiler').tag(sync=True)

    # The following traits are used to send data to the front end.
    # These traits contain the actual html displayed in the widget
    value_nav = Unicode().tag(sync=True)
    value_heading = Unicode().tag(sync=True)
    bokeh_table_div = Unicode().tag(sync=True)
    value_lprofile = Unicode().tag(sync=True)

    # Number of elements in table (used by front end to generate click events)
    n_table_elements = Int(0).tag(sync=True)

    def generate_content(self, fun=None):
        """Generate profile page for function fun. If fun=None then generate
        a summary page."""
        self.value_cache = ""
        self.generate_nav(fun)
        self.generate_heading(fun)
        self.generate_table(fun)
        self.generate_lprofile(fun)

    def generate_nav(self, fun):
        value_nav_cache = ''
        if fun is None:
            value_nav_cache += '<img src="/nbextensions/iprofiler/home.svg">'
        else:
            value_nav_cache += ('<a id="iprofile_home" '
                                'style="cursor:pointer">'
                                '<img src="/nbextensions/iprofiler/home.svg">'
                                '</a>')
        if len(self.backward) > 1:
            value_nav_cache += ('<a id="iprofile_back" '
                                'style="cursor:pointer">'
                                '<img src="/nbextensions/iprofiler/back.svg">'
                                '</a>')
        else:
            value_nav_cache += ('<img src="/nbextensions/iprofiler/back_'
                                'grey.svg">')
        if len(self.forward) > 0:
            value_nav_cache += ('<a id="iprofile_forward" '
                                'style="cursor:pointer"><img '
                                'src="/nbextensions/iprofiler/forward.svg">'
                                '</a>')
        else:
            value_nav_cache += ('<img src="/nbextensions/iprofiler/forward_'
                                'grey.svg">')
        self.value_nav = value_nav_cache

    def generate_heading(self, fun):
        """Generate a heading for the top of the iprofile."""
        value_heading_cache = ""
        if fun is None:
            value_heading_cache += "<h3>Summary</h3>"
        else:
            try:
                heading = "{} (Calls: {}, Time: {})"
                heading = heading.format(fun.co_name,
                                         self.cprofile_tree[fun]['callcount'],
                                         self.cprofile_tree[fun]['totaltime'])
                heading = html_escape(heading)
                value_heading_cache += "<h3>" + heading + "</h3>"
                value_heading_cache += ("<p>From file: " +
                                     html_escape(fun.co_filename) + "</p>")
            except AttributeError:
                value_heading_cache += "<h3>" + html_escape(fun) + "</h3>"

        self.value_heading = value_heading_cache

    def generate_table(self, fun):
        """
        Generate a table displaying the functions called by fun and their
        respective running times. This is done using Bokeh's DataTable widget,
        which is based on SlickGrid.
        """
        if fun is None:
            # Generate summary page
            calls = self.cprofile_tree.keys()
        else:
            calls = [function for function in self.cprofile_tree[fun]['calls']]

        self.n_table_elements = len(calls)

        names = [call if type(call) == str else call.co_name for call in calls]

        # List of tuples containing:
        # (id number, name, totaltime, inlinetime, cprofile_key)
        calls = list(zip(range(len(calls)), names,
                         (self.cprofile_tree[x]['totaltime'] for x in calls),
                         (self.cprofile_tree[x]['inlinetime'] for x in calls),
                         calls))

        self.id_dict = {"function" + str(id): cprofile_key for
                        (id, name, time, inlinetime, cprofile_key) in calls}

        # Sort by total time (descending)
        calls.sort(key=lambda x: x[2])
        calls.reverse()

        # Generate bokeh table
        try:
            ids, names, times, inlinetimes = list(zip(*calls))[:-1]
        except ValueError:
            return

        time_plot_multiplier = 100 / max(times)
        plot_inline_times = [time_plot_multiplier * time for time in
                             inlinetimes]
        plot_extra_times = [time_plot_multiplier * (totaltime - inlinetime)
                            for totaltime, inlinetime in zip(times,
                                                             inlinetimes)]

        self.table_data.data = dict(ids=ids, names=names, times=times,
                                    inlinetimes=inlinetimes,
                                    plot_inline_times=plot_inline_times,
                                    plot_extra_times=plot_extra_times)

        if self.bokeh_table_div == "":
            # First run
            self.init_bokeh_table()
        else:
            push_notebook()

    def init_bokeh_table(self):
        time_format = bokeh_tables.NumberFormatter(format='0,0.00000')

        name_template = '<a id="function<%= ids %>", style="cursor:pointer"><%- names %></a>'
        name_format = (bokeh_tables.
                       HTMLTemplateFormatter(template=name_template))

        time_plot_template = ('<img src="/nbextensions/iprofiler/red.gif"' +
                              'height="10" width="<%= plot_inline_times%>">' +
                              '<img src="/nbextensions/iprofiler/pink.gif"' +
                              'height="10" width="<%= plot_extra_times %>">')
        time_plot_format = (bokeh_tables.
                            HTMLTemplateFormatter(template=time_plot_template))

        columns = [bokeh_tables.TableColumn(title="Function",
                                            field="names",
                                            formatter=name_format),
                   bokeh_tables.TableColumn(title="Total time (s)",
                                            field="times",
                                            formatter=time_format,
                                            default_sort="descending"),
                   bokeh_tables.TableColumn(title="Inline time (s)",
                                            field="inlinetimes",
                                            formatter=time_format,
                                            default_sort="descending"),
                   bokeh_tables.TableColumn(title="Time plot",
                                            sortable=False,
                                            formatter=time_plot_format)]

        bokeh_table = bokeh_tables.DataTable(source=self.table_data,
                                             columns=columns,
                                             # Would be nice if width could
                                             # be automatic but this appears
                                             # to be broken in firefox and
                                             # chrome.
                                             width=620,
                                             height=200,
                                             selectable=False)

        self.bokeh_table = bokeh_table

        comms_target = bokeh_util.serialization.make_id()
        self.bokeh_comms_target = comms_target
        self.bokeh_table_div = notebook_div(hplot(bokeh_table), comms_target)
        #show(vform(self.bokeh_table))

    def generate_lprofile(self, fun):
        """
        Generate div containing profiled source code with timings of each line,
        taken from iline_profiler.
        """
        self.value_lprofile = ""
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
        self.value_lprofile = highlight(raw_code, PythonLexer(), formatter)

    def handle_on_msg(self, _, content, buffers):
        """
        Handler for click (and potentially other) events from the user.
        """
        if content == "home":
            self.backward.append(None)
            self.forward = []
            self.generate_content()
        elif content == "back":
            self.forward.append(self.backward.pop())
            self.generate_content(self.backward[-1])
        elif content == "forward":
            self.backward.append(self.forward.pop())
            self.generate_content(self.backward[-1])
        elif content == "init_complete":
            comms_target = self.bokeh_comms_target
            self.bokeh_table_handle = (bokeh_io.
                                   _CommsHandle(bokeh_util.notebook.
                                                get_comms(comms_target),
                                   bokeh_io.curstate().document,
                                   bokeh_io.curstate().document.to_json()))
            bokeh_io._state.last_comms_handle = self.bokeh_table_handle
        else:
            clicked_fun = self.id_dict[content]
            self.backward.append(clicked_fun)
            self.forward = []
            self.generate_content(clicked_fun)


def add_zipped_file_to_linecache(filename):
    (zipped_filename, extension, inner) = filename.partition('.egg/')
    zipped_filename += extension[:-1]
    assert zipfile.is_zipfile(zipped_filename)
    zipped_file = zipfile.ZipFile(zipped_filename)
    ulinecache.linecache.cache[filename] = (None, None,
                                            zipped_file.open(inner, 'r').
                                            readlines())
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
        import iprofiler.iline_profiler._iline_profiler as _iline_profiler
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
    output_notebook(hide_banner=True)
    shell.register_magics(IProfilerMagics)
