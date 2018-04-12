# -*- coding: utf-8 -*-
"""
Created on Wed Nov 11 16:24:07 2017

@author: Jake Meador
"""

import arcpy, os
import pyEscRo_classes as pyEscRo

def main(parameters):
    # Inputs from ArcGIS, gdb is the geodatabase, bldg is the short name of the building,
    # and room_num is the string of the room number
    gdb = parameters[0].valueAsText
    bldg = parameters[1].valueAsText
    
    cur = arcpy.SearchCursor(os.path.join(gdb, bldg, "room_points"))
    
    for row in cur:
        room_num = row.getvalue("RMNumber")

        # setting the workspace to the geodatabase
        arcpy.env.workspace = gdb
        arcpy.env.overwriteOutput = True

        # create building object, room object, and exit objects
        building = pyEscRo.Building(bldg, gdb)
        room = pyEscRo.Room(building, room_num)
        room.create_exits()

        # checks to see if the network dataset exists; if it doesn't, it is created
        if not arcpy.Exists(building.network):
            building.create_nd()

        # separates room from other rooms into its own feature class
        room.isolate_entry()

        # separates exits individually into their own feature classes
        for e in room.exits:
            e.isolate_entry()

        # initialize lists for ordering
        routes = []
        lengths = []

        # creates route objects and appends them to list routes
        for ex in room.exits:
            r = pyEscRo.Route(building, room, ex)
            routes.append(r)

        # performs network analysis on created routes
        for route in routes:
            route.create_layer()
            if route.length != 0.0:
                lengths.append(route.length)

        # reorder list of lengths
        lengths.sort()

        # ranks routes by lengths, shortest first
        for route in routes:
            if route.length == 0.0:
                route.rank = 0
            else:
                route.rank = lengths.index(route.length)

            if route.rank == 1:
                route.best = True

        # stores routes in new order
        ordered_routes = [None]*len(routes)
        for i in routes:
            ordered_routes[i.rank] = i

        # adds an empty layer group to the map from a .lyrx file.
        # *** IMPORTANT *** "empty_group.lyrx" must be an empty layer group stored in the same folder as the file geodatabase
        empty_group = arcpy.mp.LayerFile(os.path.join(os.path.dirname(gdb), "templates", "empty_group.lyrx"))
        aprx = arcpy.mp.ArcGISProject("current")
        aprxMap = aprx.listMaps()[0]
        aprxMap.addLayer(empty_group, "TOP")
        group = aprxMap.listLayers("Routes")[0]
        group.name = "routes_group"

        # adds routes to map
        for obj in ordered_routes:
            try:
                obj.save_layer(group)
            except AttributeError:
                continue
