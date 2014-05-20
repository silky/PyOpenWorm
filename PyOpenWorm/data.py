
# A consolidation of the data sources for the project
# includes:
# NetworkX!
# RDFlib!
# CSV!
# Other things!
#
# Works like Configure:
# Inherit from the Data class to access data of all kinds (listed above)

import sqlite3
import networkx as nx
import PyOpenWorm
from PyOpenWorm import Configure
import hashlib
import csv
import urllib2
from rdflib import URIRef, Literal, Graph, Namespace, ConjunctiveGraph, BNode
from rdflib.namespace import RDFS

# encapsulates some of the data all of the parts need...
class _B:
    def __init__(self, f):
        self.v = False
        self.f = f

    def get(self):
        if not self.v:
            self.v = self.f()

        return self.v
    def invalidate(self):
        self.v = False

class _Z:
    def __init__(self, c, n):
        self.n = n
    def get(self):
        return c[n]

class SPARQLSource(Configure):
    def get(self):
        # XXX: If we have a source that's read only, should we need to set the store separately??
        g0 = ConjunctiveGraph('SPARQLUpdateStore')
        g0.open(self['rdf.store_conf'])
        return g0
class SQLiteSource(Configure):
    def get(self):
        conn = sqlite3.connect(self['sqldb'])
        cur = conn.cursor()

        #first step, grab all entities and add them to the graph

        cur.execute("SELECT DISTINCT ID, Entity FROM tblentity")

        n = Namespace("http://openworm.org/entities/")

        # print cur.description

        g0 = ConjunctiveGraph(self['rdf.store'])
        #print self['rdf.store']
        g0.open(self['rdf.store_conf'], create=True)

        for r in cur.fetchall():
            #first item is a number -- needs to be converted to a string
           first = str(r[0])
           #second item is text
           second = str(r[1])

           # This is the backbone of any RDF graph.  The unique
           # ID for each entity is encoded as a URI and every other piece of
           # knowledge about that entity is connected via triples to that URI
           # In this case, we connect the common name of that entity to the
           # root URI via the RDFS label property.
           g0.add( (n[first], RDFS.label, Literal(second)) )


        #second step, get the relationships between them and add them to the graph
        cur.execute("SELECT DISTINCT EnID1, Relation, EnID2, Citations FROM tblrelationship")

        gi = ''

        i = 0
        for r in cur.fetchall():
           #all items are numbers -- need to be converted to a string
           first = str(r[0])
           second = str(r[1])
           third = str(r[2])
           prov = str(r[3])

           ui = self['molecule_name'](prov)
           gi = Graph(g0.store, ui)

           gi.add( (n[first], n[second], n[third]) )

           g0.add([ui, RDFS.label, Literal(str(i))])
           if (prov != ''):
               g0.add([ui, n[u'text_reference'], Literal(prov)])

           i = i + 1

        cur.close()
        conn.close()

        return g0

class Data(PyOpenWorm.Configure):
    def __init__(self, conf=False):
        PyOpenWorm.Configure.__init__(self,conf)
        self['nx'] = _B(self._init_networkX)
        try:
            self['rdf.store'] = 'default'
            self['rdf.store_conf'] = 'default'
        except PyOpenWorm.DoubleSet:
            pass
        self._init_rdf_graph()

    def _init_rdf_graph(self):
        # check rdf.source
        self['molecule_name'] = self._molecule_hash
        d = {'sqlite' : SQLiteSource(self),
                'sparql_endpoint' : SPARQLSource(self)}
        i = d[self['rdf.source']]
        self['rdf.graph'] = i
        self['semantic_net_new'] = i
        self['semantic_net'] = i

    def _molecule_hash(self, data):
        return URIRef(u'http://openworm.org/rdfmolecules/' + hashlib.sha224(data).hexdigest())

    def _init_networkX(self):
        g = nx.DiGraph()

        # Neuron table
        csvfile = urllib2.urlopen(self['neuronscsv'])

        reader = csv.reader(csvfile, delimiter=';', quotechar='|')
        for row in reader:
            neurontype = ""
            # Detects neuron function
            if "sensory" in row[1].lower():
                neurontype += "sensory"
            if "motor" in row[1].lower():
                neurontype += "motor"
            if "interneuron" in row[1].lower():
                neurontype += "interneuron"
            if len(neurontype) == 0:
                neurontype = "unknown"

            if len(row[0]) > 0: # Only saves valid neuron names
                g.add_node(row[0], ntype = neurontype)

        # Connectome table
        csvfile = urllib2.urlopen(self['connectomecsv'])

        reader = csv.reader(csvfile, delimiter=';', quotechar='|')
        for row in reader:
            g.add_edge(row[0], row[1], weight = row[3])
            g[row[0]][row[1]]['synapse'] = row[2]
            g[row[0]][row[1]]['neurotransmitter'] = row[4]
        return g

