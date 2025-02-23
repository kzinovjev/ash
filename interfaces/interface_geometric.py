import numpy as np
import os
import shutil
import time

import ash.constants
from ash.modules.module_QMMM import QMMMTheory
from ash.interfaces.interface_OpenMM import OpenMMTheory
from ash.modules.module_coords import print_coords_all,print_coords_for_atoms,print_internal_coordinate_table,write_XYZ_for_atoms,write_xyzfile
from ash.functions.functions_general import ashexit, blankline,BC,print_time_rel,print_line_with_mainheader
#import ash
from ash.modules.module_coords import check_charge_mult

################################################
# Interface to geomeTRIC Optimization Library
################################################

#Wrapper function around GeomeTRICOptimizerClass
def geomeTRICOptimizer(theory=None, fragment=None, charge=None, mult=None, coordsystem='tric', frozenatoms=None, constraintsinputfile=None, constraints=None, 
                       constrainvalue=False, maxiter=50, ActiveRegion=False, actatoms=None, convergence_setting=None, conv_criteria=None,
                       print_atoms_list=None):
    print_line_with_mainheader("geomeTRICOptimizer")
    timeA=time.time()
    optimizer=GeomeTRICOptimizerClass(theory=theory, fragment=fragment, charge=charge, mult=mult, coordsystem=coordsystem, frozenatoms=frozenatoms, 
                        constraintsinputfile=constraintsinputfile, constraints=constraints, 
                       constrainvalue=constrainvalue, maxiter=maxiter, ActiveRegion=ActiveRegion, actatoms=actatoms, 
                       convergence_setting=convergence_setting, conv_criteria=conv_criteria,
                       print_atoms_list=print_atoms_list)
    finalenergy = optimizer.run()
    print_time_rel(timeA, modulename='geomeTRIC', moduleindex=1)
    return finalenergy


# Class for optimization. Used to be standalone function. Made into class for more flexibility: micro-iterative QM/MM Opt, TruncPC QM/MM Opt, Excited-state optimizer etc.
class GeomeTRICOptimizerClass:
        def __init__(self,theory=None, fragment=None, charge=None, mult=None, coordsystem='tric', frozenatoms=None, constraintsinputfile=None, constraints=None, 
                       constrainvalue=False, maxiter=50, ActiveRegion=False, actatoms=None, convergence_setting=None, conv_criteria=None,
                       print_atoms_list=None):
            """
            Wrapper function around geomeTRIC code. Take theory and fragment info from ASH
            Supports frozen atoms and bond/angle/dihedral constraints in native code. Use frozenatoms and bondconstraints etc. for this.
            New feature: Active Region for huge systems. Use ActiveRegion=True and provide actatoms list.
            Active-atom coords (e.g. only QM region) are only provided to geomeTRIC during optimization while rest is frozen.
            Needed as discussed here: https://github.com/leeping/geomeTRIC/commit/584869707aca1dbeabab6fe873fdf139d384ca66#diff-2af7dd72b77dac63cea64c052a549fe0
            """
            print("Creating optimizer object")

            ######################
            #INITIAL CHECKS
            ######################
            if fragment==None:
                print("geomeTRIC requires fragment object")
                ashexit()
            try:
                import geometric
                self.geometric=geometric
            except:
                blankline()
                print(BC.FAIL,"geomeTRIC module not found!", BC.END)
                print(BC.WARNING,"Either install geomeTRIC using pip:\n conda install geometric\n or \n pip install geometric\n or manually from Github (https://github.com/leeping/geomeTRIC)", BC.END)
                ashexit(code=9)

            #Check charge/mult
            self.charge, self.mult = check_charge_mult(charge, mult, theory.theorytype, fragment, "geomeTRICOptimizer", theory=theory)

            if fragment.numatoms == 1:
                print("System has 1 atoms.")
                print("Doing single-point energy calculation instead")
                energy = ash.Singlepoint(fragment=fragment, theory=theory, charge=charge, mult=mult)
                return energy

            #Active region and coordsystem
            if ActiveRegion == True and coordsystem == "tric":
                #TODO: Look into this more
                print("Activeregion true and coordsystem = tric are not compatible")
                print("Switching to HDLC")
                coordsystem='hdlc'

            if actatoms==None:
                actatoms=[]
            if frozenatoms==None:
                frozenatoms=[]

            #Defining some attributes
            self.actatoms=actatoms
            self.frozenatoms=frozenatoms
            self.maxiter=maxiter
            self.constraints=constraints
            self.theory=theory
            self.coordsystem=coordsystem
            self.fragment=fragment
            self.ActiveRegion=ActiveRegion
            ######################

            ######################
            #SOME PRINTING
            ######################
            blankline()
            print(BC.WARNING, "Doing geometry optimization on fragment. Formula: {} Label: {} ".format(fragment.prettyformula,fragment.label), BC.END)
            print("Coordinate system: ", self.coordsystem)
            print("Max iterations: ", self.maxiter)
            print("Constraints: ", self.constraints)

            #Clean-up before we begin
            tmpfiles=['geometric_OPTtraj.log','geometric_OPTtraj.xyz','geometric_OPTtraj_Full.xyz','geometric_OPTtraj_QMregion.xyz', 'optimization_energies.log',
                'constraints.txt','initialxyzfiletric.xyz','geometric_OPTtraj.tmp','dummyprefix.tmp','dummyprefix.log','Fragment-optimized.ygg','Fragment-optimized.xyz',
                'Fragment-optimized_Active.xyz','geometric_OPTtraj-PDB.pdb']
            for tmpfile in tmpfiles:
                try:
                    shutil.rmtree(tmpfile)
                except FileNotFoundError:
                    pass
                except NotADirectoryError:
                    os.remove(tmpfile)
                else:
                    pass
    
            #NOTE: We are now sorting actatoms and qmatoms list both here and in QM/MM object
            #: Alternatively we could sort the actatoms list and qmatoms list in QM/MM object before doing anything. Need to check carefully though....
            #if is_integerlist_ordered(actatoms) is False:
            #    print("Problem. Actatoms list is not sorted in ascending order. Please sort this list (and possibly qmatoms list also))")
            #    ashexit()
            

            ########################################
            #CONSTRAINTS
            ########################################
            # For QM/MM we need to convert full-system atoms into active region atoms 
            #constraints={'bond':[[8854,37089]]}
            if self.ActiveRegion == True:
                if constraints != None:
                    print("Constraints set. Active region true")
                    print("User-defined constraints (fullsystem-indices):", self.constraints)
                    constraints=constraints_indices_convert(self.constraints,self.actatoms)
                    print("Converting constraints indices to active-region indices")
                    print("Constraints (actregion-indices):", self.constraints)

            #Delete constraintsfile unless asked for
            if constraintsinputfile is None:
                try:
                    os.remove('constraints.txt')
                except:
                    pass
            #Getting individual constraints from constraints dict
            if constraints is not None:
                try:
                    bondconstraints = self.constraints['bond']
                except:
                    bondconstraints = None
                try:
                    angleconstraints = self.constraints['angle']
                except:
                    angleconstraints = None
                try:
                    dihedralconstraints = self.constraints['dihedral']
                except:
                    dihedralconstraints = None
            else:
                bondconstraints=None
                angleconstraints=None
                dihedralconstraints=None
            ########################################


            #What atoms to print in outputfile in each opt-step. Example choice: QM-region only
            #If not specified then active-region or all-atoms
            if print_atoms_list == None:
                #Print-atoms list not specified. What to do: 
                if self.ActiveRegion == True:
                    #If QM/MM object then QM-region:
                    #if theory.__class__.__name__ == "QMMMTheory":
                    if isinstance(theory,QMMMTheory):
                        print("Theory class: QMMMTheory")
                        print("Will by default print only QM-region in output (use print_atoms_list option to change)")
                        print_atoms_list=self.theory.qmatoms
                    else:
                        #Print actatoms since using Active Region (can be too much)
                        print_atoms_list=self.actatoms
                else:
                    #No act-region. Print all atoms
                    print_atoms_list=fragment.allatoms
            self.print_atoms_list=print_atoms_list
            print("Atomlist to print in output:", self.print_atoms_list)


            #ActiveRegion option where geomeTRIC only sees the QM part that is being optimized
            if self.ActiveRegion == True:
                #Sorting list, otherwise trouble
                self.actatoms.sort()
                print("Active Region option Active. Passing only active-region coordinates to geomeTRIC.")
                print("Active atoms list:", self.actatoms)
                print("Number of active atoms:", len(self.actatoms))

                #Check that the actatoms list does not contain atom indices higher than the number of atoms
                largest_atom_index=max(self.actatoms)
                if largest_atom_index >= fragment.numatoms:
                    print(BC.FAIL,f"Found active-atom index ({largest_atom_index}) that is larger or equal (>=) than the number of atoms of system ({fragment.numatoms})!",BC.END)
                    print(BC.FAIL,"This does not make sense. Please provide a correct actatoms list. Exiting.",BC.END)
                    ashexit()
                #Get active region coordinates and elements
                actcoords, actelems = fragment.get_coords_for_atoms(self.actatoms)
                
                #Writing act-region coords (only) of ASH fragment to disk as XYZ file and reading into geomeTRIC
                write_xyzfile(actelems, actcoords, 'initialxyzfiletric')
                mol_geometric_frag=self.geometric.molecule.Molecule("initialxyzfiletric.xyz")
            else:
                #Write coordinates from ASH fragment to disk as XYZ-file and reading into geomeTRIC
                fragment.write_xyzfile("initialxyzfiletric.xyz")
                mol_geometric_frag=self.geometric.molecule.Molecule("initialxyzfiletric.xyz")
                    
                    
            ########################################
            # CONSTRAINTS
            ########################################
            #Define constraints provided. Write constraints.txt file
            #Frozen atom option. Only for small systems. Not QM/MM etc.
            self.constraintsfile=None
            if len(frozenatoms) > 0 :
                print("Writing frozen atom constraints")
                self.constraintsfile='constraints.txt'
                with open("constraints.txt", 'a') as confile:
                    confile.write('$freeze\n')
                    for frozat in frozenatoms:
                        #Changing from zero-indexing (ASH) to 1-indexing (geomeTRIC)
                        frozenatomindex=frozat+1
                        confile.write('xyz {}\n'.format(frozenatomindex))
            #Bond constraints
            if bondconstraints is not None :
                self.constraintsfile='constraints.txt'
                with open("constraints.txt", 'a') as confile:
                    if constrainvalue is True:
                        confile.write('$set\n')            
                    else:
                        confile.write('$freeze\n')
                    for bondpair in bondconstraints:
                        #Changing from zero-indexing (ASH) to 1-indexing (geomeTRIC)
                        #print("bondpair", bondpair)
                        if constrainvalue is True:
                            confile.write('distance {} {} {}\n'.format(bondpair[0]+1,bondpair[1]+1, bondpair[2] ))                    
                        else:    
                            confile.write('distance {} {}\n'.format(bondpair[0]+1,bondpair[1]+1))
            #Angle constraints
            if angleconstraints is not None :
                self.constraintsfile='constraints.txt'
                with open("constraints.txt", 'a') as confile:
                    if constrainvalue is True:
                        confile.write('$set\n')            
                    else:
                        confile.write('$freeze\n')
                    for angleentry in angleconstraints:
                        #Changing from zero-indexing (ASH) to 1-indexing (geomeTRIC)
                        #print("angleentry", angleentry)
                        if constrainvalue is True:
                            confile.write('angle {} {} {} {}\n'.format(angleentry[0]+1,angleentry[1]+1,angleentry[2]+1,angleentry[3] ))
                        else:
                            confile.write('angle {} {} {}\n'.format(angleentry[0]+1,angleentry[1]+1,angleentry[2]+1))
            if dihedralconstraints is not None:
                self.constraintsfile='constraints.txt'
                with open("constraints.txt", 'a') as confile:
                    if constrainvalue is True:
                        confile.write('$set\n')            
                    else:
                        confile.write('$freeze\n')
                    for dihedralentry in dihedralconstraints:
                        #Changing from zero-indexing (ASH) to 1-indexing (geomeTRIC)
                        #print("dihedralentry", dihedralentry)
                        if constrainvalue is True:
                            confile.write('dihedral {} {} {} {} {}\n'.format(dihedralentry[0]+1,dihedralentry[1]+1,dihedralentry[2]+1,dihedralentry[3]+1, dihedralentry[4] ))
                        else:
                            confile.write('dihedral {} {} {} {}\n'.format(dihedralentry[0]+1,dihedralentry[1]+1,dihedralentry[2]+1,dihedralentry[3]+1))
            if constraintsinputfile is not None:
                self.constraintsfile=constraintsinputfile

            ########################################
            #Dealing with convergence criteria
            ########################################
            if convergence_setting is None or convergence_setting == 'ORCA':
                #default
                if conv_criteria is None:
                    self.conv_criteria = {'convergence_energy' : 5e-6, 'convergence_grms' : 1e-4, 'convergence_gmax' : 3.0e-4, 'convergence_drms' : 2.0e-3, 
                            'convergence_dmax' : 4.0e-3 }
            elif convergence_setting == 'Chemshell':
                self.conv_criteria = {'convergence_energy' : 1e-6, 'convergence_grms' : 3e-4, 'convergence_gmax' : 4.5e-4, 'convergence_drms' : 1.2e-3, 
                                'convergence_dmax' : 1.8e-3 }
            elif convergence_setting == 'ORCA_TIGHT':
                self.conv_criteria = {'convergence_energy' : 1e-6, 'convergence_grms' : 3e-5, 'convergence_gmax' : 1.0e-4, 'convergence_drms' : 6.0e-4, 
                            'convergence_dmax' : 1.0e-3 }
            elif convergence_setting == 'GAU':
                self.conv_criteria = {'convergence_energy' : 1e-6, 'convergence_grms' : 3e-4, 'convergence_gmax' : 4.5e-4, 'convergence_drms' : 1.2e-3, 
                            'convergence_dmax' : 1.8e-3 }
            elif convergence_setting == 'GAU_TIGHT':
                self.conv_criteria = {'convergence_energy' : 1e-6, 'convergence_grms' : 1e-5, 'convergence_gmax' : 1.5e-5, 'convergence_drms' : 4.0e-5, 
                                'convergence_dmax' : 6e-5 }
            elif convergence_setting == 'GAU_VERYTIGHT':
                self.conv_criteria = {'convergence_energy' : 1e-6, 'convergence_grms' : 1e-6, 'convergence_gmax' : 2e-6, 'convergence_drms' : 4.0e-6, 
                                'convergence_dmax' : 6e-6 }        
            elif convergence_setting == 'SuperLoose':
                        self.conv_criteria = { 'convergence_energy' : 1e-1, 'convergence_grms' : 1e-1, 'convergence_gmax' : 1e-1, 'convergence_drms' : 1e-1, 
                            'convergence_dmax' : 1e-1 }
            else:
                print("Unknown convergence setting. Exiting...")
                ashexit()

            print("User convergence_setting:", convergence_setting)
            print("Convergence criteria:", self.conv_criteria)

            #Defining ASHengineclass engine object containing geometry and theory. ActiveRegion boolean passed.
            #Also now passing list of atoms to print in each step.
            self.ashengine = ASHengineclass(mol_geometric_frag,theory, ActiveRegion=self.ActiveRegion, actatoms=self.actatoms, print_atoms_list=self.print_atoms_list, 
                charge=self.charge, mult=self.mult, conv_criteria=self.conv_criteria, fragment=self.fragment)
            #Defining args object, containing engine object
            self.final_geometric_args=geomeTRICArgsObject(self.ashengine,self.constraintsfile,coordsys=self.coordsystem, maxiter=self.maxiter, conv_criteria=self.conv_criteria)

            print("")
        #Starting geomeTRIC run
        def run(self):
            print("Starting optimization")
            self.geometric.optimize.run_optimizer(**vars(self.final_geometric_args))
            time.sleep(1)
            blankline()
            print("geomeTRIC Geometry optimization converged in {} steps!".format(self.ashengine.iteration_count))
            blankline()

            #QM/MM: Doing final energy evaluation if Truncated PC option was on
            if isinstance(self.theory,QMMMTheory):
                if self.theory.TruncatedPC is True:
                    print("Truncated PC approximation was active. Doing final energy calculation with full PC environment")
                    self.theory.TruncatedPC=False
                    self.finalenergy, self.finalgrad = self.theory.run(current_coords=self.ashengine.full_current_coords, elems=self.fragment.elems, 
                        Grad=True, label='FinalIter', charge=self.charge, mult=self.mult)
                else:
                    self.finalenergy=self.ashengine.energy
            else:
                #Updating energy and coordinates of ASH fragment before ending
                self.finalenergy=self.ashengine.energy


            self.fragment.set_energy(self.finalenergy)
            print("Final optimized energy:",  self.finalenergy)

            #Replacing coordinates in fragment
            self.fragment.replace_coords(self.fragment.elems,self.ashengine.full_current_coords, conn=False)
            
            #Writing out fragment file and XYZ file
            self.fragment.print_system(filename='Fragment-optimized.ygg')
            self.fragment.write_xyzfile(xyzfilename='Fragment-optimized.xyz')
            if self.ActiveRegion==True:
                write_XYZ_for_atoms(self.fragment.coords, self.fragment.elems, self.actatoms, "Fragment-optimized_Active")

            #Printing internal coordinate table
            print_internal_coordinate_table(self.fragment,actatoms=self.print_atoms_list)
            blankline()
            #Now returning final energy
            #TODO: Return dictionary of energy, gradient, coordinates etc, coordinates along trajectory ??
            
            return self.finalenergy

class geomeTRICArgsObject:
    def __init__(self,eng,constraintsfile, coordsys, maxiter, conv_criteria):
        self.coordsys=coordsys
        self.maxiter=maxiter

        #self.convergence_criteria=conv_criteria
        #self.converge=conv_criteria
        #Setting these to be part of kwargs that geometric reads
        self.convergence_energy = conv_criteria['convergence_energy']
        self.convergence_grms = conv_criteria['convergence_grms']
        self.convergence_gmax = conv_criteria['convergence_gmax']
        self.convergence_drms = conv_criteria['convergence_drms']
        self.convergence_dmax = conv_criteria['convergence_dmax']
        
        
        self.prefix='geometric_OPTtraj'
        self.input='dummyinputname'
        self.constraints=constraintsfile
        #Created log.ini file here. Missing from pip installation for some reason?
        #Storing log.ini in ash dir
        path = os.path.dirname(ash.__file__)
        self.logIni=path+'/log.ini'
        self.customengine=eng

#Defining ASH engine class used to communicate with geomeTRIC
class ASHengineclass:
    def __init__(self,geometric_molf, theory, ActiveRegion=False, actatoms=None,print_atoms_list=None, charge=None, mult=None, conv_criteria=None, fragment=None):
        #Defining M attribute of engine object as geomeTRIC Molecule object
        self.M=geometric_molf
        #Defining theory from argument
        self.theory=theory
        self.ActiveRegion=ActiveRegion
        #Defining current_coords for full system (not only act region)
        self.full_current_coords=[]
        #Manual iteration count
        self.iteration_count=0
        #Defining initial E
        self.energy = 0
        #Active atoms
        self.actatoms=actatoms
        #Print-list atoms (set above)
        self.print_atoms_list=print_atoms_list
        self.charge=charge
        self.mult=mult
        self.conv_criteria=conv_criteria
        self.fragment=fragment

    #TODO: geometric will regularly do ClearCalcs in an optimization
    def clearCalcs(self):
        print("geomeTRIC: ClearCalcs.")

    #Writing out trajectory file for full system in case of ActiveRegion. Note: Actregion coordinates are done done by GeomeTRIC
    def write_trajectory_full(self):
        print("Writing trajectory for Full system to file: geometric_OPTtraj_Full.xyz")
        with open("geometric_OPTtraj_Full.xyz", "a") as trajfile:
            trajfile.write(str(self.fragment.numatoms)+"\n")
            trajfile.write("Iteration {} Energy {} \n".format(self.iteration_count,self.energy))
            for el,cor in zip(self.fragment.elems,self.full_current_coords):
                trajfile.write(el + "  " + str(cor[0]) + " " + str(cor[1]) + " " + str(cor[2]) +
                            "\n")
    #QM/MM: Writing out trajectory file for QM-region if QM/MM.
    def write_trajectory_qmregion(self):
        print("Writing trajectory for QM-region to file: geometric_OPTtraj_QMregion.xyz")
        with open("geometric_OPTtraj_QMregion.xyz", "a") as trajfile:
            trajfile.write(str(len(self.theory.qmatoms))+"\n")
            trajfile.write("Iteration {} Energy {} \n".format(self.iteration_count,self.energy))
            qm_coords, qm_elems = self.fragment.get_coords_for_atoms(self.theory.qmatoms)
            for el,cor in zip(qm_elems,qm_coords):
                trajfile.write(el + "  " + str(cor[0]) + " " + str(cor[1]) + " " + str(cor[2]) +
                            "\n")
    def write_energy_logfile(self):
        #QM/MM: Writing out logfile containing QM-energy, MM-energy, QM/MM-energy
        print("Writing logfile with energies: optimization_energies.log")
        with open("optimization_energies.log", "a") as trajfile:
            if self.iteration_count == 0:
                trajfile.write(f"Iteration QM-energy       (Eh) MM-Energy (Eh)  QM/MM-Energy (Eh)\n")
            trajfile.write(f"{self.iteration_count}         {self.theory.QMenergy} {self.theory.MMenergy} {self.theory.QM_MM_energy}\n")

    def write_pdbtrajectory(self):
        print("Writing PDB-trajectory to file: geometric_OPTtraj-PDB.pdb")
        pdbtrajectoryfile="geometric_OPTtraj-PDB.pdb"
        # Get OpenMM positions
        #STILL problem with PBC
        state = self.theory.mm_theory.simulation.context.getState(getEnergy=False, getPositions=True, getForces=False,enforcePeriodicBox=True)
        newpos = state.getPositions()
        self.theory.mm_theory.openmm.app.PDBFile.writeFile(self.theory.mm_theory.topology, newpos, file=open(pdbtrajectoryfile, 'a'))

    #Defining calculator
    def calc(self,coords,tmp, read_data=None):
        #Note: tmp and read_data not used. Needed for geomeTRIC version compatibility
        print("Convergence criteria:", self.conv_criteria)
        print()
        #Updating coords in object
        #Need to combine with rest of full-system coords
        timeA=time.time()
        self.M.xyzs[0] = coords.reshape(-1, 3) * ash.constants.bohr2ang
        #print_time_rel(timeA, modulename='geometric ASHcalc.calc reshape', moduleindex=2)
        timeA=time.time()
        currcoords=self.M.xyzs[0]
        #Special act-region (for QM/MM) since GeomeTRIC does not handle huge system and constraints
        if self.ActiveRegion==True:
            #Defining full_coords as original coords temporarily
            #full_coords = np.array(fragment.coords)
            full_coords = self.fragment.coords
            
            #Replacing act-region coordinates in full_coords with coords from currcoords
            for act_i,curr_i in zip(self.actatoms,currcoords):
                full_coords[act_i] = curr_i
            #print_time_rel(timeA, modulename='geometric ASHcalc.calc replacing act-region', moduleindex=2)
            timeA=time.time()
            self.full_current_coords = full_coords
            
            #Write out fragment with updated coordinates for the purpose of doing restart
            self.fragment.replace_coords(self.fragment.elems, self.full_current_coords, conn=False)
            self.fragment.print_system(filename='Fragment-currentgeo.ygg')
            self.fragment.write_xyzfile(xyzfilename="Fragment-currentgeo.xyz")
            #print_time_rel(timeA, modulename='geometric ASHcalc.calc replacecoords and printsystem', moduleindex=2)
            timeA=time.time()

            #PRINTING TO OUTPUT SPECIFIC GEOMETRY IN EACH GEOMETRIC ITERATION (now: self.print_atoms_list)
            print("Current geometry (Å) in step {} (print_atoms_list region)".format(self.iteration_count))
            
            print("-------------------------------------------------")
            
            #print_atoms_list
            #Previously act: print_coords_for_atoms(self.full_current_coords, fragment.elems, self.actatoms)
            print_coords_for_atoms(self.full_current_coords, self.fragment.elems, self.print_atoms_list)
            #print_time_rel(timeA, modulename='geometric ASHcalc.calc printcoords atoms', moduleindex=2)
            timeA=time.time()
            print("Note: Only print_atoms_list region printed above")
            #Request Engrad calc for full system

            E, Grad = self.theory.run(current_coords=self.full_current_coords, elems=self.fragment.elems, charge=self.charge, mult=self.mult, Grad=True, label='Iter'+str(self.iteration_count))
            #print_time_rel(timeA, modulename='geometric ASHcalc.calc theory.run', moduleindex=2)
            timeA=time.time()
            #Trim Full gradient down to only act-atoms gradient
            Grad_act = np.array([Grad[i] for i in self.actatoms])
            #print_time_rel(timeA, modulename='geometric ASHcalc.calc trim full gradient', moduleindex=2)
            timeA=time.time()
            self.energy = E

            print("Writing trajectory for Active Region to file: geometric_OPTtraj.xyz")

            #Now writing trajectory for full system
            self.write_trajectory_full()
            
            #Case QM/MM:
            if isinstance(self.theory,QMMMTheory):
                #Writing trajectory for QM-region only
                self.write_trajectory_qmregion()
                #Writing logfile with QM,MM and QM/MM energies
                self.write_energy_logfile()

                #Case MMtheory is OpenMM: Write out PDB-trajectory via OpenMM
                if isinstance(self.theory.mm_theory,OpenMMTheory):
                    self.write_pdbtrajectory()

            #print_time_rel(timeA, modulename='geometric ASHcalc.calc writetraj full', moduleindex=2)
            timeA=time.time()
            self.iteration_count += 1
            return {'energy': E, 'gradient': Grad_act.flatten()}
        else:
            self.full_current_coords=currcoords
            #PRINTING ACTIVE GEOMETRY IN EACH GEOMETRIC ITERATION
            #print("Current geometry (Å) in step {}".format(self.iteration_count))
            print("Current geometry (Å) in step {} (print_atoms_list region)".format(self.iteration_count))
            print("---------------------------------------------------")
            #Disabled: print_coords_all(currcoords, fragment.elems)
            print_coords_for_atoms(currcoords, self.fragment.elems, self.print_atoms_list)
            print("")
            print("Note: printed only print_atoms_list (this is not necessary all atoms) ")
            E,Grad=self.theory.run(current_coords=currcoords, elems=self.M.elem, charge=self.charge, mult=self.mult,
                                Grad=True, label='Iter'+str(self.iteration_count))
            self.iteration_count += 1
            self.energy = E
            return {'energy': E, 'gradient': Grad.flatten()}


#Function Convert constraints indices to actatom indices
def constraints_indices_convert(con,actatoms):
    try:
        bondcons=con['bond']
    except KeyError:
        bondcons=[]
    try:
        anglecons=con['angle']
    except KeyError:
        anglecons=[]
    try:
        dihedralcons=con['dihedral']
    except KeyError:
        dihedralcons=[]
    #Looping over constraints-class (bond,angle-dihedral)
    #list-item:
    for bc in bondcons:
        bc[0]=fullindex_to_actindex(bc[0],actatoms)
        bc[1]=fullindex_to_actindex(bc[1],actatoms)
    for ac in anglecons:
        ac[0]=fullindex_to_actindex(ac[0],actatoms)
        ac[1]=fullindex_to_actindex(ac[1],actatoms)
        ac[2]=fullindex_to_actindex(ac[2],actatoms)
    for dc in dihedralcons:
        dc[0]=fullindex_to_actindex(dc[0],actatoms)
        dc[1]=fullindex_to_actindex(dc[1],actatoms)
        dc[2]=fullindex_to_actindex(dc[2],actatoms)
        dc[3]=fullindex_to_actindex(dc[3],actatoms)
    return con


#Function to convert atom indices from full system to Active region. Used in case of QM/MM
#Single index case
def fullindex_to_actindex(fullindex,actatoms):
    actindex=actatoms.index(fullindex)
    return actindex