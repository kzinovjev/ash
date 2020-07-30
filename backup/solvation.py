#####################
# SOLVSHELL PROGRAM #
#####################
# For now only the snapshot-part. Will read snapshots from QM/MM MD Tcl-Chemshell run.
import numpy as np
import time
beginTime = time.time()
CheckpointTime = time.time()
import os
import sys
from functions_solv import *
from functions_general import *
from functions_coords import *
from functions_ORCA import *
import settings_solvation
import constants
import statistics
import shutil


programversion=0.1
blankline()
print_solvshell_header(programversion)

#TODO: reduce number of variables being passed to functions. Pass whole solvsphere object sometimes. Careful though, breaks generality
#TODO: Create more objects. QMtheory object or Input object or something and then pass that around
calcdir=os.getcwd()
# If inside PyCharm:
if 'PYCHARM_HOSTED' in os.environ:
    print("Inside PyCharm")
    calcdir='/Users/bjornssonsu/Redox-tests'
    shutil.rmtree(calcdir+'/snaps/snaps-LL', ignore_errors=True)
    shutil.rmtree(calcdir + '/snaps/SRPol-LL', ignore_errors=True)
    shutil.rmtree(calcdir + '/snaps/Bulk-LL', ignore_errors=True)
    shutil.rmtree(calcdir + '/snaps/LRPol-LL', ignore_errors=True)
    shutil.rmtree(calcdir + '/snaps/Gas-calculations', ignore_errors=True)

sys.path.append(calcdir)
os.chdir(calcdir)

# Read inputfile in cwd, called: solvshell_input.py
try:
    from solvshell_input import (programdir, orcadir, xtbdir, NumCores, calctype, orcasimpleinput_LL, orcablockinput_LL,
    orcasimpleinput_HL, orcablockinput_HL, orcasimpleinput_SRPOL, orcablockinput_SRPOL, xtbmethod, EOM, BulkCorrection, GasCorrection, ShortRangePolarization,
    SRPolShell, LRPolShell, LongRangePolarization, PrintFinalOutput, Testmode, repsnapmethod, repsnapnumber, solvbasis)
except ImportError as error:
    print("Missing variable in solvshell_input.py file!")
    #TODO: Mention which missing variable here. Proper exception handling
print("Current working directory", os.getcwd(),)
#Print input settings
blankline()

print(BC.OKBLUE,"Input variables defined:", BC.END)
print("-----------------------------------")
print("Program directory:", programdir)
print("Calculation directory:", calcdir)
print("orcadir:", orcadir )
print("xtbdir:", xtbdir )
print("NumCores:", NumCores )
print("calctype:", BC.OKBLUE,calctype )
print("EOM:", EOM)
print("orcasimpleinput_LL:", orcasimpleinput_LL)
print("orcablockinput_LL:", orcablockinput_LL)
print("ShortRangePolarization:", ShortRangePolarization)
print("orcasimpleinput_SRPOL:", orcasimpleinput_SRPOL)
print("orcablockinput_SRPOL:", orcablockinput_SRPOL)
print("solvbasis:", solvbasis)
print("SRPolShell:", SRPolShell)
print("LongRangePolarization:", LongRangePolarization)
print("xtbmethod:", xtbmethod)
print("LRPolShell:", LRPolShell)
print("BulkCorrection:", BulkCorrection)
print("GasCorrection:", GasCorrection)
print("orcasimpleinput_HL:", orcasimpleinput_HL)
print("orcablockinput_HL:", orcablockinput_HL)
print("repsnapmethod:", repsnapmethod)
print("repsnapnumber:", repsnapnumber)
print("PrintFinalOutput:", PrintFinalOutput)
print("Testmode:", Testmode)
print("-----------------------------------")

#Load some global settings and making orcadir global
settings_solvation.init(programdir,orcadir,xtbdir,NumCores)

blankline()
print_line_with_mainheader("CALCULATION TYPE: {}".format(calctype.upper()))
blankline()

mdvarfile=calcdir+'/md-variables.defs'
print("Reading MD-run variable file:", mdvarfile)
#calcdir contains md-variables.defs and snaps dir with snapshots
#Create system object with information about the system (charge,mult of states A, B, forcefield, snapshotlist etc.)
#Attributes: name, chargeA, multA, chargeB, multB, solutetypesA, solutetypesB, solventtypes, snapslist, snapshotsA, snapshotsB
solvsphere=read_md_variables_file(mdvarfile)
print("Solvsphere Object defined.")
print("Solvsphere atoms:", solvsphere.numatoms)
#Simple general connectivity stored in solvsphere object: solvsphere.connectivity
solvsphere.calc_connectivity()
print("Solvsphere connectivity stored in file: snaps/stored_connectivity")
with open(calcdir+'/snaps/stored_connectivity', 'w') as connfile:
    for i in solvsphere.connectivity:
        connfile.write(str(i)+'\n')

#Temporary redefinition of lists for easier faster test runs
if Testmode == True:
    solvsphere.snapslist, solvsphere.snapshotsA, solvsphere.snapshotsB, solvsphere.snapshots = TestModerun()

#Get solvent pointcharges for solvent-unit. e.g. [-0.8, 0.4, 0.4] for TIP3P, assuming [O, H, H] order
# Later use dictionary or object or something for this
blankline()
print("Solvent information:")
if solvsphere.solvtype=="tip3p":
    print("Solvent: TIP3P")
    solventunitcharges=[-0.834, 0.417, 0.417]
    print("Pointcharges of solvent fragment:", solventunitcharges)
    print("Atom types of solvent unit:", solvsphere.solventtypes )
else:
    print("Unknown solvent")
    solventunitcharges=[]
    exit_solvshell()

blankline()

###################################
# All snapshots: Low-Level Theory #
###################################
print_line_with_mainheader("Low-level theory on All Snapshots")
CheckpointTime = time.time()
# cd to snaps dir, create separate dir for calculations and copy fragmentfiles to it.
os.chdir('./snaps')
os.mkdir('snaps-LL')
os.chdir('./snaps-LL')
for i in solvsphere.snapshots:
    shutil.copyfile('../'+i+'.c', './'+i+'.c')
print("Current dir:", os.getcwd())
# Temp: Convert snapshots in Tcl-Chemshell fragment file format to xyz coords in Angstrom.
#Future change: Have code spit out XYZ files instead of Chemshell fragment files

#Write ORCA inputfiles and pointchargesfiles for lowlevel theory
# Doing both redox states in each inputfile


print("Creating inputfiles")
identifiername = '_LL'
solute_atoms=solvsphere.soluteatomsA
solvent_atoms=solvsphere.solventatoms
snapshotinpfiles = create_AB_inputfiles_ORCA(solute_atoms, solvent_atoms, solvsphere, solvsphere.snapshots,
                                                  orcasimpleinput_LL, orcablockinput_LL, solventunitcharges, identifiername)

print("There are {} snapshots for A trajectory.".format(len(solvsphere.snapshotsA)))
print("There are {} snapshots for B trajectory.".format(len(solvsphere.snapshotsB)))
print("There are {} snapshots in total.".format(len(snapshotinpfiles)))
blankline()
print_time_rel_and_tot(CheckpointTime, beginTime)
CheckpointTime = time.time()
#print("The following snapshot inputfiles will be run:\n", snapshotinpfiles)
blankline()

#RUN INPUT

print_line_with_subheader1("Running snapshot calculations at LL theory")
print(BC.WARNING,"LL-theory:", orcasimpleinput_LL,BC.END)
run_inputfiles_in_parallel_AB(snapshotinpfiles)

#TODO: Clean up. Delete GBW files etc. Needed ??

###################################
# GRAB OUTPUT #
###################################
blankline()
AllsnapsABenergy, AsnapsABenergy, BsnapsABenergy=grab_energies_output(snapshotinpfiles)
blankline()
#print("AllsnapsABenergy:", AllsnapsABenergy)
#print("AsnapsABenergy:", AsnapsABenergy)
#print("BsnapsABenergy:", BsnapsABenergy)
blankline()

#Average and stdevs of

#Averages and stdeviations over whole trajectory at LL theory
ave_trajAB = statistics.mean(list(AllsnapsABenergy.values()))
#stdev_trajAB = statistics.stdev(list(AllsnapsABenergy.values()))
stdev_trajAB = 0.0
ave_trajA = statistics.mean(list(AsnapsABenergy.values()))
stdev_trajA = statistics.stdev(list(AsnapsABenergy.values()))
ave_trajB = statistics.mean(list(BsnapsABenergy.values()))
stdev_trajB = statistics.stdev(list(BsnapsABenergy.values()))

print("TrajA average: {:3.3f} eV. Stdev: {:3.3f} eV.".format(ave_trajA, stdev_trajA))
print("TrajB average: {:3.3f} eV. Stdev: {:3.3f} eV.".format(ave_trajB, stdev_trajB))
print("A+B average: {:3.3f} eV. Stdev: {:3.3f} eV.".format(ave_trajAB, stdev_trajAB))
blankline()

#######################################################
# REPRESENTATIVE SNAPSHOTS
#######################################################
print("Representative snapshot method:", repsnapmethod)
print("Representative snapshot number:", repsnapnumber)
#Creating dictionaries:
repsnapsA=repsnaplist(repsnapmethod, repsnapnumber, AsnapsABenergy)
repsnapsB=repsnaplist(repsnapmethod, repsnapnumber, BsnapsABenergy)
#Combined list of repsnaps
print("Representative snapshots for each trajectory")
blankline()
print("Traj A:")
for i in repsnapsA:
    print(i)
blankline()
print("Traj B:")
for i in repsnapsB:
    print(i)

repsnaplistA = list(repsnapsA.keys())
repsnaplistB = list(repsnapsB.keys())
repsnaplistAB=repsnaplistA+repsnaplistB
blankline()
#Averages and stdeviations over repsnaps  at LL theory
repsnap_ave_trajA = statistics.mean(list(repsnapsA.values()))
repsnap_stdev_trajA = statistics.stdev(list(repsnapsA.values()))
repsnap_ave_trajB = statistics.mean(list(repsnapsB.values()))
repsnap_stdev_trajB = statistics.stdev(list(repsnapsB.values()))
repsnap_ave_trajAB= statistics.mean([repsnap_ave_trajA,repsnap_ave_trajB])
repsnap_stdev_trajAB= "TBD"
print("Repsnaps TrajA average: {:3.3f} ± {:3.3f} eV".format(repsnap_ave_trajA, repsnap_stdev_trajA))
print("Repsnaps TrajB average: {:3.3f} ± {:3.3f} eV".format(repsnap_ave_trajB, repsnap_stdev_trajB))
print("Repsnaps TrajAB average: {:3.3f} ± TBD eV".format(repsnap_ave_trajAB))
blankline()
print("Deviation between repsnaps mean and full mean for A: {:3.3f} eV.".format(ave_trajA-repsnap_ave_trajA))
print("Deviation between repsnaps mean and full mean for B: {:3.3f} eV.".format(ave_trajB-repsnap_ave_trajB))
blankline()
print_time_rel_and_tot(CheckpointTime, beginTime,'All snaps')
CheckpointTime = time.time()
#Going up to snaps dir again
os.chdir('..')

if BulkCorrection==True:
    #############################################
    # Representative snapshots: Bulk Correction #
    #############################################
    print_line_with_mainheader("Bulk Correction on Representative Snapshots")
    os.mkdir('Bulk-LL')
    os.chdir('./Bulk-LL')
    for i in repsnaplistAB:
        shutil.copyfile('../' + i + '.c', './' + i + '.c')
    print("Entering dir:", os.getcwd())

    print("Doing BulkCorrection on representative snapshots. Creating inputfiles...")
    print("Using hollow bulk sphere:", settings_solvation.bulksphere.pathtofile)
    print("Number of added bulk point charges:", settings_solvation.bulksphere.numatoms)
    bulkcorr=True
    identifiername='_Bulk_LL'
    print("repsnaplistA:", repsnaplistA)
    print("repsnaplistB:", repsnaplistB)
    blankline()
    bulkinpfiles = create_AB_inputfiles_ORCA(solute_atoms, solvent_atoms, solvsphere, repsnaplistAB,
                                                     orcasimpleinput_LL, orcablockinput_LL, solventunitcharges, identifiername, None, bulkcorr)

    # RUN BULKCORRECTION INPUTFILES
    print_line_with_subheader1("Running Bulk Correction calculations at LL theory")
    print(BC.WARNING,"LL-theory:", orcasimpleinput_LL,BC.END)
    run_inputfiles_in_parallel_AB(bulkinpfiles)

    #GRAB output
    Bulk_Allrepsnaps_ABenergy, Bulk_Arepsnaps_ABenergy, Bulk_Brepsnaps_ABenergy=grab_energies_output(bulkinpfiles)
    blankline()
    #Get bulk correction per snapshot
    #print("Bulk_Allrepsnaps_ABenergy:", Bulk_Allrepsnaps_ABenergy)
    print("Bulk-IP values for traj A:", Bulk_Arepsnaps_ABenergy)
    print("Bulk-IP values for traj B:", Bulk_Brepsnaps_ABenergy)
    blankline()
    print("Non-Bulk values for repsnapsA:", repsnapsA)
    print("Non-Bulk values for repsnapsB:", repsnapsB)
    Bulk_ave_trajA=statistics.mean(Bulk_Arepsnaps_ABenergy.values())
    Bulk_ave_trajB=statistics.mean(Bulk_Brepsnaps_ABenergy.values())
    Bulk_ave_trajAB=statistics.mean([Bulk_ave_trajA,Bulk_ave_trajB])
    Bulk_stdev_trajA=statistics.stdev(Bulk_Arepsnaps_ABenergy.values())
    Bulk_stdev_trajB=statistics.stdev(Bulk_Brepsnaps_ABenergy.values())
    Bulk_stdev_trajAB=0.0
    blankline()
    print("Bulk calculation TrajA average: {:3.3f} ± {:3.3f}".format(Bulk_ave_trajA, Bulk_stdev_trajA))
    print("Bulk calculation TrajB average: {:3.3f} ± {:3.3f}".format(Bulk_ave_trajB, Bulk_stdev_trajB))
    print("Bulk calculation TrajAB average: {:3.3f} ± TBD".format(Bulk_ave_trajAB))
    bulkcorrdict_A={}
    bulkcorrdict_B={}
    for b in Bulk_Arepsnaps_ABenergy:
        for c in repsnapsA:
            if b==c:
                bulkcorrdict_A[b]=Bulk_Arepsnaps_ABenergy[b]-repsnapsA[b]
    for b in Bulk_Brepsnaps_ABenergy:
        for c in repsnapsB:
            if b==c:
                bulkcorrdict_B[b]=Bulk_Brepsnaps_ABenergy[b]-repsnapsB[b]

    blankline()
    print("Bulk corrections per snapshot:")
    print("bulkcorrdict_A:", bulkcorrdict_A)
    print("bulkcorrdict_B", bulkcorrdict_B)
    Bulkcorr_mean_A=statistics.mean(bulkcorrdict_A.values())
    Bulkcorr_mean_B=statistics.mean(bulkcorrdict_B.values())
    Bulkcorr_stdev_A=statistics.stdev(bulkcorrdict_A.values())
    Bulkcorr_stdev_B=statistics.stdev(bulkcorrdict_B.values())
    Bulkcorr_mean_AB=statistics.mean([Bulkcorr_mean_A,Bulkcorr_mean_B])
    blankline()
    print("Traj A: Bulkcorrection {:3.3f} ± {:3.3f} eV".format(Bulkcorr_mean_A, Bulkcorr_stdev_A))
    print("Traj B: Bulkcorrection {:3.3f} ± {:3.3f} eV".format(Bulkcorr_mean_B, Bulkcorr_stdev_B))
    print("Combined Bulkcorrection {:3.3f} eV".format(Bulkcorr_mean_AB))
    blankline()
    print_time_rel_and_tot(CheckpointTime, beginTime,'Bulk')
    CheckpointTime = time.time()
    #Going up to snaps dir again
    os.chdir('..')
else:
    Bulk_ave_trajAB=0; Bulk_stdev_trajAB=0; Bulkcorr_mean_AB=0
    Bulk_ave_trajB=0; Bulk_stdev_trajB=0; Bulkcorr_mean_B=0
    Bulk_ave_trajA=0; Bulk_stdev_trajA=0; Bulkcorr_mean_A=0

if ShortRangePolarization==True:
    #############################################
    # Short-Range Polarization (QM-region expansion) calculations #
    #############################################
    print_line_with_mainheader("Short-Range Polarization calculations: QM-Region Expansion")
    os.mkdir('SRPol-LL')
    os.chdir('./SRPol-LL')
    for i in repsnaplistAB:
        shutil.copyfile('../' + i + '.c', './' + i + '.c')
    print("Current dir:", os.getcwd())

    # INCREASED QM-REGION CALCULATIONS
    print("Doing Short-Range Polarization Step. Creating inputfiles...")
    print("Snapshots:", repsnaplistAB)
    print("Using QM-region shell:", SRPolShell, "Å")
    blankline()
    # PART 1
    #Create inputfiles of repsnapshots with increased QM regions
    identifiername='_SR_LL'
    SRPolinpfiles = create_AB_inputfiles_ORCA(solute_atoms, solvent_atoms, solvsphere, repsnaplistAB,
                                                     orcasimpleinput_SRPOL, orcablockinput_SRPOL, solventunitcharges,
                                                      identifiername, SRPolShell, False, solvbasis)

    # Run ShortRangePol INPUTFILES (increased QM-region)
    print_line_with_subheader1("Running SRPol calculations at LL theory")
    print(BC.WARNING,"LL-theory:", orcasimpleinput_SRPOL,BC.END)
    print(BC.WARNING,"LL-theory:", orcablockinput_SRPOL,BC.END)
    print("Solvbasis:", solvbasis)
    SRORCAPar=True
    if SRORCAPar==True:
        print("Using ORCA parallelization. Running each file 1 by 1. ORCA using {} cores".format(NumCores))
        for SRPolinpfile in SRPolinpfiles:
            print("Running file: ", SRPolinpfile)
            run_orca_SP_ORCApar(SRPolinpfile, nprocs=NumCores)
    else:
        print("Using multiproc parallelization. All calculations running in parallel but each ORCA calculation using 1 core.")
        run_inputfiles_in_parallel_AB(SRPolinpfiles)

    #GRAB output
    SRPol_Allrepsnaps_ABenergy, SRPol_Arepsnaps_ABenergy, SRPol_Brepsnaps_ABenergy=grab_energies_output(SRPolinpfiles)
    blankline()

    # PART 2.
    # Whether to calculate repsnapshots again at SRPOL level of theory
    if orcasimpleinput_SRPOL == orcasimpleinput_LL:
        print("orcasimpleinput_SRPOL is same as orcasimpleinput_LL")
        print("Using previously calculated values for Region1")
        SRPol_Arepsnaps_ABenergy_Region1=repsnapsA
        SRPol_Brepsnaps_ABenergy_Region1=repsnapsB
    else:
        print("orcasimpleinput_SRPOL is different")
        print("Need to recalculate repsnapshots at SRPOL level of theory using regular QM-region")
        identifiername = '_SR_LL_Region1'
        SRPolinpfiles_Region1 = create_AB_inputfiles_ORCA(solute_atoms, solvent_atoms, solvsphere, repsnaplistAB,
                                                     orcasimpleinput_SRPOL, orcablockinput_SRPOL, solventunitcharges,
                                                      identifiername, None, False, solvbasis)
        #Run the inputfiles
        run_inputfiles_in_parallel_AB(SRPolinpfiles_Region1)
        #Grab the energies
        SRPol_Allrepsnaps_ABenergy_Region1, SRPol_Arepsnaps_ABenergy_Region1, SRPol_Brepsnaps_ABenergy_Region1 = grab_energies_output(
            SRPolinpfiles_Region1)


    #Calculate SRPol correction per snapshot
    #print("SRPol_Allrepsnaps_ABenergy:", SRPol_Allrepsnaps_ABenergy)
    print("Large QM-region SRPol-IP for traj A:", SRPol_Arepsnaps_ABenergy)
    print("Large QM-region SRPol-IP for traj B", SRPol_Brepsnaps_ABenergy)
    blankline()

    print("Regular QM-region values for repsnapsA:", SRPol_Arepsnaps_ABenergy_Region1)
    print("Regular QM-region for repsnapsB:", SRPol_Brepsnaps_ABenergy_Region1)

    SRPol_ave_trajA=statistics.mean(SRPol_Arepsnaps_ABenergy.values())
    SRPol_ave_trajB=statistics.mean(SRPol_Brepsnaps_ABenergy.values())
    SRPol_ave_trajAB=statistics.mean([SRPol_ave_trajA,SRPol_ave_trajB])
    SRPol_stdev_trajA=statistics.stdev(SRPol_Arepsnaps_ABenergy.values())
    SRPol_stdev_trajB=statistics.stdev(SRPol_Brepsnaps_ABenergy.values())
    SRPol_stdev_trajAB=0.0
    blankline()
    print("SRPol calculation TrajA average: {:3.3f} ± {:3.3f}".format(SRPol_ave_trajA, SRPol_stdev_trajA))
    print("SRPol calculation TrajB average: {:3.3f} ± {:3.3f}".format(SRPol_ave_trajB, SRPol_stdev_trajB))
    print("SRPol calculation TrajAB average: {:3.3f} ± TBD".format(SRPol_ave_trajAB))
    SRPolcorrdict_A={}
    SRPolcorrdict_B={}

    #Calculating correction per snapshot
    for b in SRPol_Arepsnaps_ABenergy:
        for c in repsnapsA:
            if b==c:
                SRPolcorrdict_A[b]=SRPol_Arepsnaps_ABenergy[b]-SRPol_Arepsnaps_ABenergy_Region1[b]
    for b in SRPol_Brepsnaps_ABenergy:
        for c in repsnapsB:
            if b==c:
                SRPolcorrdict_B[b]=SRPol_Brepsnaps_ABenergy[b]-SRPol_Brepsnaps_ABenergy_Region1[b]

    blankline()
    print("Dictionaries of corrections per snapshots:")
    print("SRPolcorrdict_A:", SRPolcorrdict_A)
    print("SRPolcorrdict_B", SRPolcorrdict_B)
    SRPolcorr_mean_A=statistics.mean(SRPolcorrdict_A.values())
    SRPolcorr_mean_B=statistics.mean(SRPolcorrdict_B.values())
    SRPolcorr_stdev_A=statistics.stdev(SRPolcorrdict_A.values())
    SRPolcorr_stdev_B=statistics.stdev(SRPolcorrdict_B.values())
    SRPolcorr_mean_AB=statistics.mean([SRPolcorr_mean_A,SRPolcorr_mean_B])
    blankline()
    print("Traj A: SRPolcorrection {:3.3f} ± {:3.3f} eV".format(SRPolcorr_mean_A, SRPolcorr_stdev_A))
    print("Traj B: SRPolcorrection {:3.3f} ± {:3.3f} eV".format(SRPolcorr_mean_B, SRPolcorr_stdev_B))
    print("Combined SRPolcorrection {:3.3f} eV".format(SRPolcorr_mean_AB))
    blankline()
    print_time_rel_and_tot(CheckpointTime, beginTime,'SRPol')
    CheckpointTime = time.time()
    #Going up to snaps dir again
    os.chdir('..')
else:
    SRPol_ave_trajAB=0; SRPol_stdev_trajAB=0; SRPolcorr_mean_AB=0
    SRPol_ave_trajB=0; SRPol_stdev_trajB=0; SRPolcorr_mean_B=0
    SRPol_ave_trajA=0; SRPol_stdev_trajA=0; SRPolcorr_mean_A=0

if LongRangePolarization==True:
    ##############################################################
    # Long-Range Polarization (QM-region expansion) calculations #
    ##############################################################
    print_line_with_mainheader("Long-Range Polarization calculations: xTB Level")
    os.mkdir('LRPol-LL')
    os.chdir('./LRPol-LL')
    for i in repsnaplistAB:
        shutil.copyfile('../' + i + '.c', './' + i + '.c')
    print("Current dir:", os.getcwd())

    print("Using xTB method:", xtbmethod)
    print("Doing Long-Range Polarization Step. Creating inputfiles...")
    print("Snapshots:", repsnaplistAB)
    print("Using SR QM-region shell:", SRPolShell, "Å")
    print("Using LR QM-region shell:", LRPolShell, "Å")
    blankline()
    #Create inputfiles of repsnapshots with increased QM regions
    print("Creating inputfiles for Long-Range Correction Region1:", SRPolShell, "Å")
    identifiername='_LR_LL-R1'
    LRPolinpfiles_Region1 = create_AB_inputfiles_xtb(solute_atoms, solvent_atoms, solvsphere, repsnaplistAB,
                                     solventunitcharges, identifiername, shell=SRPolShell)
    blankline()
    print("Creating inputfiles for Long-Range Correction Region2:", LRPolShell, "Å")
    identifiername='_LR_LL-R2'
    LRPolinpfiles_Region2 = create_AB_inputfiles_xtb(solute_atoms, solvent_atoms, solvsphere, repsnaplistAB,
                                     solventunitcharges, identifiername, shell=LRPolShell)
    blankline()

    # Run xTB calculations using XYZ-files
    print_line_with_subheader1("Running LRPol calculations Region 1 at xTB level of theory")
    print("LRPolinpfiles_Region1:", LRPolinpfiles_Region1)
    print(BC.WARNING,"xtb theory:", xtbmethod, BC.END)
    run_inputfiles_in_parallel_xtb(LRPolinpfiles_Region1, xtbmethod, solvsphere.ChargeA, solvsphere.MultA,solvsphere.ChargeB, solvsphere.MultB )
    print_line_with_subheader1("Running LRPol calculations Region 2 at xTB level of theory")
    print("LRPolinpfiles_Region2:", LRPolinpfiles_Region2)
    print(BC.WARNING,"xtb theory:", xtbmethod, BC.END)
    run_inputfiles_in_parallel_xtb(LRPolinpfiles_Region2, xtbmethod, solvsphere.ChargeA, solvsphere.MultA, solvsphere.ChargeB, solvsphere.MultB)

    # GRAB output
    LRPol_Allrepsnaps_ABenergy_Region1, LRPol_Arepsnaps_ABenergy_Region1, LRPol_Brepsnaps_ABenergy_Region1 = grab_energies_output_xtb(xtbmethod, LRPolinpfiles_Region1)
    blankline()
    LRPol_Allrepsnaps_ABenergy_Region2, LRPol_Arepsnaps_ABenergy_Region2, LRPol_Brepsnaps_ABenergy_Region2 = grab_energies_output_xtb(xtbmethod, LRPolinpfiles_Region2)

    # Gathering stuff for both regions
    print("LRPol_Allrepsnaps_ABenergy_Region1:", LRPol_Allrepsnaps_ABenergy_Region1)
    print("LRPol_Arepsnaps_ABenergy_Region1:", LRPol_Arepsnaps_ABenergy_Region1)
    print("LRPol_Brepsnaps_ABenergy_Region1:", LRPol_Brepsnaps_ABenergy_Region1)
    print("LRPol_Allrepsnaps_ABenergy_Region2:", LRPol_Allrepsnaps_ABenergy_Region2)
    print("LRPol_Arepsnaps_ABenergy_Region2:", LRPol_Arepsnaps_ABenergy_Region2)
    print("LRPol_Brepsnaps_ABenergy_Region2:", LRPol_Brepsnaps_ABenergy_Region2)

    #Calculating averages and stdevs
    LRPol_ave_trajA_Region2 = statistics.mean(LRPol_Arepsnaps_ABenergy_Region2.values())
    LRPol_ave_trajB_Region2 = statistics.mean(LRPol_Brepsnaps_ABenergy_Region2.values())
    LRPol_ave_trajAB_Region2 = statistics.mean([LRPol_ave_trajA_Region2, LRPol_ave_trajB_Region2])
    LRPol_stdev_trajA_Region2 = statistics.stdev(LRPol_Arepsnaps_ABenergy_Region2.values())
    LRPol_stdev_trajB_Region2 = statistics.stdev(LRPol_Brepsnaps_ABenergy_Region2.values())
    LRPol_stdev_trajAB_Region2 = 0.0
    LRPol_ave_trajA_Region1 = statistics.mean(LRPol_Arepsnaps_ABenergy_Region1.values())
    LRPol_ave_trajB_Region1 = statistics.mean(LRPol_Brepsnaps_ABenergy_Region1.values())
    LRPol_ave_trajAB_Region1 = statistics.mean([LRPol_ave_trajA_Region1, LRPol_ave_trajB_Region1])
    LRPol_stdev_trajA_Region1 = statistics.stdev(LRPol_Arepsnaps_ABenergy_Region1.values())
    LRPol_stdev_trajB_Region1 = statistics.stdev(LRPol_Brepsnaps_ABenergy_Region1.values())
    LRPol_stdev_trajAB_Region1 = 0.0
    blankline()
    print("LRPol_Region2 calculation TrajA average: {:3.3f} ± {:3.3f}".format(LRPol_ave_trajA_Region2, LRPol_stdev_trajA_Region2))
    print("LRPol_Region2 calculation TrajB average: {:3.3f} ± {:3.3f}".format(LRPol_ave_trajB_Region2, LRPol_stdev_trajB_Region2))
    print("LRPol_Region2 calculation TrajAB average: {:3.3f} ± TBD".format(LRPol_ave_trajAB_Region2))
    print("LRPol_Region1 calculation TrajA average: {:3.3f} ± {:3.3f}".format(LRPol_ave_trajA_Region1, LRPol_stdev_trajA_Region1))
    print("LRPol_Region1 calculation TrajB average: {:3.3f} ± {:3.3f}".format(LRPol_ave_trajB_Region1, LRPol_stdev_trajB_Region1))
    print("LRPol_Region1 calculation TrajAB average: {:3.3f} ± TBD".format(LRPol_ave_trajAB_Region1))
    #Calculating correction per snapshot
    LRPolcorrdict_A = {}
    LRPolcorrdict_B = {}
    for b in LRPol_Arepsnaps_ABenergy_Region2:
        for c in repsnapsA:
            if b == c:
                LRPolcorrdict_A[b] = LRPol_Arepsnaps_ABenergy_Region2[b] - LRPol_Arepsnaps_ABenergy_Region1[b]
    for b in LRPol_Brepsnaps_ABenergy_Region2:
        for c in repsnapsB:
            if b == c:
                LRPolcorrdict_B[b] = LRPol_Brepsnaps_ABenergy_Region2[b] - LRPol_Brepsnaps_ABenergy_Region1[b]
    blankline()
    print("Dictionaries of corrections per snapshots:")
    print("LRPolcorrdict_A:", LRPolcorrdict_A)
    print("LRPolcorrdict_B", LRPolcorrdict_B)
    LRPolcorr_mean_A = statistics.mean(LRPolcorrdict_A.values())
    LRPolcorr_mean_B = statistics.mean(LRPolcorrdict_B.values())
    LRPolcorr_stdev_A = statistics.stdev(LRPolcorrdict_A.values())
    LRPolcorr_stdev_B = statistics.stdev(LRPolcorrdict_B.values())
    LRPolcorr_mean_AB = statistics.mean([LRPolcorr_mean_A, LRPolcorr_mean_B])
    blankline()
    print("Traj A: LRPolcorrection {:3.3f} ± {:3.3f} eV".format(LRPolcorr_mean_A, LRPolcorr_stdev_A))
    print("Traj B: LRPolcorrection {:3.3f} ± {:3.3f} eV".format(LRPolcorr_mean_B, LRPolcorr_stdev_B))
    print("Combined LRPolcorrection {:3.3f} eV".format(LRPolcorr_mean_AB))
    blankline()
    print_time_rel_and_tot(CheckpointTime, beginTime,'LRPol')
    CheckpointTime = time.time()
    #Going up to snaps dir again
    os.chdir('..')
else:
    LRPol_ave_trajAB=0; LRPol_stdev_trajAB=0; LRPolcorr_mean_AB=0
    LRPol_ave_trajB=0; LRPol_stdev_trajB=0; LRPolcorr_mean_B=0
    LRPol_ave_trajA=0; LRPol_stdev_trajA=0; LRPolcorr_mean_A=0
    LRPol_ave_trajA_Region1=0; LRPol_stdev_trajA_Region1=0;
    LRPol_ave_trajA_Region2=0; LRPol_stdev_trajA_Region2=0
    LRPol_ave_trajB_Region1=0; LRPol_stdev_trajB_Region1=0;
    LRPol_ave_trajB_Region2=0; LRPol_stdev_trajB_Region2=0
    LRPol_ave_trajAB_Region1=0; LRPol_stdev_trajAB_Region1=0;
    LRPol_ave_trajAB_Region2=0; LRPol_stdev_trajAB_Region2=0
blankline()


if GasCorrection:
    ####################
    # Gas calculations #
    ####################
    print_line_with_mainheader("Gas calculations: Low-Level and High-Level Theory")

    gaslistA = ['gas-molA.c']
    gaslistB = ['gas-molB.c']
    os.mkdir('Gas-calculations')
    os.chdir('./Gas-calculations')
    shutil.copyfile('../' + 'gas-molA.c', './' + 'gas-molA.c')
    shutil.copyfile('../' + 'gas-molB.c', './' + 'gas-molB.c')
    print("Current dir:", os.getcwd())

    print("Doing Gas calculations. Creating inputfiles...")
    print("gaslistA:", gaslistA); print("gaslistB:", gaslistB)
    gaslist=gaslistA+gaslistB
    identifiername='_Gas_LL'
    #create_AB_inputfiles_onelist
    gasinpfiles_LL = create_AB_inputfiles_ORCA(solute_atoms, [], solvsphere, gaslist,orcasimpleinput_LL,
                                                   orcablockinput_LL, solventunitcharges, identifiername)
    identifiername='_Gas_HL'
    gasinpfiles_HL = create_AB_inputfiles_ORCA(solute_atoms, [], solvsphere, gaslist,orcasimpleinput_HL,
                                                   orcablockinput_HL, solventunitcharges, identifiername)

    print("Created inputfiles:")
    print(gasinpfiles_LL)
    print(gasinpfiles_HL)
    # RUN GASCORRECTION INPUTFILES
    print_line_with_subheader1("Running Gas calculations at LL theory")
    print(BC.WARNING, "LL-theory:", orcasimpleinput_LL, BC.END)
    run_inputfiles_in_parallel_AB(gasinpfiles_LL)
    # HL Gas phase would later be run using OpenMPI parallelization
    print_line_with_subheader1("Running Gas calculations at HL theory")
    print(BC.WARNING,"HL-theory:", orcasimpleinput_HL,BC.END)
    #run_inputfiles_in_parallel_AB(gasinpfiles_HL)
    run_orca_SP_ORCApar(gasinpfiles_HL[0], nprocs=NumCores)
    run_orca_SP_ORCApar(gasinpfiles_HL[1], nprocs=NumCores)
    #GRAB output
    gasA_stateA_LL=finalenergiesgrab('gas-molA_StateAB_Gas_LL.out')[0]
    gasA_stateB_LL=finalenergiesgrab('gas-molA_StateAB_Gas_LL.out')[1]
    gasA_VIE_LL=(gasA_stateB_LL-gasA_stateA_LL)*constants.hartoeV
    gasB_stateA_LL=finalenergiesgrab('gas-molB_StateAB_Gas_LL.out')[0]
    gasB_stateB_LL=finalenergiesgrab('gas-molB_StateAB_Gas_LL.out')[1]
    gasB_VIE_LL=(gasA_stateB_LL-gasB_stateB_LL)*constants.hartoeV
    gasAB_AIE_LL=(gasB_stateB_LL-gasA_stateA_LL)*constants.hartoeV
    print("gasA_VIE_LL:", gasA_VIE_LL)
    print("gasB_VIE_LL:", gasB_VIE_LL)
    print("gasAB_AIE_LL:", gasAB_AIE_LL)
    blankline()

    gasA_stateA_HL=finalenergiesgrab('gas-molA_StateAB_Gas_HL.out')[0]
    gasA_stateB_HL=finalenergiesgrab('gas-molA_StateAB_Gas_HL.out')[1]
    gasA_VIE_HL=(gasA_stateB_HL-gasA_stateA_HL)*constants.hartoeV
    gasB_stateA_HL=finalenergiesgrab('gas-molB_StateAB_Gas_HL.out')[0]
    gasB_stateB_HL=finalenergiesgrab('gas-molB_StateAB_Gas_HL.out')[1]
    gasB_VIE_HL=(gasA_stateB_HL-gasB_stateB_HL)*constants.hartoeV
    gasAB_AIE_HL=(gasB_stateB_HL-gasA_stateA_HL)*constants.hartoeV
    print("gasA_VIE_HL:", gasA_VIE_HL)
    print("gasB_VIE_HL:", gasB_VIE_HL)
    print("gasAB_AIE_HL:", gasAB_AIE_HL)
    blankline()
    print_time_rel_and_tot(CheckpointTime, beginTime,'Gas calculations')
    CheckpointTime = time.time()
    # Going up to snaps dir again
    os.chdir('..')
else:
    gasAB_AIE_LL=0; gasAB_AIE_HL=0;
    gasB_VIE_LL=0; gasB_VIE_HL=0;
    gasA_VIE_LL=0; gasA_VIE_HL=0


#PRINT FINAL OUTPUT
if PrintFinalOutput==True:
    if calctype=="redox":
        print_line_with_mainheader("FINAL OUTPUT: REDOX")
        blankline()
        print_line_with_subheader1("Trajectory A")

        print_redox_output_state("A", solvsphere, orcasimpleinput_LL, orcasimpleinput_HL, solvsphere.snapshotsA, ave_trajA, stdev_trajA,
                                 repsnap_ave_trajA, repsnap_stdev_trajA, repsnaplistA, Bulk_ave_trajA, Bulk_stdev_trajA, Bulkcorr_mean_A,
                                 SRPol_ave_trajA, SRPol_stdev_trajA, SRPolcorr_mean_A, LRPol_ave_trajA_Region1, LRPol_ave_trajA_Region2,
                                 LRPol_stdev_trajA_Region1, LRPol_stdev_trajA_Region2, LRPolcorr_mean_A, gasA_VIE_LL, gasA_VIE_HL)
        print_line_with_subheader1("Trajectory B")
        print_redox_output_state("A", solvsphere, orcasimpleinput_LL, orcasimpleinput_HL, solvsphere.snapshotsB, ave_trajB, stdev_trajB,
                                 repsnap_ave_trajB, repsnap_stdev_trajB, repsnaplistB, Bulk_ave_trajB, Bulk_stdev_trajB, Bulkcorr_mean_B,
                                 SRPol_ave_trajB, SRPol_stdev_trajB, SRPolcorr_mean_B, LRPol_ave_trajB_Region1, LRPol_ave_trajB_Region2,
                                 LRPol_stdev_trajB_Region1, LRPol_stdev_trajB_Region2, LRPolcorr_mean_B, gasB_VIE_LL, gasB_VIE_HL)
        print_line_with_subheader1("Final Average")
        print_redox_output_state("AB", solvsphere, orcasimpleinput_LL, orcasimpleinput_HL, solvsphere.snapshots, ave_trajAB, stdev_trajAB,
                                 repsnap_ave_trajAB, repsnap_stdev_trajAB, repsnaplistAB, Bulk_ave_trajAB, Bulk_stdev_trajAB, Bulkcorr_mean_AB,
                                 SRPol_ave_trajAB, SRPol_stdev_trajAB, SRPolcorr_mean_AB, LRPol_ave_trajAB_Region1, LRPol_ave_trajAB_Region2,
                                 LRPol_stdev_trajAB_Region1, LRPol_stdev_trajAB_Region2, LRPolcorr_mean_AB, gasAB_AIE_LL, gasAB_AIE_HL)

        blankline()
blankline()
blankline()
print_time_rel_and_tot(CheckpointTime, beginTime)
print_solvshell_footer()