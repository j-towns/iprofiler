import html
from ipywidgets import DOMWidget
from traitlets import Unicode, Int
from ipywidgets.widgets.widget import CallbackDispatcher, register

from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import HtmlFormatter

import linecache


class IProfile(DOMWidget):
    def __init__(self, cprofile, lprofile=None, *args, **kwargs):
        self.generate_cprofile_tree(cprofile)
        self.lprofile = lprofile
        self.generate_content(self.roots[0])
        self.value = str(self.html_value)
        self.on_msg(self.handle_on_msg)

        super(IProfile, self).__init__(value=self.value)

    def generate_cprofile_tree(self, cprofile):
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

    _view_name = Unicode('IProfileView').tag(sync=True)

    # This trait is the actual html displayed in the widget
    value = Unicode().tag(sync=True)

    # Number of elements in table (used by front end to generate click events)
    n_table_elements = Int(0).tag(sync=True)

    # Dictionary mapping html id's to function names
    id_dict = {}

    def generate_content(self, fun):
        # Generate page for a particular function fun
        self.html_value = html.HTML()
        self.generate_table(fun)
        if self.lprofile is not None:
            self.generate_lprofile(fun)

    def generate_table(self, fun):
        """
        Generate a table displaying the functions called by fun and their
        respective running times.
        """
        table = self.html_value.table()
        h = table.thead().tr()
        h.th("Function")
        h.th("Total time (seconds)")
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

        raw_code = ""
        linenos = range(firstlineno, ltimings[-1][0] + 1)
        for lineno in linenos:
            raw_code += linecache.getline(fun.co_filename, lineno)

        formatter = LProfileFormatter(firstlineno, ltimings, noclasses=True)
        self.html_value += highlight(raw_code, PythonLexer(), formatter)

    def handle_on_msg(self, _, content, buffers):
        clicked_fun = self.id_dict[content]
        self.generate_content(clicked_fun)

        self.value = str(self.html_value)

class LProfileFormatter(HtmlFormatter):

    def __init__(self, firstlineno, ltimings, *args, **kwargs):
        self.lineno = firstlineno
        self.ltimings = ltimings
        super(LProfileFormatter, self).__init__(*args, **kwargs)

    def wrap(self, source, outfile):
        return super(LProfileFormatter,
                     self).wrap(self._wrap_code(source), outfile)

    def _wrap_code(self, source):
        template = '{:>8} {:>6} {:>4} {}'
        yield 0, template.format('Time', 'Calls', '<strong>Code</strong>', '\n')
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
                yield i, template.format('', '', lineno, line)
            self.lineno += 1
