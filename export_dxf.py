#Function I want to implement into button

import adsk.core, adsk.fusion, adsk.cam, traceback

def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        design = app.activeProduct
        if not design:
            ui.messageBox('No active Fusion design', 'No Design')
            return

        # Get the root component of the active design.
        rootComp = design.rootComponent
        #box = rootComp.bRepBody.boundingBox


        # Iterate over any bodies in the root component.
        totalVolume = 0

        for j in range(0, rootComp.bRepBodies.count):
            body = rootComp.bRepBodies.item(j)

            # Get the volume of the current body and add it to the total.
            totalVolume += body.volume
            length = body.boundingBox.maxPoint.x - body.boundingBox.minPoint.x
            width = body.boundingBox.maxPoint.y - body.boundingBox.minPoint.y
            height = body.boundingBox.maxPoint.z - body.boundingBox.minPoint.z

        # Iterate through all of the occurrences in the assembly.
        for i in range(0, rootComp.allOccurrences.count):
            occ = rootComp.allOccurrences.item(i)

            # Get the associated component.
            comp = occ.component

            # Iterate over all of the bodies within the component.
            for j in range(0, comp.bRepBodies.count):
                body = comp.bRepBodies.item(j)

                # Get the volume of the current body and add it to the total.
                totalVolume += body.volume
                length = body.boundingBox.maxPoint.x - body.boundingBox.minPoint.x
                width = body.boundingBox.maxPoint.y - body.boundingBox.minPoint.y
                height = body.boundingBox.maxPoint.z - body.boundingBox.minPoint.z

        # Format a string to display the volume using the default distance units.
        resultLength = design.unitsManager.formatInternalValue(length, design.unitsManager.defaultLengthUnits, True)
        resultWidth = design.unitsManager.formatInternalValue(width, design.unitsManager.defaultLengthUnits, True)
        resultHeight = design.unitsManager.formatInternalValue(height, design.unitsManager.defaultLengthUnits, True)
        ui.messageBox('The length of the part is: ' + resultLength + "\n" + "The width of the part is: "
         + resultWidth + "\n" + "The height of the part is: " + resultHeight)
    except:
        if ui:
            ui.messageBox('Failed:\n{}'.format(traceback.format_exc()))