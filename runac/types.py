'''Functionality for the Runa type system.

The core types are outlined in this file:

- void
- bool, byte
- i8, u8, i32, u32, int, uint, float
- function
- iter
- tuple (as a `build_tuple()` constructor)
- owner, ref, opt

Actual implementations attached to these types are mostly contained in the
core library. Additionally, helpers are provided for template types and their
concrete variants; these are used for traits and generics support.
'''

from . import ast, util
import copy, platform

WORD_SIZE = int(platform.architecture()[0][:2])

BASIC = {
	'bool': 'i1',
	'byte': 'i8',
	'i8': 'i8',
	'u8': 'i8',
	'i32': 'i32',
	'u32': 'i32',
	'u64': 'i64',
	'int': 'i%i' % WORD_SIZE,
	'uint': 'i%i' % WORD_SIZE,
	'float': 'double',
}

INTEGERS = {
	'i8': (True, 8),
	'u8': (False, 8),
	'i32': (True, 32),
	'u32': (False, 32),
	'u64': (False, 64),
	'int': (True, WORD_SIZE),
	'uint': (False, WORD_SIZE),
}

BASIC_FLOATS = {'float': 64}

class Type(object):
	def __eq__(self, other):
		return self.__class__ == other.__class__

class FunctionDef(util.AttribRepr):
	def __init__(self, decl, type):
		self.decl = decl
		self.type = type
		self.name = decl # might be overridden by the Module

class ReprId(object):
	
	def __hash__(self):
		return hash(repr(self))
	
	def __eq__(self, other):
		return repr(self) == repr(other)
	
	def __ne__(self, other):
		return not self.__eq__(other)
	
	def select(self, node, name, actual):
		
		if name not in self.methods:
			msg = "%s does not have a method '%s'"
			if node.args:
				t = node.args[0].type.name
			elif isinstance(node.name.type, Type):
				t = node.name.name
			else:
				assert False, node
			raise util.Error(node, msg % (t, name))
		
		opts = copy.copy(self.methods[name])
		if name == '__init__' and '__new__' in self.methods:
			opts += self.methods['__new__']
		
		res = []
		formals = []
		for fun in opts:

			formals.append([t.name for t in fun.type.over[1]][1:])
			tmp = actual
			if '__init__' in fun.decl:
				tmp = [ref(self)] + actual
			
			if len(fun.type.over[1]) != len(tmp):
				continue
			
			score = 0
			for at, ft in zip(tmp, fun.type.over[1]):
				if not compat(at, ft):
					score -= 1000
					break
				elif at == ft:
					score += 10
				else:
					score += 1
			
			if score > 0:
				res.append(fun)
		
		if not res:
			astr = ', '.join([t.name for t in actual][1:])
			bits = astr, '), ('.join(', '.join(f) for f in formals)
			msg = '(%s) does not fit any of (%s)'
			raise util.Error(node, msg % bits)
		
		assert len(res) == 1, res
		return res[0]

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
	attribs = {}
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
	attribs = {}
	methods = {}

class template(ReprId):
	
	byval = False
	attribs = {}
	methods = {}
	type = Type()
	
	@property
	def name(self):
		return self.__class__.__name__
	
	@property
	def ir(self):
		assert False, 'not a concrete type'
	
	def __repr__(self):
		return '<template: %s>' % self.__class__.__name__

class iter(template):
	params = 'T',
	attribs = {}
	methods = {}

class void(base):
	ir = 'void'
	attribs = {}
	methods = {}
	byval = True

class anyint(base):
	
	attribs = {}
	methods = {}
	
	@property
	def ir(self):
		assert False, 'not a concrete type'

class anyfloat(base):
	
	attribs = {}
	methods = {}
	
	@property
	def ir(self):
		assert False, 'not a concrete type'

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

class opt(base):
	
	def __init__(self, over):
		self.over = over
	
	@property
	def name(self):
		return '%s?' % self.over.name
	
	@property
	def ir(self):
		return self.over.ir
	
	def __repr__(self):
		return '<type: %s?>' % (self.over.name)

SINTS = {anyint()}
UINTS = set()
INTS = {anyint()}
FLOATS = {anyfloat()}
WRAPPERS = owner, ref

class function(base):
	
	def __init__(self, rtype, formal):
		self.over = rtype, formal
		self.args = None
	
	def __repr__(self):
		if not self.over[1] or isinstance(self.over[1][0], tuple):
			formal = ['%r' % i[1] for i in self.over[1]]
		else:
			formal = ['%r' % i for i in self.over[1]]
		return '<fun %r <- [%s]>' % (self.over[0], ', '.join(formal))
	
	@property
	def ir(self):
		args = ', '.join(a.ir for a in self.over[1])
		return '%s (%s)*' % (self.over[0].ir, args)

def unwrap(t):
	while isinstance(t, WRAPPERS):
		t = t.over
	return t

def generic(t):
	return isinstance(unwrap(t), (anyint, anyfloat))

def wrangle(s):
	s = s.replace('&', 'R')
	s = s.replace('$', 'O')
	s = s.replace('[', 'BT')
	s = s.replace(']', 'ET')
	return s

def compat(a, f, strict=False):
	
	if isinstance(a, concrete) and isinstance(f, concrete):
		return all(compat(i[0], i[1], True) for i in zip(a.params, f.params))
	
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
	elif isinstance(f, opt) and not isinstance(a, opt):
		return compat(a, f.over)
	elif not strict and (isinstance(a, WRAPPERS) or isinstance(f, WRAPPERS)):
		return compat(unwrap(a), unwrap(f))
	elif strict and (isinstance(a, WRAPPERS) and isinstance(f, WRAPPERS)):
		return compat(unwrap(a), unwrap(f))
	elif a in UINTS and f in UINTS:
		return a.bits < f.bits
	elif isinstance(f, trait):
		
		for k, malts in util.items(f.methods):
			
			if k not in a.methods:
				return False
			
			art = a.methods[k][0].type.over[0]
			frt = malts[0].type.over[0]
			rc = compat(art, frt)
			if not rc:
				return False
			
			tmalts = set()
			for fun in malts:
				tmalts.add(tuple(at for at in fun.type.over[1][1:]))
			
			amalts = set()
			for fun in a.methods[k]:
				amalts.add(tuple(at for at in fun.type.over[1][1:]))
			
			if tmalts != amalts:
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

class TypeMap(object):
	
	def __init__(self):
		self.map = {
			'void': void,
			'anyint': anyint,
			'anyfloat': anyfloat,
			'iter': iter,
		}
	
	def __contains__(self, key):
		return key in self.map
	
	def __getitem__(self, key):
		return self.map[key]
	
	def __setitem__(self, key, val):
		self.map[key] = val
	
	def get(self, t, stubs={}):
		if t is None:
			return void()
		elif t == '...':
			return VarArgs()
		elif isinstance(t, base):
			return t
		elif isinstance(t, str) and t[0] == '$':
			return owner(self.get(t[1:], stubs))
		elif isinstance(t, str) and t[0] == '&':
			return ref(self.get(t[1:], stubs))
		elif isinstance(t, str) and '[' in t:
			ext = t.partition('[')
			assert ext[2][-1] == ']'
			return self.apply(self.get(ext[0]), self.get(ext[2][:-1]))
		elif isinstance(t, str):
			return stubs[t] if t in stubs else self[t]()
		elif isinstance(t, ast.Name):
			if t.name in stubs:
				return stubs[t.name]
			if t.name not in self:
				raise util.Error(t, "type '%s' not found" % t.name)
			return self[t.name]()
		elif isinstance(t, ast.Elem):
			if isinstance(self.get(t.obj.name, stubs), template):
				if t.key.name in stubs:
					return self.get(t.obj.name, stubs)
			return self.apply(self[t.obj.name](), self.get(t.key, stubs))
		elif isinstance(t, ast.Owner):
			return owner(self.get(t.value, stubs))
		elif isinstance(t, ast.Ref):
			return ref(self.get(t.value, stubs))
		elif isinstance(t, ast.Opt):
			return opt(self.get(t.value, stubs))
		elif isinstance(t, ast.Tuple):
			return self.build_tuple(tuple(self.get(v) for v in t.values))
		else:
			assert False, 'no type %s' % t
	
	def add(self, node):
		
		if isinstance(node, ast.Trait):
			parent = trait
		elif node.params:
			parent = template
		else:
			parent = base
		
		if isinstance(node, ast.Trait):
			fields = {'methods': {}}
		elif node.params:
			fields = {'methods': {}, 'attribs': {}, 'params': {}}
		else:
			fields = {'methods': {}, 'attribs': {}}
		
		if node.name.name in BASIC:
			fields['ir'] = BASIC[node.name.name]
			fields['byval'] = True
		
		self[node.name.name] = type(node.name.name, (parent,), fields)
	
	def fill(self, node):
		
		cls = self[node.name.name]
		stubs = {}
		if not isinstance(node, ast.Trait):
			cls.params = tuple(n.name for n in node.params)
			stubs = {n.name: Stub(n.name) for n in node.params}
			for i, (atype, name) in enumerate(node.attribs):
				cls.attribs[name.name] = i, self.get(atype, stubs)
		
		for method in node.methods:
			
			name = method.name.name
			rtype = void()
			if method.rtype is not None:
				rtype = self.get(method.rtype, stubs)
			
			args = []
			for i, arg in enumerate(method.args):
				if not i and arg.name.name == 'self':
					wrapper = owner if name == '__del__' else ref
					args.append(('self', wrapper(self.get(node.name, stubs))))
				else:
					args.append((arg.name.name, self.get(arg.type, stubs)))
			
			irname = '%s.%s' % (node.name.name, name)
			if name in cls.methods:
				irname = irname + '$' + '.'.join(wrangle(a[1].name) for a in args)
				assert rtype == cls.methods[name][0].type.over[0]
			
			fun = FunctionDef(irname, function(rtype, tuple(a[1] for a in args)))
			fun.type.args = [a[0] for a in args]
			cls.methods.setdefault(name, []).append(fun)
			method.irname = irname
		
		obj = cls()
		if node.name.name in INTEGERS:
			
			cls.signed, cls.bits = INTEGERS[node.name.name]
			INTS.add(obj)
			if cls.signed:
				SINTS.add(obj)
			else:
				UINTS.add(obj)
			
			self['anyint'].methods.update(cls.methods)
		
		elif node.name.name in BASIC_FLOATS:
			cls.bits = BASIC_FLOATS[node.name.name]
			FLOATS.add(obj)
			self['anyfloat'].methods.update(cls.methods)
		
		return obj
	
	def realize(self, n):
		if isinstance(n, ast.Decl):
			rtype = self.get(n.rtype)
			atypes = [self.get(a.type) for a in n.args]
			return FunctionDef(n.name.name, function(rtype, atypes))
		else:
			rtype = self.get(n.rtype)
			atypes = [self.get(t) for t in n.atypes]
			return FunctionDef(n.decl, function(rtype, atypes))
	
	def build_tuple(self, params):
		
		params = tuple(params)
		name = 'tuple[%s]' % ', '.join(p.name for p in params)
		internal = name.replace('%', '_').replace('.', '_')
		cls = self[('tuple', params)] = type(internal, (concrete,), {
			'ir': '%tuple$' + '.'.join(wrangle(t.name) for t in params),
			'name': name,
			'params': params,
			'methods': {'v%i' % i: (i, t) for (i, t) in enumerate(params)},
			'attribs': {},
		})
		
		return cls()
	
	def apply(self, tpl, params):
		
		params = params if isinstance(params, tuple) else (params,)
		name = '%s[%s]' % (tpl.name, ', '.join(p.name for p in params))
		internal = name.replace('$', '_').replace('.', '_')
		cls = self[(tpl.name, params)] = type(internal, (concrete,), {
			'ir': '%' + tpl.name + '$' + '.'.join(t.name for t in params),
			'name': name,
			'params': params,
			'methods': {},
			'attribs': {},
		})
		
		trans = {k: v for (k, v) in zip(tpl.params, params)}
		for k, v in util.items(tpl.attribs):
			if isinstance(v[1], Stub):
				cls.attribs[k] = v[0], trans[v[1].name]
			elif isinstance(v[1], WRAPPERS) and isinstance(v[1].over, Stub):
				cls.attribs[k] = v[0], v[1].__class__(trans[v[1].over.name])
			else:
				cls.attribs[k] = v[0], v[1]
		
		for k, mtypes in util.items(tpl.methods):
			for method in mtypes:
				
				rtype = method.type.over[0]
				if rtype == tpl:
					rtype = cls()
				
				formal = method.type.over[1]
				formal = (ref(cls()),) + formal[1:]
				t = function(rtype, formal)
				
				pmd = tpl.name + '$' + '.'.join(t.name for t in params)
				decl = method.decl.replace(tpl.name, pmd)
				cls.methods.setdefault(k, []).append(FunctionDef(decl, t))
		
		return cls()
