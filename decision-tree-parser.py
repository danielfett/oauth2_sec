#!/usr/bin/python3
import yaml, json
from itertools import chain
import sys

document = open(sys.argv[1], 'r')

config, rules = yaml.load_all(document)

nodes = []


origid = id
def id(obj):
    return 'node' + str(origid(obj))

class VarNode:
    def __init__(self, parent, variables, config):
        self.parent = parent
        self.children = []
        if self.parent is not None:
            self.parent.children.append(self)
        self.variables = variables
        self.config = config
        self.outcomes = {}

    @property
    def all_vars(self):
        out = self.variables.copy()
        if self.parent is not None:
            out.update(self.parent.all_vars)
        return out

    def check(self, expression):
        vars = self.all_vars
        return eval(expression, {}, vars)

    def __iter__(self):
        yield self
        yield from chain(*map(iter, self.children))

    def iter_edges(self):
        for c in self.children:
            yield (self, c)
        yield from chain(*map(VarNode.iter_edges, self.children))

    def __str__(self):
        if not self.parent:
            return ''
        value = self.variables[self.config['id']]
        text = next((x['name'] for x in self.config['values'] if x['value'] == value), '???')
        return text

    def get_state(self, prop):
        if prop in self.outcomes:
            if self.outcomes[prop] is True:
                return 'pass'
            else:
                return 'fail'
        return "unknown"

variables = {}


def parse_config(parent_nodes, config):
    if not 'values' in config:
        config['values'] = [
            {'value': True, 'name': 'yes'},
            {'value': False, 'name': 'no'},
        ]
    new_nodes = []
    for value in config['values']:
        for parent_node in parent_nodes:
            if 'conflict' in value:
                if parent_node.check(value['conflict']):
                    continue
            var_values = {
                config['id']: value['value'],
            }
            if 'implies' in value:
                var_values.update(value['implies'])
            n = VarNode(parent_node, var_values, config)
            new_nodes.append(n)
    return new_nodes


start_node = VarNode(None, {}, {
    'name': "OAuth",
    'type': "root",
    'id': 'root',
})
nodes = [start_node]

for c in config['variables']:
    nodes = parse_config(nodes, c)


for ruleset in rules:
    for r in ruleset['rules']:
        prop = r['prop'].strip()
        if prop.startswith('not '):
            prop = prop[4:].strip()
            res = False
        else:
            res = True

        for n in start_node:
            print (n)
            try:
                if n.check(r['if']):
                    n.outcomes[prop] = res
                    print (f"Setting {prop} to {res}")
            except NameError as e:
                print (str(e) + ", vars: " + repr(n.all_vars))
                continue

def filename(config, outcome):
    return f"{config['id']}-{outcome['id']}.html"

def write_output_for(outcome):

    nodes = [
        {
            'data': {
                'id': id(n),
                'label': str(n),
                'state': n.get_state(outcome['id']),
                'parent': n.config['id']
            }, 
        } for n in start_node
    ]

    nodes += [
        {
            'data': {
                'id': v['id'],
                'label': (v['type'] + ": " + v['name']),
            }
        } for v in config['variables']
    ]

    edges = [
        {
            'data': {
                'source': id(s), 'target': id(t),
            }
        } for s, t in start_node.iter_edges()
    ]

    elements = {
        'nodes': nodes,
        'edges': edges
    }

    root = id(start_node)

    style = [
        {
            'selector': 'node',
            'css': {
                'content': 'data(label)',
                'font-size': '25px',
            }
        },
        {
            'selector': 'edge',
            'css': {
                'curve-style': 'bezier',
                'target-arrow-shape': 'triangle',
                'width': 4,
                'line-color': '#ddd',
                'target-arrow-color': '#ddd',
            }
        },
        {
            'selector': 'node[state="pass"]',
            'css': {
                'background-color': '#70ff60',
            }
        },
        {
            'selector': 'node[state="fail"]',
            'css': {
                'background-color': '#ff7060',
            }
        },
        {
            'selector': '$node > node',
            'css': {
                'padding-top': '10px',
                'padding-left': '10px',
                'padding-bottom': '10px',
                'padding-right': '10px',
                'text-valign': 'top',
                'text-halign': 'center',
                'font-size': '30px',
            }
        }
    ]

    js = """
    var cy = cytoscape({
      container: document.getElementById('cy'),

      boxSelectionEnabled: false,
      autounselectify: true,

        style: """ + json.dumps(style) + """,
        elements: """ + json.dumps(elements) + """,
        layout: {
        name: 'breadthfirst',
        directed: true,
        roots: '#""" + root + """',
        padding: 10
      }
    });

    """

    links = " &middot; ".join("<a href='" + filename(config, o) + "'>" + o['name'] + "</a>" for o in config['outcomes'])


    with open(filename(config, outcome), 'w') as f:

        f.write(f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
        body {{
          font: 20px helvetica neue, helvetica, arial, sans-serif;
        }}

        #cy {{
          height: 100vh;
          width: 100vw;
        }}
        </style>
        <meta charset=utf-8 />
        <meta name="viewport" content="user-scalable=no, initial-scale=1.0, minimum-scale=1.0, maximum-scale=1.0, minimal-ui">
        <title>Security Analysis {config['name']} / {outcome['name']}</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.2.20/cytoscape.js"></script>
        </head>
        <body>
        <div>
        <h1>Security Analysis {config['name']}</h1>
        <h2>{outcome['name']}</h2>
        <b>{outcome['desc']} (green=true, red=false, grey=unknown)</b><br>
        Other properties: {links}
        </div>
        <div id="cy"></div>
        <!-- Load application code at the end to ensure DOM is loaded -->
        <script>
        {js}
        </script>

        
        </body>
        </html>
        """)
        
for o in config['outcomes']:
    write_output_for(o)
