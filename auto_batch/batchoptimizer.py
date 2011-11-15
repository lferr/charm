
from batchlang import *
import batchparser
import string

class ExpInstanceFinder:
    def __init__(self):
        # keys must match
        self.instance = {}
    
    def visit(self, node, data):
        pass
    
    def visit_exp(self, node, data):
        left = node.left
        right = node.right
        if left.type == ops.ATTR:
            if right.type == ops.ATTR:
                self.record(str(left), str(right))
            elif right.type == ops.MUL:
                # a ^ (b * c) ==> a : b, a : c
                value_1 = right.left
                value_2 = right.right
                if value_1.type == ops.ATTR:
                    self.record(str(left), str(value_1))
                if value_2.type == ops.ATTR:
                    self.record(str(left), str(value_2))
            else:
                # dont care for now
                return

    def record(self, key, value):
#        print("key =>", key, ", value =>", value)
        if self.instance.get( key ):
            if self.instance[ key ].get( value ):
                self.instance[ key ][ value ] += 1
            else:
                self.instance[ key ][ value ] = 1
            return

        self.instance[ key ] = { value: 1 }
        return


class PairInstanceFinder:
    def __init__(self):
        # keys must match
        self.instance = {}
        self.index = 0
        
    def visit(self, node, data):
        pass
    
    def visit_pair(self, node, data):
        lhs = node.left
        rhs = node.right
        if Type(lhs) == ops.ATTR:
            key = 'left'

        if Type(rhs) == ops.ATTR:
            key = 'right'        
        self.record(key, lhs, rhs)
        return

    def record(self, key, lnode, rnode):
        print("key =>", key, ", nodes =>", lnode, rnode)
        found = False
        for i in self.instance.keys():
            data = self.instance[ i ]
            if data['key'] == 'left':
                if str(lnode) == str(data['lnode']): # found a match
                    data['instance'] += 1; found = True
                    break
            elif data['key'] == 'right':
                if str(rnode) == str(data['rnode']):
                    data['instance'] += 1; found = True
                    break
        # if not found
        if not found:
            self.instance[ self.index ] = { 'key':key, 'lnode':lnode, 'rnode':rnode, 'instance':1 }
            self.index += 1
        return


# substitute nodes that can be precomputed with a stub
# variable that is computed later
class SubstituteExps:
    def __init__(self, op_instance, precomp, variables):
        # assert input is not equal to None
        self.instance = op_instance
        self.inst_map = {}
        self.precomp = precomp
        self.precomp_code = {} # for new optimizations we find
        self.vars = variables
        self.prefix = 'pre' # self.prefix + self.alpha[cnt]; cnt += 1
        self.alpha = string.ascii_uppercase
        self.cnt = 0

    # TODO: clean-up this implementation
    def canExpBePrecomputed(self, base, exp):
        for i in self.instance.keys():
            for j in self.instance[ i ].keys():
                if self.instance[ i ][ j ] > 1 and (i == str(base) and j == str(exp)) and len(base.attr_index) == 1:
                    # combine sets: TODO
                    if base.attr_index: index = base.attr_index[0] 
                    if exp.attr_index: index = exp.attr_index[0]
                    else: index = None
                    _key = self.record(str(i), str(j), index)
                    #print("_key =>", _key, "\n\n")
                    k = BinaryNode(_key)

                    self.precomp[ _key ] = str(i) + "^" + str(j)
#                    if index == 'j': # "j => N", "i => whatever"
#                        bp = batchparser.BatchParser()
#                        self.precomp_code[ _key ] = bp.parse("for{j:=1, N} do " + str(i) + "^" + str(j))   
                    if self.vars.get(base.getAttribute()) == None:
                        print("Need to define variable: ", base.getAttribute())
                    else:
                        self.vars[ k.getAttribute() ] = self.vars[ base.getAttribute() ]
                    # can we find a precomp key for this? if so, return it
                    # otherwise, create one and return it.(IMPORTANT!!!!)
                    return _key
        return False

    def record(self, key, value, index=None):
#        print("key =>", key, ", value =>", value)
        if self.inst_map.get( key ):
            if self.inst_map[ key ].get( value ):
                var = self.inst_map[ key ][ value ]
                #print("recovered key =>", var)
                return var
            else:
                self.cnt += 1
                if index: var_index = index
                else: var_index = ''
                self.inst_map[ key ][ value ] = self.prefix + self.alpha[self.cnt] + '_' + var_index
                return self.inst_map[ key ][ value ]
            return 
        
        if index: var_index = index
        else: var_index = ''
        self.inst_map[ key ] = { value: self.prefix + self.alpha[self.cnt] + '_' + var_index }
        self.cnt += 1
        #print("found key =>", self.inst_map[ key ][ value ])
        return self.inst_map[ key ][ value ]

    def visit(self, node, data):
        pass
    
    def visit_exp(self, node, data):
        left = node.left
        right = node.right
        #print("left type =>", Type(left))
        if Type(left) == ops.ATTR:
            if Type(right) == ops.ATTR:
                key = self.canExpBePrecomputed(left, right)
                if key:
                    # make substitution
                    new_node = BinaryNode(key)
                    batchparser.addAsChildNodeToParent(data, new_node)
                else:
                    pass
                    #print("left =>", left)
                    #print("right =>", right) 
                    # no need to apply any substitutions
            elif Type(right) == ops.MUL:
                node_1 = right.left
                node_2 = right.right
#                print("left =>", left)
#                print("node1 =>", node_1)
#                print("node2 =>", node_2)
                if Type(node_1) == ops.ATTR:
                    key = self.canExpBePrecomputed(left, node_1)
                    if key:
                        # a ^ (b * c) ==> A ^ c (if a^b can be precomputed)
                        new_node1 = BinaryNode(ops.EXP)
                        new_node1.left = BinaryNode(key)
                        new_node1.right = node_2                        
                        batchparser.addAsChildNodeToParent(data, new_node1)
                
                if Type(node_2) == ops.ATTR:
                    key = self.canExpBePrecomputed(left, node_2)
                    if key:
                        # a ^ (b * c) ==> A ^ b (if a^c can be precomputed)                        
                        new_node2 = BinaryNode(ops.EXP)
                        new_node2.left = BinaryNode(key)
                        new_node2.right = node_1
                        batchparser.addAsChildNodeToParent(data, new_node2)
            elif Type(right) == ops.OF:
                pass
            else:
                print("Substitute: missing some cases: ", Type(right))

class SubstitutePairs:
    pass

class SubstituteSigDotProds:
    def __init__(self, vars, index='z', sig='N' ):
        self.prefix = 'dot' # self.prefix + self.alpha[cnt]; cnt += 1
        self.alpha = string.ascii_uppercase
        self.cnt = 0        
        self.sig = sig 
        self.index = index 
        self.vars_def = vars
        self.dotprod = { 'start':'1', 'stop':self.sig, 'index':self.index, 'list':[], 'dict':{}, 'types':{} }

    def setState(self, count):
        self.cnt = count # allow us to maintain a synchronized alphabet
        
    def getkey(self):
        key = self.prefix + self.alpha[self.cnt]
        self.cnt += 1
        #print('key =>', key)
        return key
    
    def store(self, key, value, the_type=None):
        self.dotprod[ 'dict' ][ key ] = value
        self.dotprod[ 'types' ][ key ] = the_type
        self.dotprod[ 'list' ].append( key )
    
    def visit(self, node, data):
        pass
    
    def visit_on(self, node, data):
        index = str(node.left.right.attr)
        dot_type = self.deriveNodeType(node.right)
        #print("node.right type +=> ", dot_type, node.right)
        #print("index =>", index)

        n = self.searchProd(node.right, node)
        if n:
            (t, p) = n
#            print("Found it:", t)
            dot_type2 = self.deriveNodeType(t.right)
            # perform substition
            subkey = BinaryNode(self.getkey())
            self.store(subkey, t, dot_type2)
            if p.left == t:
                p.left = subkey
#                print("p =>", p)
        
        if index == self.sig:
            key = BinaryNode(self.getkey())
            self.store(key, node, dot_type)
            
            batchparser.addAsChildNodeToParent(data, key)
    
#    def visit_of(self, node, data):
#        sig = str(node.left.right.attr)
#
#        if sig == self.sig:
#            key = BinaryNode(self.getkey())
#            self.store(key, node)
#            batchparser.addAsChildNodeToParent(data, key)
#            
                
    def searchProd(self, node, parent):
        if node == None: return None
        elif node.type == ops.ON:
            return (node, parent)
        else:
            result = self.searchProd(node.left, node)
            if result: return result            
            result = self.searchProd(node.right, node)
            return result

    def deriveNodeType(self, node):
        if node.type == ops.ATTR:
            _type = node.attr
        elif node.type == ops.HASH:
            _type = str(node.right.attr)
            return _type
        elif node.type == ops.EXP:
            return self.deriveNodeType(node.left)
        elif node.type == ops.PAIR:
            return 'GT'
        elif node.type == ops.ON:
            return self.deriveNodeType(node.right)
        elif node == None:
            return None
        else:
            return self.deriveNodeType(node.left)
        #print("printing type =>", _type)
        #print("node =>", node)
        assert self.vars_def.get(_type) != None, "Key error in vars db => '%s'" % _type
        return self.vars_def[_type]
