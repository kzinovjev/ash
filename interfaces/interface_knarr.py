#Non-intrusive interface to Knarr
#Assumes that Knarr directory exists inside ASH (for now at least)

import ash
from functions_general import blankline
import numpy as np
import sys
import os
import copy

#This makes Knarr part of python path
#Recommended way?
yggpath = os.path.dirname(ash.__file__)
sys.path.insert(0,yggpath+'/knarr')

from KNARRio.system_print import PrintHeader, PrintDivider, PrintCredit
from KNARRatom.utilities import InitializeAtomObject, InitializePathObject
from KNARRjobs.path import DoPathInterpolation
from KNARRio.io import ReadTraj
from KNARRjobs.neb import DoNEB
import KNARRatom.atom

#LOG of Knarr-code modifications
#1. Various python2 print-statements to print-functions changes
#2. Various additions of int() in order to get integer of division products (Python2/3 change)
#3. Made variable  calculator.ISCION = True . Bad idea?

#Knarr settings for path-generation, NEB and optimizer
#These will be the reasonable defaults that can be overridden by special keywords in Yggdrasill NEB object
#RB modified springconst from 10 to 5
# Changed "IDPP_RMS_F": 0.005    and "IDPP_MAX_F": 0.01
path_parameters = {"METHOD": "DOUBLE", "INTERPOLATION": "IDPP", "NIMAGES": 6,
              "INSERT_CONFIG": None, "IDPP_MAX_ITER": 200,
              "IDPP_SPRINGCONST": 5.0, "IDPP_TIME_STEP": 0.01,
              "IDPP_MAX_MOVE": 0.1, "IDPP_MAX_F": 0.03, "IDPP_RMS_F": 0.005}

neb_settings = {"PATH": "neb.xyz",
              "CLIMBING": True,
              "TANGENT": "IMPROVED",
              "SPRINGTYPE": "DISTANCE",
              "PERP_SPRINGTYPE": "",
              "ENERGY_WEIGHTED": True, "SPRINGCONST": 1.0, "SPRINGCONST2": 10.0,
              "MIN_RMSD": True, "REMOVE_EXTERNAL_FORCE": True,
              "FREE_END": False, "FREE_END_TYPE": 'PERP', "FREE_END_ENERGY": 0.0,
              "FREE_END_ENERGY2": 0.0, "FREE_END_KAPPA": 0.0,
              "CONV_TYPE": "ALL", "TOL_SCALE": 10, "TOL_MAX_FCI": 0.026, "TOL_RMS_FCI": 0.013,
              "TOL_MAX_F": 0.026, "TOL_RMS_F": 0.013, "TOL_TURN_ON_CI": 1.0,
              "ZOOM": False,
              "TOL_TURN_ON_ZOOM": 0.5,
              "REPARAM": 0, "TOL_REPARAM": 0.0,
              "INTERPOLATION_TYPE": "LINEAR",
              "AUTO_ZOOM": True, "ZOOM_OFFSET": 1, "ZOOM_ALPHA": 0.5,
              "RESTART_OPT_ON_CI": True,
              "LBFGS_REPARAM_ON_RESTART": False
              }

optimizer = {"OPTIM_METHOD": "LBFGS", "MAX_ITER": 1000, "TOL_MAX_FORCE": 0.01,
             "TOL_RMS_FORCE": 0.005, "TIME_STEP": 0.01, "MAX_MOVE": 0.1, "RESTART_ON_SCALING": True,
             "LBFGS_MEMORY": 20,
             "LBFGS_DAMP": 1.0,
             "FD_STEP": 0.001,
             "LINESEARCH": None}

#Path generator
def Knarr_pathgenerator(nebsettings,path_parameters,react,prod,ActiveRegion):
    sett = nebsettings
    type_of_method_string = path_parameters["METHOD"].upper()
    if type_of_method_string == "SINGLE":
        prod_is_needed = False
    elif type_of_method_string == "DOUBLE":
        prod_is_needed = True
    else:
        raise TypeError("Either choose single or double ended path generation")

    nim = path_parameters["NIMAGES"]
    path = InitializePathObject(nim, react)
    if prod_is_needed:
        # Check product
        if react.GetNDim() != prod.GetNDim():
            raise RuntimeError("Reactant / product do not match")
        if react.GetSymbols() != prod.GetSymbols():
            raise RuntimeError("Reactant / product do not match")
        path.SetConfig2(prod.GetCoords())

        # check insertion
        insertion = path_parameters["INSERT_CONFIG"]
        if insertion is not None:
            insertion = InitializeAtomObject(name="insertion", input_config=path_parameters["INSERT_CONFIG"],
                                             pbc=main_control["PBC"])
            if insertion.GetSymbols() != react.GetSymbols():
                raise ValueError("Insertion does not match reactant / product")
            path.SetInsertionConfig(insertion.GetCoords())
    else:
        prod = None

    #Setting path.twodee True  prevents RMSD alignment in pathgeneration
    if ActiveRegion is True:
        print("Using ActiveRegion in NEB. Turning off RMSD alignment in Path generation")
        path.twodee = True
        #print("path istwodee", path.IsTwoDee())
    DoPathInterpolation(path, path_parameters)

#Convert coordinates list to Knarr-type array
def coords_to_Knarr(coords):
    coords_xyz=[]
    for i in coords:
        coords_xyz.append([i[0]]);coords_xyz.append([i[1]]);coords_xyz.append([i[2]])
    coords_xyz_np=np.array(coords_xyz)
    return coords_xyz_np

#Wrapper around Yggdrasill object
class KnarrCalculator:
    def __init__(self,theory,fragment1,fragment2,runmode='serial',printlevel=None, ActiveRegion=False, actatoms=None,
                 full_fragment_reactant=None, full_fragment_product=None, numimages=None, FreeEnd=False ):
        self.FreeEnd=FreeEnd
        self.numimages=numimages
        self.printlevel=printlevel
        self.forcecalls=0
        self.iterations=0
        self.theory=theory
        #Yggdrasill fragments for reactant and product
        #Used for element list and keep track of full system if QM/MM
        self.fragment1=fragment1
        self.fragment2=fragment2
        #Full Yggdrasill fragments for reactant and product. Inactive part of reactant will be used for all images
        self.full_fragment_reactant=full_fragment_reactant
        self.full_fragment_product=full_fragment_product
        self.runmode=runmode
        self.ISCION=False
        self.ActiveRegion=ActiveRegion
        self.actatoms=actatoms
        print("self.actatoms:", self.actatoms)
        self.full_coords_images_dict={}
        self.energies_dict={}
    def Compute(self,path, list_to_compute=None):
        blankline()
        self.iterations+=1
        print("Calling KnarrCalculator.Compute")
        print("NEB iteration:", self.iterations)
        if list_to_compute is None:
            print("None. list_to_compute:", list_to_compute)
            list_to_compute=[]
        else:
            list_to_compute=list(list_to_compute)
        print("Computing images:", list_to_compute)

        #

        #print("self.iterations:", self.iterations)
        counter=0
        F = np.zeros(shape=(path.GetNDimIm() * path.GetNim(), 1))
        E = np.zeros(shape=(path.GetNim(), 1))
        numatoms=int(path.ndofIm/3)

        if self.runmode=='serial':
            for image_number in list_to_compute:
                print("Computing image: ", image_number)
                image_coords_1d = path.GetCoords()[image_number * path.ndimIm : (image_number + 1) * path.ndimIm]
                image_coords=np.reshape(image_coords_1d, (numatoms, 3))
                # Request Engrad calc
                #Todo: Reduce printlevel for QM-theory here. Means that printlevel needs to be uniform accross all theories
                #Todo: Use self.printlevel so that it can adjust from outside
                blankline()

                if self.ActiveRegion == True:
                    currcoords=image_coords
                    # Defining full_coords as original coords temporarily
                    #full_coords = self.full_fragment_reactant.coords
                    #Creating deep copy of reactant coordinates as it will be modified
                    full_coords = copy.deepcopy(self.full_fragment_reactant.coords)

                    # Replacing act-region coordinates with coords from currcoords

                    for i, c in enumerate(full_coords):
                        if i in self.actatoms:
                            # Silly. Pop-ing first coord from currcoords until done
                            curr_c, currcoords = currcoords[0], currcoords[1:]
                            full_coords[i] = curr_c
                    full_current_image_coords = full_coords

                    #List of all image-geometries (full coords)
                    #full_coords_images_list.append(full_current_image_coords)

                    self.full_coords_images_dict[image_number] = copy.deepcopy(full_current_image_coords)

                    #EnGrad calculation on full system
                    En_image, Grad_image_full = self.theory.run(current_coords=full_current_image_coords,
                                                                elems=self.full_fragment_reactant.elems, Grad=True)
                    print("Energy of image {} is : {}".format(image_number,En_image))
                    #Trim Full gradient down to only act-atoms gradient
                    Grad_image = np.array([Grad_image_full[i] for i in self.actatoms])

                    #Keeping track of energies for each image in a dict
                    self.energies_dict[image_number] = En_image

                else:
                    En_image, Grad_image = self.theory.run(current_coords=image_coords, elems=self.fragment1.elems, Grad=True)
                    #Keeping track of energies for each image in a dict
                    self.energies_dict[image_number] = En_image


                counter += 1
                #Energies array for all images
                E[image_number]=En_image
                #Forces array for all images
                #Todo: Check units
                F[image_number* path.ndimIm : (image_number + 1) * path.ndimIm] = -1 * np.reshape(Grad_image,(int(path.ndofIm),1))
        elif self.runmode=='parallel':
            print("parallel is not yet done")
            print("")
            exit()
        path.SetForces(F)
        path.SetEnergy(E)
        #Forcecalls
        path.AddFC(counter)
        blankline()

        print("NEB iteration done")
        print("Energies of images dict:", self.energies_dict)
        blankline()
        #Write out full MEP path in each NEB iteration.
        if self.ActiveRegion is True:
            #if len(list_to_compute) > 2:
            if self.iterations > 1:
                self.write_Full_MEP_Path(path, list_to_compute, E)

        #print("self.ISCION:", self.ISCION)
        if self.iterations > 3 :
            if self.ISCION is True:
                print('%4ls  %4s  %9ls %5ls %6ls %9ls %9ls %9ls %6ls' % ('it', 'dS', 'Energy', 'HEI', 'RMSF', 'MaxF', 'RMSF_CI', 'MaxF_CI', 'step'))
            else:
                print(' %4ls %4s  %9ls %5ls %7ls %9ls %8ls' % ('it', 'dS', 'Energy', 'HEI', 'RMSF', 'MaxF', 'step'))

    def write_Full_MEP_Path(self, path, list_to_compute, E):
        #Write out MEP for full coords in each iteration. Knarr writes out Active Part.
        if self.ActiveRegion is True:
            with open("knarr_MEP_FULL.xyz", "w") as trajfile:
                #Todo: This will fail if free_end=True
                #Todo: disable react and prod printing if free_end True

                #Writing reactant image. Only if FreeEnd is False (normal)
                if self.FreeEnd is False:
                    trajfile.write(str(self.full_fragment_reactant.numatoms) + "\n")
                    trajfile.write("Image 0. Energy: {} \n".format(self.energies_dict[0]))
                    for el, corr in zip(self.full_fragment_reactant.elems, self.full_fragment_reactant.coords):
                        trajfile.write(el + "  " + str(corr[0]) + " " + str(corr[1]) + " " + str(corr[2]) + "\n")

                #Writing all active images in this NEB iteration
                for imageid in list_to_compute:
                    #print("fc:", fc)
                    trajfile.write(str(self.full_fragment_reactant.numatoms) + "\n")
                    trajfile.write("Image {}. Energy: {} \n".format(imageid, E[imageid][0]))
                    #for el, cord in zip(self.full_fragment_reactant.elems, fc):
                    for el, cord in zip(self.full_fragment_reactant.elems, self.full_coords_images_dict[imageid]):
                        trajfile.write(el + "  " + str(cord[0]) + " " + str(cord[1]) + " " + str(cord[2]) + "\n")

                #Writing product image. Only if FreeEnd is False (normal)
                if self.FreeEnd is False:
                    trajfile.write(str(self.full_fragment_product.numatoms) + "\n")
                    trajfile.write("Image {} Energy: {} \n".format(self.numimages-1,self.energies_dict[self.numimages-1]))
                    for el, corp in zip(self.full_fragment_product.elems, self.full_fragment_product.coords):
                        trajfile.write(el + "  " + str(corp[0]) + " " + str(corp[1]) + " " + str(corp[2]) + "\n")


#Yggdrasill NEB function. Calls Knarr
def NEB(reactant=None, product=None, theory=None, images=None, interpolation=None, CI=None, free_end=None,
        conv_type=None, tol_scale=None, tol_max_fci=None, tol_rms_fci=None, tol_max_f=None, tol_rms_f=None,
        tol_turn_on_ci=None, ActiveRegion=False, actatoms=None, runmode='serial', printlevel=1,
        idpp_maxiter=None):

    if reactant==None or product==None or theory==None:
        print("You need to provide reactant and product fragment and a theory to NEB")
        exit()

    print("Launching Knarr program")
    blankline()
    PrintDivider()
    PrintDivider()
    PrintHeader()
    PrintCredit()
    PrintDivider()
    PrintDivider()
    numatoms = reactant.numatoms

    #Override some default settings if requested
    #Default is; NEB-CI, IDPP interpolation, 6 images
    if images is not None:
        path_parameters["NIMAGES"]=images
    if interpolation is not None:
        path_parameters["INTERPOLATION"]=interpolation
    if idpp_maxiter is not None:
        path_parameters["IDPP_MAX_ITER"] = idpp_maxiter
    if CI is not None:
        if CI is False:
            neb_settings["CLIMBING"]=False
    if free_end is not None:
        neb_settings["FREE_END"] = True
    if conv_type is not None:
        neb_settings["CONV_TYPE"] = conv_type
    if tol_scale is not None:
        neb_settings["TOL_SCALE"] = tol_scale
    if tol_max_fci is not None:
        neb_settings["TOL_MAX_FCI"] = tol_max_fci
    if tol_rms_fci is not None:
        neb_settings["TOL_RMS_FCI"] = tol_rms_fci
    if tol_max_f is not None:
        neb_settings["TOL_MAX_F"] = tol_max_f
    if tol_rms_f is not None:
        neb_settings["TOL_RMS_F"] = tol_rms_f
    if tol_turn_on_ci is not None:
        neb_settings["TOL_TURN_ON_CI"] = tol_turn_on_ci


    if ActiveRegion is True:
        print("Active Region feature active. Setting RMSD-alignment in NEB to false (required).")
        neb_settings["MIN_RMSD"] = False

    blankline()
    print("Active Knarr settings:")
    blankline()

    print("Interpolation path parameters:\n", path_parameters)
    blankline()
    print("NEB parameters:\n", neb_settings)
    blankline()
    print("Optimizer parameters:\n", optimizer)
    blankline()

    #Zero-valued constraints list. We probably won't use constraints for now
    constr = np.zeros(shape=(numatoms * 3, 1))

    #ActiveRegion feature
    if ActiveRegion==True:
        print("Active Region option Active. Passing only active-region coordinates to Knarr.")
        if actatoms is None:
            print("add actatoms argument to NEB for ActiveRegion True")
            exit(1)
        R_actcoords, R_actelems = reactant.get_coords_for_atoms(actatoms)
        P_actcoords, P_actelems = product.get_coords_for_atoms(actatoms)
        new_reactant = ash.Fragment(coords=R_actcoords, elems=R_actelems)
        new_product = ash.Fragment(coords=P_actcoords, elems=P_actelems)

        #Create Knarr calculator from Yggdrasill theory.
        calculator = KnarrCalculator(theory, fragment1=new_reactant, fragment2=new_product, runmode=runmode,
                                     ActiveRegion=True, actatoms=actatoms, full_fragment_reactant=reactant,
                                     full_fragment_product=product,numimages=images )

        # Symbols list for Knarr
        Knarr_symbols = [y for y in new_reactant.elems for i in range(3)]

        # New numatoms and constraints for active-region system
        numatoms = new_reactant.numatoms
        constr = np.zeros(shape=(numatoms * 3, 1))

        # Create KNARR Atom objects. Used in path generation
        react = KNARRatom.atom.Atom(coords=coords_to_Knarr(new_reactant.coords), symbols=Knarr_symbols, ndim=numatoms * 3,
                                    ndof=numatoms * 3, constraints=constr, pbc=False)
        prod = KNARRatom.atom.Atom(coords=coords_to_Knarr(new_product.coords), symbols=Knarr_symbols, ndim=numatoms * 3,
                                   ndof=numatoms * 3, constraints=constr, pbc=False)


    else:
        #Create Knarr calculator from Yggdrasill theory
        calculator = KnarrCalculator(theory, fragment1=reactant, fragment2=product,
                                     ActiveRegion=False, runmode=runmode,numimages=images)

        # Symbols list for Knarr
        Knarr_symbols = [y for y in reactant.elems for i in range(3)]

        # Create KNARR Atom objects. Used in path generation
        react = KNARRatom.atom.Atom(coords=coords_to_Knarr(reactant.coords), symbols=Knarr_symbols, ndim=numatoms * 3,
                                    ndof=numatoms * 3, constraints=constr, pbc=False)
        prod = KNARRatom.atom.Atom(coords=coords_to_Knarr(product.coords), symbols=Knarr_symbols, ndim=numatoms * 3,
                                   ndof=numatoms * 3, constraints=constr, pbc=False)


    # Generate path via Knarr_pathgenerator. ActiveRegion used to prevent RMSD alignment if doing actregion QM/MM etc.
    Knarr_pathgenerator(neb_settings, path_parameters, react, prod, ActiveRegion)
    blankline()
    print("Initial path generation done!")
    print("Reading initial path")
    #Reading initial path from XYZ file. Hardcoded as knarr_path.xyz
    rp, ndim, nim, symb = ReadTraj("knarr_path.xyz")
    path = InitializePathObject(nim, react)
    path.SetCoords(rp)

    print("Starting NEB")

    #Setting printlevel of theory during E+Grad steps  1=very-little, 2=more, 3=lots, 4=verymuch
    print("NEB printlevel is:", printlevel)
    theory.printlevel=printlevel
    print("Theory print level set to:", theory.printlevel)
    if theory.__class__.__name__ == "QMMMTheory":
        theory.qm_theory.printlevel = printlevel
        theory.mm_theory.printlevel = printlevel

    #Now starting NEB from path object, using neb_settings and optimizer settings
    DoNEB(path, calculator, neb_settings, optimizer)

    #Todo: Check if DoNeb converged or not??

    #Getting saddlepoint-structure and energy if CI-NEB
    if neb_settings["CLIMBING"] is True:
        if ActiveRegion == True:
            print("Getting saddlepoint geometry and creating new fragment for Full system")
            print("Has not been confirmed to work...")
            #Finding CI coords and energy
            CI = np.argmax(path.GetEnergy())
            saddle_coords_1d=path.GetCoords()[CI * path.GetNDimIm():(CI + 1) * path.GetNDimIm()]
            saddle_coords=np.reshape(saddle_coords_1d, (numatoms, 3))
            saddle_energy = path.GetEnergy()[CI]

            #Combinining frozen region with optimized active-region for saddle-point
            # Defining full_coords as original coords temporarily
            full_saddleimage_coords = copy.deepcopy(reactant.coords)
            # Replacing act-region coordinates with coords from currcoords
            for i, c in enumerate(saddle_coords):
                if i in actatoms:
                    # Silly. Pop-ing first coord from currcoords until done
                    curr_c, saddle_coords = saddle_coords[0], saddle_coords[1:]
                    full_saddleimage_coords[i] = curr_c

            #Creating new Yggdrasill fragment for Full Saddle-point geometry
            Saddlepoint_fragment = ash.Fragment(coords=full_saddleimage_coords, elems=reactant.elems, connectivity=reactant.connectivity)
            Saddlepoint_fragment.set_energy(saddle_energy)
            #Adding atomtypes and charges if present.
            Saddlepoint_fragment.update_atomcharges(reactant.atomcharges)
            Saddlepoint_fragment.update_atomtypes(reactant.atomtypes)

            #Writing out Saddlepoint fragment file and XYZ file
            Saddlepoint_fragment.print_system(filename='Saddlepoint-optimized.ygg')
            Saddlepoint_fragment.write_xyzfile(xyzfilename='Saddlepoint-optimized.xyz')

        else:
            #Finding CI coords and energy
            CI = np.argmax(path.GetEnergy())
            saddle_coords_1d=path.GetCoords()[CI * path.GetNDimIm():(CI + 1) * path.GetNDimIm()]
            saddle_coords=np.reshape(saddle_coords_1d, (numatoms, 3))
            saddle_energy = path.GetEnergy()[CI]
            #Creating new Yggdrasill fragment
            Saddlepoint_fragment = ash.Fragment(coords=saddle_coords, elems=reactant.elems, connectivity=reactant.connectivity)
            Saddlepoint_fragment.set_energy(saddle_energy)
            #Writing out Saddlepoint fragment file and XYZ file
            Saddlepoint_fragment.print_system(filename='Saddlepoint-optimized.ygg')
            Saddlepoint_fragment.write_xyzfile(xyzfilename='Saddlepoint-optimized.xyz')


    print('KNARR successfully terminated')
    blankline()
    print("Please consider citing the following paper if you found the NEB module (from Knarr) useful: To be added")
    if neb_settings["CLIMBING"] is True:
        return Saddlepoint_fragment