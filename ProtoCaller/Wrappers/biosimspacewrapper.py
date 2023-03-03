import ProtoCaller as _PC
if not _PC.BIOSIMSPACE:
    raise ImportError("BioSimSpace module cannot be imported")

from collections.abc import Iterable as _Iterable
import copy as _copy
import re as _re
import warnings as _warnings

import BioSimSpace as _BSS
import Sire.MM as _SireMM
import Sire.Maths as _SireMaths
import Sire.Mol as _SireMol
import Sire.Vol as _SireVol


def centre(system, box_length):
    """
    Centres the system given a box length.

    Parameters
    ----------
    system : BioSimSpace.System
        The input system to be centred.
    box_length : float, iterable
        Length of the box in nm.

    Returns
    -------
    system : BioSimspace.System
        The centred BioSimSpace system.
    box_length : tuple
        The new box length. Only different from the input value if the box is too small for the system.
    translation_vec: Sire.Maths.vector
        The centering translation vector.
    """
    if not isinstance(box_length, _Iterable):
        cubic = True
        box_length = 3 * [box_length]
    else:
        cubic = (len(set(box_length)) == 1)

    box = system._getAABox()
    min_coords, max_coords = box.minCoords(), box.maxCoords()
    centre = (min_coords + max_coords) / 2
    difference = max_coords - min_coords

    box_length_new = []
    for x, y in zip(difference, box_length):
        box_length_new += [y] if x < 10 * y else [x / 10 + 1]
    if cubic:
        box_length_new = 3 * [max(box_length_new)]
    if box_length_new != box_length:
        _warnings.warn("Insufficient input box size. Changing to a box size of ({:.3f}, {:.3f}, {:.3f}) nm...".format(
            *box_length_new))

    translation_vec = -centre + _SireMaths.Vector([5 * x for x in box_length_new])
    system.translate(tuple(translation_vec))
    system = resize(system, box_length_new)

    return system, tuple(box_length_new), translation_vec


def resize(system, box_length):
    """
    Changes the box size of the system or adds one if there is no box.

    Parameters
    ----------
    system : BioSimSpace.System
        The input system to be resized.
    box_length : float, iterable
        Length of the box in nm.

    Returns
    -------
    system : BioSimSpace.System
        The resized system.
    """
    if not isinstance(box_length, _Iterable):
        box_length = 3 * [box_length]
    box_length = tuple([10 * x for x in box_length])
    system._sire_object.setProperty("space", _SireVol.PeriodicBox(_SireMaths.Vector(box_length)))
    return system


def rescaleSystemParams(system, scale, includelist=None, excludelist=None, neutralise=True):
    """
    Rescales charge, Lennard-Jones and dihedral parameters for REST(2).

    Parameters
    ----------
    system : BioSimSpace.System
        Input system to be rescaled.
    scale : float
        Multiplication factor for the charge, Lennard-Jones and dihedral parameters. 0 < scale < 1.
    includelist : [str]
        Molecule names to be included in the rescaling. Default: None.
    excludelist : [str]
        Molecule names to be excluded in the rescaling. Default: ["WAT"].
    neutralise : bool
        Whether to rescale a minimum number of Na+ or Cl- ions so that the rescaled part of the system is neutralised.

    Returns
    -------
    system_new : BioSimSpace.System
        The rescaled system.
    """
    if excludelist is None and includelist is None:
        excludelist = ["WAT"]
    elif excludelist is not None and includelist is not None:
        raise ValueError("Only one of includelist and excludelist can be set")

    if neutralise:
        if excludelist is not None:
            total_charge = round(sum([mol.charge().magnitude() for mol in system.getMolecules()
                                      if mol._sire_object.name().value() not in excludelist]))
        elif includelist is not None:
            total_charge = round(sum([mol.charge().magnitude() for mol in system.getMolecules()
                                      if mol._sire_object.name().value() in includelist]))

    mols_mod = []

    for mol in system.getMolecules():
        if neutralise and mol._sire_object.name().value().lower() == "na" and total_charge < 0:
            total_charge += 1
        elif neutralise and mol._sire_object.name().value().lower() == "cl" and total_charge > 0:
            total_charge -= 1
        elif excludelist is not None:
            if mol._sire_object.name().value() in excludelist:
                mols_mod += [mol]
                continue
        elif includelist is not None:
            if mol._sire_object.name().value() not in includelist:
                mols_mod += [mol]
                continue

        mol_edit = mol._sire_object.edit()

        if scale != 1:
            for prop in ["dihedral", "dihedral0", "dihedral1", "improper", "improper0", "improper1"]:
                try:
                    potentials = mol_edit.property(prop).potentials()
                    prop_new = _SireMM.FourAtomFunctions(mol_edit.info())
                    for potential in potentials:
                        prop_new.set(potential.atom0(), potential.atom1(), potential.atom2(), potential.atom3(),
                                     potential.function() * scale)
                    mol_edit = mol_edit.setProperty(prop, prop_new).molecule()
                except:
                    continue

        for atom in mol_edit.atoms():
            idx = atom.index()

            for prop in ["atomtype", "atomtype0", "atomtype1"]:
                try:
                    atomtype_new = atom.property(prop) + "_"
                    mol_edit = mol_edit.atom(idx).setProperty(prop, atomtype_new).molecule()
                except:
                    continue

            if scale != 1:
                for prop in ["LJ", "LJ0", "LJ1"]:
                    try:
                        LJ = atom.property(prop)
                        LJ = LJ.fromSigmaAndEpsilon(LJ.sigma(), LJ.epsilon() * scale)
                        mol_edit = mol_edit.atom(idx).setProperty(prop, LJ).molecule()
                    except:
                        continue

                for prop in ["charge", "charge0", "charge1"]:
                    try:
                        charge = atom.property(prop)
                        charge = charge * scale
                        mol_edit = mol_edit.atom(idx).setProperty(prop, charge).molecule()
                    except:
                        continue

        if mol._sire_object.name().value().lower() in ["na", "cl"]:
            resname = mol_edit.residue().name()
            resname_new = _SireMol.ResName(resname.value() + "_")
            mol_edit = mol_edit.residue(resname).rename(resname_new)

        mol._sire_object = mol_edit.commit()
        mols_mod += [mol]

    system_new = _BSS._SireWrappers._system.System(mols_mod)
    box = system._sire_object.property("space")
    system_new._sire_object.setProperty("space", box)

    return system_new


def rescaleBondedDummies(system, scale, bonds=None):
    """
    Rescales bonds which are connected to the dummy atoms

    Parameters
    ----------
    system : BioSimSpace.System
        Input system to be modified.
    scale : float
        Multiplication factor for the bond length. 0.5 < scale < 1 for best
        performance. If scale is too low, the user might encounter numerical
        stability problems in the simulation.
    bonds : {str: [(int, int)]}
        A dictionary which contains all of the bonds to be rescaled. Its keys
        contain the name of the molecule, and the values are lists of tuples
        which contain the bond indices to be rescaled. Default: all dummy bonds
        in the system are rescaled.

    Returns
    -------
    system_new : BioSimSpace.System
        The rescaled system.
    """
    if scale == 1:
        return system

    mols_mod = []

    for mol in system.getMolecules():
        mol_name = mol._sire_object.name().value()
        if bonds is not None and (mol_name not in bonds.keys() or not bonds[mol_name]):
            mols_mod += [mol]
            continue
        if bonds is None:
            bonds_to_incl = None
        else:
            bonds_to_incl = {frozenset(x) for x in bonds[mol_name]}

        mol_edit = mol._sire_object.edit()

        dummies0 = []
        dummies1 = []

        for atom in mol_edit.atoms():
            pat = r"AtomIdx\((\d*)\)"
            if "dummy" in atom.property("element0").toString():
                dummies0 += [int(*_re.search(pat, atom.index().toString()).groups())]
            elif "dummy" in atom.property("element1").toString():
                dummies1 += [int(*_re.search(pat, atom.index().toString()).groups())]

        for prop, dummies in zip(["bond0", "bond1"], [dummies0, dummies1]):
            potentials = mol_edit.property(prop).potentials()
            prop_new = _copy.copy(mol_edit.property(prop))
            for potential in potentials:
                pat = r"Index\((\d*)\)"
                at0_idx = int(*_re.search(pat, potential.atom0().toString()).groups())
                at1_idx = int(*_re.search(pat, potential.atom1().toString()).groups())
                bond_key = {at0_idx, at1_idx}

                # we ignore bonds that are not specified by the user
                if bonds_to_incl is not None and bond_key not in bonds_to_incl:
                    continue

                # we ignore non-dummy bonds
                if not at0_idx in dummies and not at1_idx in dummies:
                    continue

                func = potential.function()
                func_str = func.toString()
                pat = r"(\S*)\s*\[r - (\S*)\]"
                k, r_eq = [float(x) for x in _re.match(pat, func_str).groups()]

                # here we scale the r_eq
                # this is a bit of a hack since it is difficult to instantiate
                # Sire CAS from python
                func = k * ((func / k).root(2) + (1 - scale) * r_eq).squared()

                prop_new.set(potential.atom0(), potential.atom1(), func)
            mol_edit = mol_edit.setProperty(prop, prop_new).molecule()

        mol._sire_object = mol_edit.commit()
        mols_mod += [mol]

    system_new = _BSS._SireWrappers._system.System(mols_mod)
    box = system._sire_object.property("space")
    system_new._sire_object.setProperty("space", box)

    return system_new
