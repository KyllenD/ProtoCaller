ProtoCaller
===========

About
-----

ProtoCaller is a Python library which enables controlled automation of relative protein-ligand binding free energy
calculations in GROMACS. ProtoCaller uses a variety of tools to automate the free energy calculation process,
such as: Biopython, BioSimSpace, CHARMM-GUI, (optionally) Modeller, Open Babel, ParmEd, PDB2PQR, pdbfixer, RDKit.

ProtoCaller can be run on both Linux and macOS. Installation is easy and performed through Conda. Please check the
other sections for further information.


Installation
------------

This package is distributed via Conda. To install it, run the following command:

.. code-block:: bash

    conda install -c conda-forge -c omnia -c michellab -c kdilsook protocaller

The newest version (1.2.0) is highly recommended due to recent database overhauls in the Protein Data Bank.


Getting Started
---------------

Full docstring documentation can be found `here <https://protocaller.readthedocs.io/en/latest/ProtoCaller.html>`_.
There are also a few `examples <https://protocaller.readthedocs.io/en/latest/Examples.html>`_ which you can run to
see how ProtoCaller works.
