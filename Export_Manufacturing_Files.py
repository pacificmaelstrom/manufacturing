import adsk.core, adsk.fusion, adsk.cam, traceback
import os
import time
from datetime import datetime
import shutil
import logging

# Configure logging
logging.basicConfig(filename='export_manufacturing_files.log', level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')


# FUSION PART NAME DEPENDENCIES OVERVIEW:
# parts must be named with the right codes for parsing by this program

# Part naming guidelines and examples:

#     !!! Underscore character "_" is reserved for the program exporter. 
#     !!! All fusion components must be either: 
#         > A sheet metal part (underscore optional)
#         > A part using a defined code with underscore "MJF_" for example
#         > A part using a dynamic supplier code "stepperonline_" which will be parsed
#         > An assembly component with no bodies (only other components)

#     Our goal is to reduce painful duplicate information as much as possible using automation.
#     We avoid hard-to-maintain or understand part numbering systems in favor of
#     > The model is the only source of truth
#     > Generate BOM and manufacturing files dynamically from the model
#     Part names are long-text descriptive part names for easy readability
    
#     But: 
#     We will prepend manufacturing codes in order to easily extract this info

#     Example 1:
#     "steering servo arm screw" 
#         becomes:
#     "9200394A30_steering servo arm screw"
#         which parses into:
#     McMaster CSV: 9200394A30, Qty ? , steering servo arm screw
    
#     Example 2: 
#     "steering servo arm"
#         becomes
#     "MJF_steering servo arm"
#         which parses into
#     MJF 3D printing from external supplier, Export STL file "Qty1_MJF_steering servo arm.stl"
#         note how the STL file name contains quantity, material and description for easy ordering
#         The quantity will be analized and added automatically
        
#     All files will be distributed into folders organized by manufacturing process for easy ordering

    
# PART CODE DESCRIPTIONS:
# We have several types of parts:
# Sheet metal parts (determine sheetmetal property) 
#     > create DXF of flat pattern (thats simple)
#     > Optional codes "0.63AL_" or "0.118PC_" for material callout

# Plastic parts start with "FDM_" or "MJF_" etc
#     > Export as STL files for 3D printing
#     > Auto assign plastic material to these parts?

# Metal machining parts start with "CNC_"
#     > Export as STEP file (none of these yet...)

# Mcmaster parts start with "<mcmaster part no>_"
#     > In mcmaster list with quantity and description (description being what follows the _)

# Open builds parts start with "OB_"
#     > In open builds list.. "OB_low profile M5x20mm"

# We can auto assign material properties to each part (so we don't have to sync that)
# We can add other manufacturing codes and back-update this information with the right coding

# Key idea: all info clearly visible in the model not hidden behind properties screens etc...

# TODO:
# >> Will invest extra time in makeing sure the model is structured for this
# >> changing the model will propagate to manufacturing
# >> USE PREVIOUS MODEL VERSIONS for exporting the compatible parts... 
#         > we could do a geometry comparison to validate if a part has changed since last version
#         > Need to consider whatever internal fusion 360 IDs may exist

def run(context):
    ui = None

    try:
        app = adsk.core.Application.get()
        ui  = app.userInterface
        design = app.activeProduct

        if not isinstance(design, adsk.fusion.Design):
            logging.error('No active Fusion design')
            ui.messageBox('No active Fusion design', 'Error')
            return

        rootComp = design.rootComponent
        allOccs = rootComp.allOccurrences

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        export_folder = r'C:\Users\pacif\OneDrive\Desktop\FPVAIRSOFTSRC\manufacturing\Export_Manufacturing_Files\Coyote'
        
        try:
            shutil.rmtree(export_folder)
        except Exception as e:
            logging.warning(f"Error removing {export_folder}, did it exist? Exception: {e}")

        export_folder = export_folder

        if not os.path.exists(export_folder):
            os.makedirs(export_folder)

        logging.info("Export started...")

        #sheet metal parts
        dxf_list = set()
        dxf_bom = "<sheet metal dxf>\n"

        #3d printed parts
        stl_list = set()
        stl_bom = "<3d printed parts>\n"

        #specific supplier lists
        mcmaster_list = set()
        mcmaster_bom = "<mcmaster>\n"

        #all other parts
        supplier_flags = set()

        #export branching#flags
        flag_multibody = False
        flag_export_dxf = True
        flag_export_mcmaster = True
        flag_export_dynamic = True
        flag_export_stl = True

        if flag_multibody: logging.info("flag_multibody")
        if flag_export_dxf: logging.info("flag_dxf")
        if flag_export_mcmaster: logging.info("flag_mcmaster")
        if flag_export_dynamic: logging.info("flag_dynamic")

        #first check bodies of root component
        for j in range(0, rootComp.bRepBodies.count):
            body = rootComp.bRepBodies.item(j)
            logging.warning(f"Found body at root component level '{body.name}'")

        #Design files export
        for i in range(0, rootComp.allOccurrences.count):
            occ = rootComp.allOccurrences.item(i)
            
            # Get the associated component.
            comp = occ.component

            #iterate once through for each component name
            if True:
                #check for multibody parts
                if flag_multibody and comp.bRepBodies.count > 1:
                    logging.info(f"{comp.name} #multibody count: {comp.bRepBodies.count}")

                # Sheet metal exporting
                if flag_export_dxf:
                    dxf_folder = os.path.join(export_folder, 'dxf')
                    if not os.path.exists(dxf_folder):
                        os.makedirs(dxf_folder)
                    for j in range(0, comp.bRepBodies.count):
                        body = comp.bRepBodies.item(j)
                        if body.isSheetMetal:
                            if (comp.name not in dxf_list):
                                dxf_list.add(comp.name) #first occurance
                                dxf_bom += "qty1_" + comp.name + ".dxf\n"

                                # Check if the component has a flat pattern
                                if hasattr(comp, 'flatPattern') and comp.flatPattern:
                                    # Export flat pattern as DXF
                                    exportMgr = design.exportManager
                                    file_name = os.path.join(dxf_folder, "qty1_" +comp.name + '.dxf')
                                    dxfOptions = exportMgr.createDXFFlatPatternExportOptions(filename=file_name, flatPattern=comp.flatPattern)
                                    exportMgr.execute(dxfOptions)
                                    logging.info(f"Exported DXF: {file_name}")
                            else: #second occurance or more, only change qty
                                #find in log and in files
                                start_pos = dxf_bom.find(comp.name)
                                original_start = start_pos
                                #backup until newline character or 0
                                end_pos = start_pos
                                while dxf_bom[end_pos] != "\n":
                                    end_pos += 1
                                while dxf_bom[start_pos] != "\n":
                                    start_pos -= 1
                                #export line fron start pos to "\n"
                                line = dxf_bom[start_pos+1 : end_pos + 1]  #""my_string[a:b] gives you a substring from index a to (b - 1).
                                #find original quantity and add 1
                                prefix = dxf_bom[start_pos+1: original_start-1]
                                quantity = int(prefix.removeprefix("qty").removesuffix("_"))
                                quantity += 1
                                #replace the line with new line
                                dxf_bom = dxf_bom.replace(line, (f"qty{quantity}_" + comp.name + '.dxf' + "\n"))

                                #also rename the exported part file!
                                current_name = line.removesuffix("\n")
                                current_file_name = os.path.join(dxf_folder, current_name)
                                new_name = f"qty{quantity}_" + comp.name + '.dxf'
                                new_file_name = os.path.join(dxf_folder, new_name)
                                os.rename(current_file_name, new_file_name)
                                logging.info(f"Renamed DXF: {current_file_name} to {new_file_name}")

                #first identify a tagged part by the underscore character
                #if the file exists, change its name to update the quantity?
                if "_" in comp.name:
                    names = comp.name.split("_")

                    #mcmaster parts start with numbers, all other parts have supplier tag
                    try:
                        if names[0][0] in "0123456789": #see if part no

                            mcmaster_folder = os.path.join(export_folder, 'mcmaster')
                            if not os.path.exists(mcmaster_folder):
                                os.makedirs(mcmaster_folder)

                            if names[0] not in mcmaster_list:
                                mcmaster_list.add(names[0]) #initial one
                                #part exclusions
                                #exclude sheet metal hardware
                                if flag_export_mcmaster:
                                    description = comp.name.removeprefix((names[0] + "_")).replace("\t", " ").replace("\n", "")
                                    mcmaster_bom += names[0] + "\t1\t" + description + "\n"
                                    logging.info(f"Added McMaster part: {names[0]} with description: {description}")

                            else: #second occurance or more, only change qty
                                #find in log and in files
                                if flag_export_mcmaster:
                                    #from the part name go forward until \t 
                                    try:
                                        start_pos = mcmaster_bom.find(names[0]) #find the MM part no
                                        end_pos = start_pos
                                        while mcmaster_bom[end_pos] != "\n":
                                            end_pos += 1
                                        while mcmaster_bom[start_pos] != "\n":
                                            start_pos -= 1
                                        #export line fron start pos to "\n"
                                        line = mcmaster_bom[start_pos+1 : end_pos+1] #"my_string[a:b] gives you a substring from index a to (b - 1)."

                                        #search the line for the number and change it
                                        end_num = 0
                                        start_num = 0
                                        while line[start_num] != "\t":
                                            start_num += 1
                                        end_num = start_num + 1
                                        while line[end_num] != "\t":
                                            end_num += 1
                                        #export line fron start pos to "\t"
                                        quantity = int(line[start_num : end_num+1].removeprefix("\t").removesuffix("\t"))
                                        quantity += 1
                                        #now find the line
                                        #backup until newline character or 0
                                        
                                        #replace the line with new line
                                        description = comp.name.removeprefix((names[0] + "_")).replace("\t", " ").replace("\n", "")
                                        mcmaster_bom = mcmaster_bom.replace(line, (names[0] + f"\t{quantity}\t" + description + "\n"), 1)
                                        logging.info(f"Updated McMaster part: {names[0]} with new quantity: {quantity}")
                                    except Exception as e:
                                        logging.error(f"Error processing duplicate McMaster part: {comp.name}. Exception: {e}")
                    except Exception as e:
                        logging.error(f"Error with index[0][0]: {comp.name}. Exception: {e}")

                    #stl parts start with stl tags, not implemented
                    if (names[0].lower() == "mjf") or (names[0].lower() == "fdm") or (names[0].lower() == "sla"):

                        stl_folder = os.path.join(export_folder, 'stl')
                        if not os.path.exists(stl_folder):
                            os.makedirs(stl_folder)

                        stl_list.add(comp.name)

                        #MJF (high load 3d print)
                        if flag_export_stl:
                            #MJF (high load 3d print)
                            if comp.name.lower().startswith("mjf_"): #mjf parts
                                quantity = 0
                                exportMgr = design.exportManager
                                xfolder = os.path.join(export_folder, 'mjf')
                                if not os.path.exists(xfolder):
                                    os.makedirs(xfolder)
                                file_name = os.path.join(stl_folder, f"qty{quantity}_" + comp.name + '.stl')
                                stlOptions = exportMgr.createSTLExportOptions(comp, file_name)
                                exportMgr.execute(stlOptions)
                                logging.info(f"Exported STL: {file_name}")
                            
                            #FDM (standard layerd 3d print)
                            if comp.name.lower().startswith("fdm_"): #fdm parts
                                quantity = 0
                                exportMgr = design.exportManager
                                xfolder = os.path.join(export_folder, 'fdm')
                                if not os.path.exists(xfolder):
                                    os.makedirs(xfolder)
                                file_name = os.path.join(stl_folder, f"qty{quantity}_" + comp.name + '.stl')
                                stlOptions = exportMgr.createSTLExportOptions(comp, file_name)
                                exportMgr.execute(stlOptions)
                                logging.info(f"Exported STL: {file_name}")

                            #SLA (standard layerd 3d print)
                            if comp.name.lower().startswith("sla_"): #fdm parts
                                quantity = 0
                                exportMgr = design.exportManager
                                xfolder = os.path.join(export_folder, 'sla')
                                if not os.path.exists(xfolder):
                                    os.makedirs(xfolder)
                                file_name = os.path.join(stl_folder, f"qty{quantity}_" + comp.name + '.stl')
                                stlOptions = exportMgr.createSTLExportOptions(comp, file_name)
                                exportMgr.execute(stlOptions)
                                logging.info(f"Exported STL: {file_name}")

                    #dynamic parts parts start with supplier tag
                    if (names[0] in stl_list) or (names[0] in mcmaster_list): #see if part already considered
                        pass
                    else:
                        #if its not, extract the tag and see if it already exists
                        if flag_export_dynamic:
                            logging.info(comp.name)

                            if not names[0] in supplier_flags:
                                supplier_flags.add(names[0])

                                supplier_folder = os.path.join(export_folder, names[0])
                                if not os.path.exists(supplier_folder):
                                    os.makedirs(supplier_folder)

                                #create a supplier file
                                supplier_file_path = os.path.join(supplier_folder, (names[0] + '.txt'))
                                with open(supplier_file_path, 'w') as supplier_file:
                                    supplier_file.write(comp.name + "\n")
                                    logging.info(f"Created supplier file: {supplier_file_path}")
                            else:
                                #supplier already exists
                                supplier_folder = os.path.join(export_folder, names[0])
                                #create a supplier file
                                supplier_file_path = os.path.join(supplier_folder, (names[0] + '.txt'))
                                with open(supplier_file_path, 'a') as supplier_file:
                                    supplier_file.write(comp.name + "\n")
                                    logging.info(f"Updated supplier file: {supplier_file_path}")

                #part does not have flag and is not sheetmetal
                else: 
                    if comp.bRepBodies.count > 0:
                        #filter out sheet metal bodies
                        body = comp.bRepBodies.item(0)
                        if not body.isSheetMetal:
                            logging.info(f"[?: {comp.name}]")

        # Write logMessage to a text file
        log_file_path = os.path.join(export_folder, 'export_names.txt')
        with open(log_file_path, 'w') as log_file:
            log_file.write(f"timestamp: {timestamp}")
            log_file.write(dxf_bom)
            log_file.write(mcmaster_bom)
            logging.info(f"Export names written to: {log_file_path}")

        mcmaster_bom_file_path = os.path.join(export_folder, 'mcmaster_bom.txt')
        with open(mcmaster_bom_file_path, 'w') as log_file:
            log_file.write(mcmaster_bom)
            logging.info(f"McMaster BOM written to: {mcmaster_bom_file_path}")
        
        dxf_bom_file_path = os.path.join(export_folder, 'dxf_bom.txt')
        with open(dxf_bom_file_path, 'w') as log_file:
            log_file.write(dxf_bom)
            logging.info(f"DXF BOM written to: {dxf_bom_file_path}")

        ui.messageBox(f"Exports: {log_file_path}")

    except Exception as e:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))
            logging.error(f"Failed: {traceback.format_exc()}")

            # Write logMessage to a text file
            log_file_path = os.path.join(export_folder, 'export_names.txt')
            with open(log_file_path, 'w') as log_file:
                log_file.write(dxf_bom)
                log_file.write(mcmaster_bom)
                logging.info(f"Export names written to: {log_file_path} after failure")

def get_component_tree(occurrence):
    tree = []
    while occurrence:
        tree.append(occurrence.name)
        occurrence = occurrence.assemblyContext
    return ' -> '.join(reversed(tree))


