#!/usr/bin/python3
import yaml, json
from itertools import chain
import sys
from jinja2 import Template

document = open(sys.argv[1], 'r')

config = yaml.load(document)

nodes = []


origid = id
def id(obj):
    return 'node' + str(origid(obj))

class Rule:
    def __init__(self, obj):
        self.condition = obj['if']
        self.desc = obj['desc']
        prop = obj['secprop'].strip()
        if prop.startswith('not '):
            prop = prop[4:].strip()
            res = 'false'
        elif prop.startswith('~'):
            res = 'conditional'
        else:
            res = 'true'
        self.secprop = prop
        self.result = res

    def to_css(self):
        return f"{self.secprop}_{self.result}"


class VarNode:
    def __init__(self, parent, variables, config):
        self.parent = parent
        self.children = []
        if self.parent is not None:
            self.parent.children.append(self)
        self.variables = variables
        self.config = config
        self.secprops = {}

    @property
    def all_vars(self):
        out = self.variables.copy()
        if self.parent is not None:
            out.update(self.parent.all_vars)
        return out

    def check(self, expression):
        vars = self.all_vars
        return eval(expression, {}, vars)

    def check_rule(self, rule):
        try:
            if n.check(rule.condition):
                if rule.secprop in self.secprops:
                    self.secprops[rule.secprop].append(rule)
                else:
                    self.secprops[rule.secprop] = [rule]
        except NameError as e:
            print (str(e) + ", vars: " + repr(n.all_vars))

    def __iter__(self):
        yield self
        yield from chain(*map(iter, self.children))

    def iter_edges(self):
        for c in self.children:
            yield (self, c)
        yield from chain(*map(VarNode.iter_edges, self.children))

    def iter_leaves(self):
        if self.is_leaf:
            yield self
        else:
            yield from chain(*map(VarNode.iter_leaves, self.children))

    def iter_non_leaves(self):
        if not self.is_leaf:
            yield self
        else:
            yield from chain(*map(VarNode.iter_leaves, self.children))
        

    @property
    def is_leaf(self):
        return len(self.children) == 0

    def __str__(self):
        if not self.parent:
            return ''
        value = self.variables[self.config['id']]
        text = next((x['name'] for x in self.config['values'] if x['value'] == value), '???')
        return text

    def to_cy_nodes(self):
        yield {
            'data': {
                'type': 'node',
                'id': id(self),
                'label': str(self),
                'parent': self.config['id']
            }, 
        }
        if self.parent is None:
            yield {
                'data': {
                    'type': 'node',
                    'id': 'secprop_results',
                }
            }
        if self.is_leaf:
            for prop, rules in self.secprops.items():
                last_rule = rules[-1]
                yield {
                    'data': {
                        'type': 'secprop',
                        'id': f"secprop_{id(self)}_{prop}",
                        'state': last_rule.to_css(),
                        'parent': 'secprop_results',
                    }, 
                }
        else:
            yield from chain(*map(VarNode.to_cy_nodes, self.children))
            
    def to_cy_edges(self):
        for c in self.children:
            yield {
                'data': {
                    'source': id(self), 'target': id(c),
                }
            }
        if self.is_leaf:
            for prop, rules in self.secprops.items():
                yield {
                    'data': {
                        'source': id(self),
                        'target': f"secprop_{id(self)}_{prop}",
                    }
                }
                yield {
                    'data': {
                        'source': f"secprop_{id(self)}_{prop}",
                        'target': id(rules[-1]),
                    }
                }
        yield from chain(*map(VarNode.to_cy_edges, self.children))

    

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
    'name': config['name'],
    'type': "root",
    'id': 'root',
})
nodes = [start_node]

for c in config['variables']:
    nodes = parse_config(nodes, c)

rules = [Rule(r) for r in config['rules']]

for rule in rules:
    for n in start_node.iter_leaves():
        n.check_rule(rule)

def filename(config):
    return f"{config['id']}.html"

def write_output_for(template):

    nodes = list(start_node.to_cy_nodes())


    nodes += [
        {
            'data': {
                'type': 'variable',
                'id': v['id'],
                'label': v['name'],
            }
        } for v in config['variables']
    ]

    nodes += [
        {
            'data': {
                'type': 'rule',
                'id': id(rule),
                'label': rule.desc
            }
        } for rule in rules
    ]
        
    elements = {
        'nodes': nodes,
        'edges': list(start_node.to_cy_edges())
    }

    root = id(start_node)

    
    with open(filename(config), 'w') as f:
        f.write(template.render(
            root=root,
            elements=json.dumps(elements),
            config=config,       
        ))

template = Template(open(config['template'], 'r').read())

write_output_for(template)
