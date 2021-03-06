********************
Hacking the compiler
********************

Here are some pointers if you want to read some source code.
The compiler driver is in ``runac/__main__.py``:
it's a small script implementing a few useful commands.
The code actually driving the compiler is in ``runac/__init__.py``.
Here you can see the lexer, parser, transformation passes, codegen,
and compilation of LLVM IR to machine code being done.
The general structure is like this:

1. Parser phase (includes lexing and parsing), in ``runac/parser.py``
2. :ref:`blocks`, in ``runac/blocks.py``
3. Transformation passes:
   
   a. :ref:`liveness`, in ``runac/liveness.py``
   b. :ref:`typer`, in ``runac/typer.py``
   c. :ref:`specialize`, in ``runac/specialize.py``
   d. :ref:`escapes`, in ``runac/escapes.py``
   e. :ref:`destructor`, in ``runac/destructor.py``
   
4. :ref:`codegen`, in ``runac/codegen.py``

The parser, which is based on rply, returns an AST (node classes in
``runac/ast.py``). This gets processed by the AST walker in
``runac/blocks.py`` to get to a control flow graph with shallow basic blocks:
all expressions are flattened into a single statement, with assignment to
temporary variables, and all control flow is structured as a graph, with
relevant AST nodes at the top of this file.

The resulting tree is then passed through a number of transformation passes.
Currently, the ``liveness`` pass determines variable liveness, the ``typer``
pass performs type inference, the ``specialize`` pass improves on the
inferenced types, the ``escapes`` pass performs an escape analysis, and the
``destruct`` pass inserts code to clean up heap-allocated objects.

The transformed tree is then passed to the AST walker in ``runac/codegen.py``,
where LLVM IR is generated. This can then be passed into ``clang``.

A regression test suite is implemented in the ``tests/`` dir, where each
source file (``rns`` extension) represents a single test case. Execute the
entire suite by executing ``make test`` in the root directory.


.. _blocks:

AST to CFG transformation
=========================

.. automodule:: runac.blocks


.. _liveness:

Liveness analysis
=================

.. automodule:: runac.liveness


.. _typer:

Type inference and type checking
================================

.. automodule:: runac.typer


.. _specialize:

Type specialization
===================

.. automodule:: runac.specialize


.. _escapes:

Escape analysis
===============

.. automodule:: runac.escapes


.. _destructor:

Destructor insertion
====================

.. automodule:: runac.destructor


.. _codegen:

Code generation
===============

.. automodule:: runac.codegen
