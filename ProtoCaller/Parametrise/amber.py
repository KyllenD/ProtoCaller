import glob as _glob
import os as _os
import warnings as _warnings

import ProtoCaller as _PC
import ProtoCaller.Wrappers.babelwrapper as _babel
import ProtoCaller.Utils.runexternal as _runexternal

__all__ = ["amberWrapper", "runAntechamber", "runParmchk", "runTleap"]


def amberWrapper(params, filename, molecule_type, id=None, charge=None, *args, **kwargs):
    """
    Parametrises an input file according to AMBER force field.

    Parameters
    ----------
    params : ProtoCaller.Parametrise.Params
        Force field parameters.
    filename : str
        Name of the input file.
    molecule_type : str
        The type of the molecule. One of: "protein", "ligand", "cofactor", "water", "simple_anion", "complex_anion",
        "simple_cation", "complex_cation".
    id : str
        The name of the molecule. Default: equal to molecule_type.
    charge : bool
        The net charge of the molecule. Default: automatic detection by antechamber.
    args
        Positional arguments to be passed to the relevant wrapper.
    kwargs
        Keyword arguments to be passed to the relevant wrapper.

    Returns
    -------
    files : [str]
        The output parametrised file(s). If there is more than one file, the first one is always the topology file and
        the second one - the coordinate file.
    """
    if id is None: id = molecule_type
    force_fields, files, param_files = [], [filename], []

    if molecule_type == "protein":
        force_fields = [params.protein_ff, params.water_ff]
    elif molecule_type in ["water", "simple_anion", "simple_cation"]:
        force_fields = [params.water_ff]
    elif molecule_type == "complex_anion":
        _warnings.warn("AMBER parametrisation failed: polyatomic anions not supported")
        return
    elif molecule_type == "complex_cation":
        _warnings.warn("AMBER parametrisation failed: transition metals not supported")
        return
    elif molecule_type == "cofactor":
        force_fields = [params.ligand_ff]
        param_files = _glob.glob("%s/shared/amber-parameters/cofactors/%s.*" % (_PC.HOMEDIR, id))
    elif molecule_type == "ligand":
        force_fields = [params.ligand_ff]
        files = [runAntechamber(params.ligand_ff, filename, charge=charge)]
        param_files = [runParmchk(params.ligand_ff, files[0])]
    else:
        raise ValueError("Value %s for molecule_type not supported " % molecule_type)

    return runTleap(force_fields=force_fields, files=files, param_files=param_files, id=id, *args, **kwargs)


def runAntechamber(force_field, file, output_ext="mol2", charge=None):
    """
    A wrapper around antechamber.

    Parameters
    ----------
    force_field : str
        Which force field to use. Only "gaff" and "gaff2" are accepted.
    file : str
        Name of input file.
    output_ext : str
        Output extension.
    charge : int
        The net charge of the molecule. Default: automatic detection by antechamber.

    Returns
    -------
    output_name : str
        Absolute path of the output parametrised file.
    """
    input_base, input_ext = _os.path.splitext(file)[0], file.split(".")[-1]
    if input_ext.lower() in ["mol", "sdf"]:
        _babel.babelTransform(file, output_extension="mol2", pH=None)
        input_ext = "mol2"

    output_name = "%s_antechamber.%s" % (input_base, output_ext)

    commandstr = "antechamber -i '%s' -fi %s -o '%s' -fo %s -c bcc -at %s -s 2" % (
        file, input_ext, output_name, output_ext, force_field)
    if charge is not None:
        commandstr += " -nc {}".format(charge)

    _runexternal.runExternal(commandstr, procname="antechamber")

    return _os.path.abspath(output_name)


def runParmchk(force_field, file):
    """
    A wrapper around parmchk2.

    Parameters
    ----------
    force_field : str
        Which force field to use. Only "gaff" and "gaff2" are accepted.
    file : str
        Name of the file generated by antechamber.

    Returns
    -------
    filename_output : str
        Absolute path to the extra parameter file generated by parmchk2.
    """
    input_base, input_ext = _os.path.splitext(file)[0], file.split(".")[-1]
    commandstr = "parmchk2 -i '{0}.{1}' -f {1} -o '{0}.frcmod' -s %s".format(input_base, input_ext, force_field)
    _runexternal.runExternal(commandstr, procname="parmchk2")

    return _os.path.abspath(input_base + ".frcmod")


def runTleap(force_fields=None, files=None, param_files=None, id=None, disulfide_bonds=None):
    """
    Writes and runs tleap scripts.

    Parameters
    ----------
    force_fields : [str]
        All force fields to be loaded in tleap.
    files : [str]
        All regular files to be loaded in tleap.
    param_files : [str]
        All parameter files to be loaded in tleap.
    id : str
        The name of the molecule. Default: equal to molecule_type.
    disulfide_bonds : [[ProtoCaller.IO.PDB.Residue, ProtoCaller.IO.PDB.Residue]]:
        Residues between which there is a disulfide bond.

    Returns
    -------
    filenames : [str]
        Absolute paths of the final parametrised files. The first file is a topology file and the second file is a
        coordinate file.
    """
    if id is None: id = "molecule"
    if disulfide_bonds is None: disulfide_bonds = []

    filename_tleap = "tleap_script_%s.in" % id
    filenames = [id + ".prmtop", id + ".inpcrd"]

    with open(filename_tleap, "w+") as out:
        for force_field in force_fields:
            out.write("source \"%s\"\n" % returnFFPath(force_field))
        if param_files is not None:
            for param_file in param_files:
                ext = param_file.split(".")[-1].lower()
                if ext in ["frcmod", "frcfld"]:
                    command = "loadamberparams"
                elif ext in ["off", "lib"]:
                    command = "loadoff"
                elif ext == "prep":
                    command = "loadamberprep"
                else:
                    _warnings.warn("%s is not a valid parameter file. Skipping value..." % param_file)
                    continue
                out.write("%s \"%s\"\n" % (command, param_file))
        for file in files:
            ext = file.split(".")[-1]
            if ext == "pqr": ext = "pdb"
            out.write("MOL = load%s \"%s\"\n" % (ext, file))
        for disulfide_bond in disulfide_bonds:
            out.write("bond MOL.%d.SG MOL.%d.SG\n" % (disulfide_bond[0].resSeq, disulfide_bond[1].resSeq))
        out.write("check MOL\n")
        out.write("saveAmberParm MOL {0} {1}\n".format(*filenames))
        out.write("quit\n")

    _runexternal.runExternal("tleap -f %s" % filename_tleap, procname="tleap")
    return [_os.path.abspath(f) for f in filenames]


def returnFFPath(name):
    """
    Returns the relative path of the target force field.

    Parameters
    ----------
    name : str
        Force field name.

    Returns
    -------
    name : str
        Relative path to the force field file.
    """
    if name in _PC.AMBEROLDFFS:
        return "oldff/leaprc." + name
    elif name in _PC.AMBERPROTEINFFS:
        return "leaprc.protein.%s" % name
    elif name in _PC.AMBERWATERFFS:
        return "leaprc.water.%s" % name
    else:
        return "leaprc." + name
