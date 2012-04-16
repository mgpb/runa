from util import Error
import ast, types

LIBRARY = {
	'print': ('print', 'void', [('s', 'IStr')]),
	'str': ('str', 'str', [('v', 'IStr')]),
	'bool': ('bool', 'bool', [('v', 'IBool')]),
	'range': ('range', 'intiter', [
		('start', 'int'), ('stop', 'int'), ('step', 'int')]
	),
	'open': ('fopen', 'file', [('fn', 'str')]),
	'strtoi': ('strtoi', 'int', [('s', 'str')]),
}

class Base(object):
	
	def __repr__(self):
		
		name = self.__class__.__name__
		type = ''
		if hasattr(self, 'type'):
			typename = repr(self.type)[7:-1]
			type = ('[%s]' % typename) if hasattr(self, 'type') else ''
		
		fields = self.__dict__.items()
		fields = ['%s=%r' % (k, v) for (k, v) in fields if k != 'type']
		fields = (' {%s}' % ', '.join(fields)) if fields else ''
		return '<%s%s%s>' % (name, type, fields)

class Value(Base):
	def __init__(self, type):
		self.type = type

class Constant(Value):
	def __init__(self, node=None):
		if node is None: return
		Value.__init__(self, types.get(node))
		self.value = node.val

class Function(Base):
	
	def __init__(self, name, rtype, args):
		self.name = name
		self.rtype = types.get(rtype if rtype else 'void')
		self.args = [types.get(a[1]) for a in args]
		self.anames = {a[0]: i for (i, a) in enumerate(args)}
		self.graph = None
		self.rt = False
	
	@classmethod
	def fromnode(cls, node):
		name = node.name.name
		rtype = node.rtype.name if node.rtype else None
		args = [(a.name.name, a.type) for a in node.args]
		return cls(name, rtype, args)
	
	@classmethod
	def frommethod(cls, type, node):
		
		name = type.name + '.' + node.name.name
		rtype = types.get(node.rtype.name if node.rtype else 'void')
		if name == type.name + '.__init__' and rtype != types.void():
			msg = "__init__() method return type must be 'void'"
			raise Error(node.rtype, msg)
			
		args = [(a.name.name, a.type) for a in node.args]
		assert args[0][1].name == type.name
		return cls(name, rtype, args)

class Reference(Value):
	def __init__(self, type, name):
		Value.__init__(self, type)
		self.name = name

class Argument(Value):
	def __init__(self, type, name):
		Value.__init__(self, type)
		self.name = name

class Return(Base):
	def __init__(self, value):
		self.value = value

class Call(Value):
	def __init__(self, name, type, args):
		Value.__init__(self, type)
		self.name = name
		self.args = args

class Init(Value):
	def __init__(self, type, args):
		Value.__init__(self, type)
		self.args = args

class Select(Value):
	def __init__(self, type, cond, left, right):
		Value.__init__(self, type)
		self.cond = cond
		self.left = left
		self.right = right

class Branch(Base):
	def __init__(self, cond, left, right=None):
		self.cond = cond
		self.left = left
		self.right = right

class BinOp(Value):
	def __init__(self, type, op, operands):
		Value.__init__(self, type)
		self.op = op
		self.operands = operands

class Math(BinOp):
	pass

class Compare(BinOp):
	pass

class GetAttr(Value):
	def __init__(self, type, obj, key):
		Value.__init__(self, type)
		self.obj = obj
		self.key = key

class GetItem(Value):
	def __init__(self, type, obj, key):
		Value.__init__(self, type)
		self.obj = obj
		self.key = key

class SetAttr(Base):
	def __init__(self, obj, key, value):
		self.obj = obj
		self.key = key
		self.value = value

class Assign(Base):
	def __init__(self, name, value):
		self.name = name
		self.value = value

class Block(Base):
	
	def __init__(self, id, named=None, preds=None):
		self.id = id
		self.named = named or {}
		self.preds = preds or []
		self.steps = []
	
	def __contains__(self, name):
		if name in self.named:
			return True
		for pred in self.preds:
			if name in pred:
				return True
	
	def __getitem__(self, name):
		
		if name in self.named:
			return self.named[name]
		
		for pred in self.preds:
			if name in pred:
				return pred[name]
		
		assert False
	
	def __setitem__(self, name, val):
		self.named[name] = val
	
	def push(self, inst):
		self.steps.append(inst)

class GraphBuilder(object):
	
	def __init__(self, mod, fun):
		
		self.mod = mod
		self.fun = fun
		
		args = {}
		for aname, pos in fun.anames.iteritems():
			args[aname] = Argument(fun.args[pos], name=aname)
		for cname, const in mod.const.iteritems():
			args[cname] = const
		
		self.cur = self.entry = Block(0, named=args)
		self.blocks = [self.cur]
		self.idx = 0
	
	def build(self, node):
		self.visit(node)
		return self.blocks
	
	def block(self, preds):
		id = len(self.blocks)
		new = Block(id, preds=[self.blocks[i] for i in preds])
		self.blocks.append(new)
		self.cur = new
		return new
	
	def push(self, val):
		self.cur.push(val)
	
	def boolean(self, val):
		if val.type == types.bool():
			return val
		return Call('bool', types.bool(), (val,))
	
	def visit(self, node):
		
		if hasattr(self, node.__class__.__name__):
			return getattr(self, node.__class__.__name__)(node)
		
		for k in node.fields:
			attr = getattr(node, k)
			if isinstance(attr, list):
				for v in attr:
					self.visit(v)
			else:
				self.visit(attr)
	
	# Terminals
	
	def Bool(self, node):
		return Constant(node)
	
	def Int(self, node):
		return Constant(node)
	
	def Float(self, node):
		return Constant(node)
	
	def String(self, node):
		return Constant(node)
	
	def Name(self, node):
		if node.name not in self.cur:
			raise Error(node, "undefined name '%s'" % node.name)
		val = self.cur[node.name]
		return Reference(val.type, node.name)
	
	# Boolean operators
	
	def Not(self, node):
		cond = self.boolean(self.visit(node.value))
		true = Constant()
		true.type = types.bool()
		true.value = True
		false = Constant()
		false.type = types.bool()
		false.value = False
		return Select(types.bool(), cond, false, true)
	
	def And(self, node):
		left, right = self.visit(node.left), self.visit(node.right)
		cond = self.boolean(left)
		if left.type == right.type:
			return Select(left.type, cond, right, left)
		else:
			return Select(types.bool(), cond, self.boolean(right), cond)
	
	def Or(self, node):
		left, right = self.visit(node.left), self.visit(node.right)
		cond = self.boolean(left)
		if left.type == right.type:
			return Select(left.type, cond, left, right)
		else:
			return Select(types.bool(), cond, cond, self.boolean(right))
	
	# Arithmetic operators
	
	def math(self, op, node):
		left, right = self.visit(node.left), self.visit(node.right)
		if left.type != right.type:
			bits = left.type.name, right.type.name
			raise Error(node, "unmatched types '%s', '%s'" % bits)
		return Math(left.type, op, (left, right))
	
	def Add(self, node):
		return self.math('add', node)
	
	def Sub(self, node):
		return self.math('sub', node)
	
	def Mul(self, node):
		return self.math('mul', node)
	
	def Div(self, node):
		return self.math('div', node)
	
	# Comparison operators
	
	def compare(self, op, node):
		left, right = self.visit(node.left), self.visit(node.right)
		if left.type != right.type:
			bits = left.type.name, right.type.name
			raise Error(node, "unmatched types '%s', '%s'" % bits)
		return Compare(types.bool(), op, (left, right))
	
	def Eq(self, node):
		return self.compare('eq', node)
	
	def NEq(self, node):
		return self.compare('ne', node)
	
	def LT(self, node):
		return self.compare('lt', node)
	
	# Other operators
	
	def Return(self, node):
		self.push(Return(self.visit(node.value)))
	
	def Elem(self, node):
		obj = self.visit(node.obj)
		key = self.visit(node.key)
		return GetItem(types.get(obj.type.over), obj, key)
	
	def Attrib(self, node):
		obj = self.visit(node.obj)
		attr = node.attrib.name
		type = obj.type.attribs[attr][1]
		return GetAttr(type, obj, attr)
	
	def Ternary(self, node):
		
		values = [self.visit(i) for i in node.values]
		if values[0].type != values[1].type:
			bits = values[0].type.name, values[1].type.name
			raise Error(node, "unmatched types '%s', '%s'" % bits)
		
		cond = self.boolean(self.visit(node.cond))
		return Select(values[0].type, cond, values[0], values[1])
	
	def Assign(self, node):
		
		value = self.visit(node.right)
		if isinstance(node.left, ast.Attrib):
			obj = self.visit(node.left.obj)
			attr = node.left.attrib.name
			self.push(SetAttr(obj, attr, value))
			return
		
		assert isinstance(node.left, ast.Name)
		self.cur[node.left.name] = value
		self.push(Assign(node.left.name, value))
	
	def Call(self, node):
		
		args = [self.visit(arg) for arg in node.args]
		if isinstance(node.name, ast.Attrib):
			obj = self.visit(node.name.obj)
			name = node.name.attrib.name
			fname = '%s.%s' % (obj.type.name, name)
			meta = obj.type.methods[node.name.attrib.name]
			return Call(fname, types.get(meta[1]), [obj] + args)
		
		if not isinstance(node.name, ast.Name):
			raise Error(node, 'not a function or method')
		
		elif node.name.name in self.mod.functions:
			fun = self.mod.functions[node.name.name]
			val = Call(node.name.name, fun.rtype, args)
			return val
		
		elif node.name.name in types.ALL:
			type = types.get(node.name)
			return Init(type, args)
		
		raise Error(node, 'not a function or method')
	
	# Block statements
	
	def Suite(self, node):
		for stmt in node.stmts:
			val = self.visit(stmt)
			if val is None: continue
			self.push(val)
	
	def If(self, node):
		
		need = 2 + len(node.blocks[1:]) * 2
		if not node.blocks[-1][0]:
			need -= 1
		
		prev = None
		condpreds, exitpreds = [], []
		condblocks, exiting = [], []
		for i, (cond, suite) in enumerate(node.blocks):
			
			if cond:
				cond = self.boolean(self.visit(cond))
			
			if cond and i + 1 == len(node.blocks):
				exitpreds.append(self.cur.id)
			
			if i:
				self.block(condpreds)
			
			if prev:
				self.blocks[prev[0]].push(Branch(prev[1], prev[2], self.cur.id))
			
			source = self.cur.id
			if cond:
				condpreds = [self.cur.id]
				self.block(condpreds)
			
			self.visit(suite)
			exitpreds.append(self.cur.id)
			exiting.append(self.cur)
			prev = (source, cond, self.cur.id) if cond else None
		
		self.block(exitpreds)
		for block in exiting:
			block.push(Branch(None, self.cur.id))
		
		if prev:
			self.blocks[prev[0]].push(Branch(prev[1], prev[2], self.cur.id))
	
	def While(self, node):
		
		start = self.cur
		cond = self.boolean(self.visit(node.cond))
		header = self.block([self.idx])
		body = self.block([header.id])
		self.visit(node.suite)
		exit = self.block([header.id, body.id])
		
		start.push(Branch(None, header.id))
		header.push(Branch(cond, body.id, exit.id))
		body.push(Branch(None, header.id))
	
	def For(self, node):
		
		start = self.cur
		source = self.visit(node.source)
		self.push(Assign('loop.source', source))
		header = self.block([self.idx])
		start.push(Branch(None, header.id))
		
		meta = source.type.methods['__next__']
		iter = Reference(source.type, 'loop.source')
		atypes = [iter] + [types.get(a) for a in meta[2]]
		val = Call(meta[0], types.get(meta[1]), atypes)
		header.named[node.lvar.name] = val
		header.push(Assign(self.visit(node.lvar), val))
		
		body = self.block([header.id])
		self.visit(node.suite)
		exit = self.block([header.id, body.id])
		body.push(Branch(None, header.id))
		header.push(Branch(node.lvar, body.id, exit.id))

class Module(object):
	
	def __init__(self, node):
		self.const = {}
		self.types = {}
		self.functions = {}
		self.order = []
		self.build(node)

	def build(self, node):
		
		for name, meta in LIBRARY.iteritems():
			self.functions[name] = Function(*meta)
			self.functions[name].rt = True
		
		bodies = {}
		for n in node.suite:
			if isinstance(n, ast.Assign):
				self.const[n.left.name] = Constant(n.right)
				self.order.append(('const', n.left.name))
			elif isinstance(n, ast.Function):
				self.functions[n.name.name] = Function.fromnode(n)
				bodies[n.name.name] = n.suite
				self.order.append(('fun', n.name.name))
			elif isinstance(n, ast.Class):
				t = self.types[n.name.name] = types.add(n)
				self.order.append(('class', n.name.name))
				for m in n.methods:
					method = Function.frommethod(t, m)
					self.functions[method.name] = method
					bodies[method.name] = m.suite
					self.order.append(('fun', method.name))
		
		for name, fun in self.functions.iteritems():
			if fun.rt: continue
			builder = GraphBuilder(self, fun)
			fun.graph = builder.build(bodies[name])
