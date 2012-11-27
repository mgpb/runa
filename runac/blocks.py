import ast, types

class Branch(object):
	def __init__(self, target):
		self.label = target
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

class CondBranch(object):
	fields = ('cond',)
	def __init__(self, cond, tg1, tg2):
		self.cond = cond
		self.tg1 = tg1
		self.tg2 = tg2
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

class Block(object):
	
	def __init__(self, id, anno=None):
		self.id = id
		self.anno = anno
		self.steps = []
		self.assigns = set()
		self.uses = set()
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	
	def push(self, inst):
		self.steps.append(inst)
	
	def needbranch(self):
		return not isinstance(self.steps[-1], ast.Return)

class FlowGraph(object):
	
	def __init__(self):
		self.blocks = {0: Block(0, 'entry')}
		self.edges = None
		self.redges = None
		self.exits = None
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	
	def block(self, anno=None):
		id = len(self.blocks)
		self.blocks[id] = Block(id, anno)
		return self.blocks[id]
	
	def walk(self, path):
		next = self.edges.get(path[-1], [])
		if not next:
			yield path + (None,)
			return
		for n in next:
			for res in self.walk(path + (n,)):
				yield res

class FlowFinder(object):
	
	def __init__(self):
		self.flow = FlowGraph()
		self.cur = self.flow.blocks[0]
		self.tmp = 0
	
	def build(self, node):
		self.visit(node)
		return self.flow
	
	def visit(self, node):
		if hasattr(self, node.__class__.__name__):
			getattr(self, node.__class__.__name__)(node)
		else:
			self.cur.push(node)
	
	def Suite(self, node):
		for stmt in node.stmts:
			self.visit(stmt)
	
	def If(self, node):
		
		prevcond, exits = None, []
		for i, (cond, suite) in enumerate(node.blocks):
			
			if i and cond is not None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				condblock = self.flow.block('if-cond')
				prevcond.steps[-1].tg2 = condblock.id
				condblock.push(CondBranch(cond, None, None))
				prevcond = condblock
			
			block = self.flow.block('if-suite')
			if i and cond is not None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg1 = block.id
			
			if not i:
				self.cur.push(CondBranch(cond, block.id, None))
				prevcond = self.cur
			elif cond is None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg2 = block.id
				prevcond = None
			
			self.cur = block
			self.visit(suite)
			if self.cur.needbranch():
				exits.append(self.cur)
		
		exit = self.flow.block('if-exit')
		if prevcond:
			assert isinstance(prevcond.steps[-1], CondBranch)
			prevcond.steps[-1].tg2 = exit.id
		
		self.cur = exit
		for block in exits:
			block.push(Branch(exit.id))
	
	def While(self, node):
		
		assert False, 'obsolete'
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
		
		assert False, 'obsolete'
		start = self.cur
		source = self.visit(node.source)
		self.cur.push(Assign('loop.source', source))
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
	
	def __init__(self):
		self.refs = {}
		self.constants = {}
		self.types = {}
		self.code = []
		self.variants = set() # populated by type inferencing pass
		self.scope = None # populated by type inferencing pass
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	
	def merge(self, mod):
		
		for k, v in mod.refs.iteritems():
			assert k not in self.refs
			self.refs[k] = v
		
		for k, v in mod.constants.iteritems():
			assert k not in self.constants
			self.constants[k] = v
		
		for k, v in mod.types.iteritems():
			assert k not in self.types
			self.types[k] = v
		
		self.code += mod.code
	
def module(node):
	
	mod = Module()
	for n in node.suite:
		
		if isinstance(n, ast.RelImport):
			for name in n.names:
				
				if isinstance(n.base, ast.Name):
					base = n.base.name
				else:
					start = n.base
					res = []
					while isinstance(start, ast.Attrib):
						res.append(start.attrib.name)
						start = start.obj
					res.append(start.name)
					base = '.'.join(reversed(res))
					
				mod.refs[name.name] = base + '.' + name.name
		
		elif isinstance(n, ast.Class):
			mod.types[n.name.name] = n
			for m in n.methods:
				mod.code.append(((n.name.name, m.name.name), m))
		
		elif isinstance(n, ast.Function):
			mod.code.append((n.name.name, n))
		
		else:
			assert False, n
	
	for k, v in mod.code:
		
		cfg = v.flow = FlowFinder().build(v.suite)
		cfg.edges = {}
		
		for i, bl in cfg.blocks.iteritems():
			
			if not bl.steps:
				auto = ast.Return(None)
				auto.value = None
				bl.steps.append(auto)
				continue
			
			if isinstance(bl.steps[-1], Branch):
				cfg.edges.setdefault(i, []).append(bl.steps[-1].label)
			elif isinstance(bl.steps[-1], CondBranch):
				cfg.edges.setdefault(i, []).append(bl.steps[-1].tg1)
				cfg.edges.setdefault(i, []).append(bl.steps[-1].tg2)
			elif not isinstance(bl.steps[-1], ast.Return):
				auto = ast.Return(None)
				auto.value = None
				auto.pos = v.pos
				bl.steps.append(auto)
		
		cfg.exits = set()
		reachable = set()
		for p in cfg.walk((0,)):
			reachable |= set(p[:-1])
			cfg.exits.add(p[-2])
		
		for i in set(cfg.blocks) - reachable:
			del cfg.blocks[i]
		
		cfg.redges = {}
		for src, dsts in cfg.edges.iteritems():
			for dst in dsts:
				cfg.redges.setdefault(dst, []).append(src)
	
	return mod

