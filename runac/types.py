import ast

class Type(object):
	def __eq__(self, other):
		return self.__class__ == other.__class__

class ReprId(object):
	
	def __hash__(self):
		return hash(repr(self))
	
	def __eq__(self, other):
		return repr(self) == repr(other)
	
	def __ne__(self, other):
		return not self.__eq__(other)

class base(ReprId):
	
	byval = False
	attribs = {}
	methods = {}
	type = Type()
	
	@property
	def name(self):
		return self.__class__.__name__
	
	@property
	def ir(self):
		return '%' + self.name
	
	def __repr__(self):
		return '<type: %s>' % self.__class__.__name__

class trait(ReprId):
	
	byval = False
	methods = {}
	type = Type()
	
	@property
	def name(self):
		return self.__class__.__name__
	
	@property
	def ir(self):
		return '%%%s.wrap' % self.name
	
	def __repr__(self):
		return '<trait: %s>' % self.name

class concrete(base):
	pass

class template(base):
	
	@property
	def ir(self):
		raise TypeError('not a concrete type')
	
	def __repr__(self):
		return '<template: %s>' % self.__class__.__name__
	
	def __getitem__(self, params):
		
		params = params if isinstance(params, tuple) else (params,)
		name = '%s[%s]' % (self.name, ', '.join(p.name for p in params))
		internal = name.replace('$', '_').replace('.', '_')
		cls = ALL[(self.name, params)] = type(internal, (concrete,), {
			'ir': '%' + self.name + '$' + '.'.join(t.name for t in params),
			'name': name,
			'methods': {},
			'attribs': {},
		})
		
		trans = {k: v for (k, v) in zip(self.params, params)}
		for k, v in self.attribs.iteritems():
			if isinstance(v[1], Stub):
				cls.attribs[k] = v[0], trans[v[1].name]
			elif isinstance(v[1], WRAPPERS) and isinstance(v[1].over, Stub):
				cls.attribs[k] = v[0], v[1].__class__(trans[v[1].over.name])
			else:
				cls.attribs[k] = v[0], v[1]
		
		return cls()

class void(base):
	ir = 'void'
	byval = True

class anyint(base):
	@property
	def ir(self):
		raise TypeError('not a concrete type')

class anyfloat(base):
	@property
	def ir(self):
		raise TypeError('not a concrete type')

BASIC = {
	'bool': 'i1',
	'byte': 'i8',
	'i32': 'i32',
	'u32': 'i32',
	'int': 'i64',
	'uint': 'i64',
}

INTEGERS = {
	'byte': (False, 8),
	'i32': (True, 32),
	'u32': (False, 32),
	'int': (True, 64),
	'uint': (False, 64),
}

class module(base):
	def __init__(self, path=None):
		self.path = path
		self.functions = {}

class owner(base):
	
	def __init__(self, over):
		self.over = over
	
	@property
	def name(self):
		return '$%s' % self.over.name
	
	@property
	def ir(self):
		return self.over.ir + '*'
	
	def __repr__(self):
		return '<type: $%s>' % (self.over.name)

class ref(base):
	
	def __init__(self, over):
		self.over = over
	
	@property
	def name(self):
		return '&%s' % self.over.name
	
	@property
	def ir(self):
		return self.over.ir + '*'
	
	def __repr__(self):
		return '<type: &%s>' % (self.over.name)

class function(base):
	
	def __init__(self, rtype, formal):
		self.over = rtype, formal
	
	def __repr__(self):
		if not self.over[1] or isinstance(self.over[1][0], tuple):
			formal = ['%r' % i[1] for i in self.over[1]]
		else:
			formal = ['%r' % i for i in self.over[1]]
		return '<fun %r <- [%s]>' % (self.over[0], ', '.join(formal))
	
	@property
	def ir(self):
		raise NotImplementedError

def unwrap(t):
	while isinstance(t, WRAPPERS):
		t = t.over
	return t

def generic(t):
	return isinstance(unwrap(t), (anyint, anyfloat))

def compat(a, f):
	
	if isinstance(a, (tuple, list)) and isinstance(f, (tuple, list)):
		if len(a) != len(f):
			return False
		if f and f[-1] == VarArgs():
			return all(compat(i[0], i[1]) for i in zip(a, f[:-1]))
		return all(compat(i[0], i[1]) for i in zip(a, f))
	
	if a == f:
		return True
	elif isinstance(a, anyint) and f in INTS:
		return True
	elif isinstance(a, ref) and isinstance(f, owner):
		return False
	elif isinstance(a, WRAPPERS) or isinstance(f, WRAPPERS):
		return compat(unwrap(a), unwrap(f))
	elif a in UINTS and f in UINTS:
		return a.bits < f.bits
	elif isinstance(f, trait):
		
		for k, (x, rt, atypes) in f.methods.iteritems():
			
			if k not in a.methods:
				return False
			
			rc = compat(a.methods[k][1], rt)
			aargs = [i[1] for i in a.methods[k][2][1:]]
			fargs = [i[1] for i in atypes[1:]]
			ac = compat(aargs, fargs)
			if not rc or not ac:
				return False
		
		return True
		
	else:
		return False

class Stub(object):
	def __init__(self, name):
		self.name = name
	def __repr__(self):
		return '<%s(%r)>' % (self.__class__.__name__, self.name)

class VarArgs(base):
	@property
	def ir(self):
		return '...'

def get(t, stubs={}):
	if t is None:
		return void()
	elif t == '...':
		return VarArgs()
	elif isinstance(t, base):
		return t
	elif isinstance(t, basestring) and t[0] == '$':
		return owner(get(t[1:], stubs))
	elif isinstance(t, basestring) and t[0] == '&':
		return ref(get(t[1:], stubs))
	elif isinstance(t, basestring):
		return stubs[t] if t in stubs else ALL[t]()
	elif isinstance(t, ast.Name):
		return stubs[t.name] if t.name in stubs else ALL[t.name]()
	elif isinstance(t, ast.Elem):
		return ALL[t.obj.name](get(t.key, stubs))
	elif isinstance(t, ast.Owner):
		return owner(get(t.value, stubs))
	elif isinstance(t, ast.Ref):
		return ref(get(t.value, stubs))
	else:
		assert False, 'no type %s' % t

ALL = {}
for k in globals().keys():
	obj = globals()[k]
	if type(obj) == type and base in obj.__bases__:
		ALL[k] = globals()[k]

for k, cls in ALL.iteritems():
	for m, mdata in cls.methods.iteritems():
		rtype = get(mdata[1])
		atypes = [(n, get(t)) for (n, t) in mdata[2]]
		cls.methods[m] = (m[0], rtype, atypes)

SINTS = {anyint()}
UINTS = set()
INTS = set()
FLOATS = {anyfloat()}
WRAPPERS = owner, ref

def add(node):
	
	if isinstance(node, ast.Trait):
		parent = trait
	elif node.params:
		parent = template
	else:
		parent = base
	
	if isinstance(node, ast.Trait):
		fields = {'methods': {}}
	else:
		fields = {'methods': {}, 'attribs': {}}
	
	ALL[node.name.name] = type(node.name.name, (parent,), fields)

def fill(node):
	
	cls = ALL[node.name.name]
	if node.name.name in BASIC:
		cls.ir = BASIC[node.name.name]
		cls.byval = True
	
	stubs = {}
	if not isinstance(node, ast.Trait):
		cls.params = tuple(n.name for n in node.params)
		stubs = {n.name: Stub(n.name) for n in node.params}
		for i, (atype, name) in enumerate(node.attribs):
			cls.attribs[name.name] = i, get(atype, stubs)
	
	for method in node.methods:
		
		name = method.name.name
		irname = '%s.%s' % (node.name.name, name)
		rtype = void() if method.rtype is None else get(method.rtype, stubs)
		
		args = []
		for i, arg in enumerate(method.args):
			if not i and arg.name.name == 'self':
				wrapper = owner if name == '__del__' else ref
				args.append(('self', wrapper(get(node.name, stubs))))
			else:
				args.append((arg.name.name, get(arg.type, stubs)))
		
		cls.methods[name] = irname, rtype, args
		method.irname = irname
	
	obj = cls()
	if node.name.name in INTEGERS:
		
		cls.signed, cls.bits = INTEGERS[node.name.name]
		INTS.add(obj)
		if cls.signed:
			SINTS.add(obj)
		else:
			UINTS.add(obj)
		
		ALL['anyint'].methods.update(cls.methods)
	
	return obj
