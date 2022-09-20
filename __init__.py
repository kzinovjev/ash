"""
ASH - A MULTISCALE MODELLING PROGRAM

"""
# Python libraries
import os
import shutil
import numpy as np
import copy
import subprocess as sp
import glob
import sys
import inspect
import time
import atexit

###############
# ASH modules
###############
import ash

# Adding modules,interfaces directories to sys.path
ashpath = os.path.dirname(ash.__file__)
# sys.path.insert(1, ashpath+'/modules')
# sys.path.insert(1, ashpath+'/interfaces')
# sys.path.insert(1, ashpath+'/functions')

from ash.functions.functions_general import blankline, BC, listdiff, print_time_rel, print_time_rel_and_tot, pygrep, \
    printdebug, read_intlist_from_file, frange, writelisttofile, load_julia_interface, read_datafile, write_datafile

# Fragment class and coordinate functions
import ash.modules.module_coords
from ash.modules.module_coords import get_molecules_from_trajectory, eldict_covrad, write_pdbfile, Fragment, read_xyzfile, \
    write_xyzfile, make_cluster_from_box, read_ambercoordinates, read_gromacsfile
from ash.modules.module_coords import remove_atoms_from_system_CHARMM, add_atoms_to_system_CHARMM, getwaterconstraintslist,\
    QMregionfragexpand, read_xyzfiles, Reaction

# Singlepoint
import ash.modules.module_singlepoint
from ash.modules.module_singlepoint import Singlepoint, newSinglepoint, ZeroTheory, Singlepoint_fragments,\
     Singlepoint_theories, Singlepoint_fragments_and_theories, Singlepoint_reaction

# Parallel
import ash.functions.functions_parallel
from ash.functions.functions_parallel import Singlepoint_parallel, run_QMMM_SP_in_parallel

# Freq
from ash.modules.module_freq import AnFreq, NumFreq, approximate_full_Hessian_from_smaller, calc_rotational_constants,get_dominant_atoms_in_mode, write_normalmode

# Constants
import ash.constants

# functions related to electronic structure
import ash.functions.functions_elstructure
from ash.functions.functions_elstructure import read_cube, write_cube_diff

#multiwfn interface
import ash.interfaces.interface_multiwfn
from ash.interfaces.interface_multiwfn import multiwfn_run
# Spinprojection
from ash.modules.module_spinprojection import SpinProjectionTheory

# Surface
from ash.modules.module_surface import calc_surface, calc_surface_fromXYZ, read_surfacedict_from_file, \
    write_surfacedict_to_file

# QMcode interfaces
from ash.interfaces.interface_ORCA import ORCATheory, counterpoise_calculation_ORCA, ORCA_External_Optimizer, run_orca_plot, \
        run_orca_mapspc, make_molden_file_ORCA, grab_coordinates_from_ORCA_output
import ash.interfaces.interface_ORCA

from ash.interfaces.interface_Psi4 import Psi4Theory
from ash.interfaces.interface_dalton import DaltonTheory
from ash.interfaces.interface_pyscf import PySCFTheory
from ash.interfaces.interface_MLMM import MLMMTheory
from ash.interfaces.interface_MRCC import MRCCTheory
from ash.interfaces.interface_CFour import CFourTheory
from ash.interfaces.interface_xtb import xTBTheory

# MM: external and internal
from ash.interfaces.interface_OpenMM import OpenMMTheory, OpenMM_MD, OpenMM_MDclass, OpenMM_Opt, OpenMM_Modeller, \
    MDtraj_imagetraj, solvate_small_molecule, MDAnalysis_transform, OpenMM_box_relaxation, write_nonbonded_FF_for_ligand
from ash.modules.module_MM import NonBondedTheory, UFFdict, UFF_modH_dict, LJCoulpy, coulombcharge, LennardJones, \
    LJCoulombv2, LJCoulomb, MMforcefield_read

# QM/MM
from ash.modules.module_QMMM import QMMMTheory, actregiondefine
from ash.modules.module_polembed import PolEmbedTheory

# Knarr
from ash.interfaces.interface_knarr import NEB

# ASE-Dynamics
from ash.interfaces.interface_ASE import Dynamics_ASE

# Plumed interface
from ash.interfaces.interface_plumed import plumed_ASH, MTD_analyze

# Solvation
# NOTE: module_solvation.py or module_solvation2.py To be cleaned up
import ash.functions.functions_solv

# Molcrys
import ash.modules.module_molcrys
from ash.modules.module_molcrys import molcrys, Fragmenttype

# Geometry optimization
from ash.functions.functions_optimization import SimpleOpt, BernyOpt
from ash.interfaces.interface_geometric import geomeTRICOptimizer

# PES
import ash.modules.module_PES
from ash.modules.module_PES import PhotoElectronSpectrum, potential_adjustor_DFT

# Workflows, benchmarking etc
import ash.modules.module_workflows
import ash.modules.module_highlevel_workflows
from ash.modules.module_highlevel_workflows import CC_CBS_Theory, ORCA_CC_CBS_Theory
from ash.modules.module_workflows import ReactionEnergy, thermochemprotocol_reaction, thermochemprotocol_single, \
    confsampler_protocol, auto_active_space, calc_xyzfiles, ProjectResults, Reaction_Highlevel_Analysis, FormationEnthalpy, \
    AutoNonAufbau, ExcitedStateSCFOptimizer
import ash.modules.module_benchmarking
from ash.modules.module_benchmarking import run_benchmark


#Plotting
import ash.modules.module_plotting
from ash.modules.module_plotting import reactionprofile_plot, contourplot, plot_Spectrum, MOplot_vertical, ASH_plot

# Other
import ash.interfaces.interface_crest
from ash.interfaces.interface_crest import call_crest, call_crest_entropy, get_crest_conformers

# Initialize settings
import ash.settings_ash

# Print header
import ash.ash_header
ash_header.print_header()

# Exit command (footer)
if ash.settings_ash.settings_dict["print_exit_footer"] is True:
    atexit.register(ash_header.print_footer)
    if ash.settings_ash.settings_dict["print_full_timings"] is True:
        atexit.register(ash_header.print_timings)

# Julia dependency. Load in the beginning or not. 
#As both PyJulia and PythonCall are a bit slow to load, it is best to only load when needed (current behaviour)
if ash.settings_ash.settings_dict["load_julia"] is True:
    try:
        print("Importing Julia interface and loading functions")
        Juliafunctions = load_julia_interface()
        # Hungarian package needs to be installed
        # try:
        #    from julia import Hungarian
        # except:
        #    print("Problem loading Julia packages: Hungarian")

    except ImportError:
        print("Problem importing Julia interface")
        print(
            "Make sure Julia is installed, Pythoncall/juliacall and the required Julia packages have been "
            "installed.")
        print("Proceeding. Slower Python routines will used instead when possible")
        # Connectivity code in Fragment
        ash.settings_ash.settings_dict["connectivity_code"] = "py"
        # LJ+Coulomb and pairpot arrays in nonbonded MM
        ash.settings_ash.settings_dict["nonbondedMM_code"] = "py"
