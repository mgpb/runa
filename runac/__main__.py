#!/usr/bin/env python

from __future__ import print_function
import optparse, sys, os
from runac import util
import runac

def tokens(fn, opts):
	'''Print a list of tokens and location info'''
	with open(fn) as f:
		for x in runac.lex(f.read()):
			print(x.name, x.value, (x.source_pos.lineno, x.source_pos.colno))

def parse(fn, opts):
	'''Print the syntax tree resulting from parsing the source'''
	print(runac.parse(fn))

def show(fn, opts):
	'''Print syntax tree after processing the pass specified by --last'''
	for cfg in runac.show(fn, opts.last):
		print(cfg)

def generate(fn, opts):
	'''Print LLVM IR as generated by the code generation process'''
	ir = runac.ir(fn)
	if not opts.test:
		print(ir)

def compile(fn, opts):
	'''Compile the given program to a binary of the same name'''
	ir = runac.ir(fn)
	runac.compile(ir, os.path.basename(fn).rsplit('.rns')[0])

COMMANDS = {
	'tokens': tokens,
	'parse': parse,
	'show': show,
	'generate': generate,
	'compile': compile,
}

def find(cmd):
	if cmd in COMMANDS: return COMMANDS[cmd]
	matched = sorted(i for i in COMMANDS if i.startswith(cmd))
	if len(matched) == 1:
		return COMMANDS[matched[0]]
	elif len(matched) > 1:
		print('ambiguous command: %r' % cmd)
		return lambda x, y: None
	else:
		print('no command found: %r' % cmd)
		return lambda x, y: None

if __name__ == '__main__':
	
	parser = optparse.OptionParser()
	
	parser.add_option('--last', help='last pass', default='destruct')
	parser.add_option('--test', help='no output', action='store_true')
	parser.add_option('--traceback', help='show full traceback',
	                  action='store_true')
	opts, args = parser.parse_args()
	
	if len(args) < 1:
		print('The Runa compiler. A command takes a single file as an argument.')
		print('\nCommands:\n')
		for cmd, fun in sorted(COMMANDS.items()):
			print('%s: %s' % (cmd, fun.__doc__))
		print('\nAny unique command abbrevation will also work.')
		parser.print_help()
		sys.exit(1)
	
	try:
		find(args[0])(args[1], opts)
	except util.Error as e:
		if opts.traceback:
			raise
		sys.stderr.write(e.show())
	except util.ParseError as e:
		if opts.traceback:
			raise
		sys.stderr.write(e.show())
