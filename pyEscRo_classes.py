# -*- coding: utf-8 -*-
"""
Created on Wed Nov 11 16:25:36 2017

@author: Jake Meador
"""

import arcpy, os

class Building:
    def __init__(self, name, gdb):
        self.name = name
        self.geodatabase = gdb
        # paths to feature classes stored in building's dataset
        self.dataset = os.path.join(gdb, name)
        self.room_points = os.path.join(self.dataset, "room_points")
        self.exits = os.path.join(self.dataset, "exits")
        self.stairs = os.path.join(self.dataset, "stairs")
        self.aisles = os.path.join(self.dataset, "aisles")
        self.rooms = os.path.join(self.dataset, "rooms")
        self.floors = os.path.join(self.dataset, "floors")
        self.building = os.path.join(self.dataset, "building")
        self.floor_lines = os.path.join(self.dataset, "floor_lines")
        self.network = os.path.join(self.dataset, name+"_ND")
    
    # creates network dataset from template
    # *** IMPORTANT *** template must be stored in same folder as file geodatabase
    def create_nd(self):
        folder = os.path.dirname(self.geodatabase)
        template = os.path.join(folder, "templates", "ND_template")
        arcpy.na.CreateNetworkDatasetFromTemplate(template, self.dataset)
        arcpy.na.BuildNetwork(self.network)


class EndPoint:
    # parameters on creation are building object, room or exit number, and parent shapefile
    # number should be a string (i.e. 123A, EXIT1, etc.)
    def __init__(self, _bldg, num):
        self.building = _bldg
        self.number = num
        # name of the room (i.e. men's restroom)
        self.name = ""
        # floor where the endpoint is located
        self.floor = 1
        # Potentially could need to be changed in future iterations depending 
        # on application. As of now, floors are assumed to be separated by 
        # 3 meters, and the ground floor is at an elevation of 107 meters.
        self.height = 104 + (self.floor * 3)
        # shapefile of origin of data
        self.parent = ""
        # shapefile of endpoint separated from parent shapefile
        self.shapefile = ""
    
    # separates the entry for the endpoint from the rest of the entries and creates
    # a shapefile for it; separate shapefile is needed for later processes
    def isolate_entry(self):
        self.shapefile = os.path.join(self.building.name, self.parent+"_"+self.number)
        
        if not arcpy.Exists(self.shapefile):
            arcpy.Select_analysis(self.parent, self.shapefile, "RMNumber = '"+self.number+"'")


class Room(EndPoint):
    def __init__(self, _bldg, num):
        super().__init__(_bldg, num)
        self.parent = self.building.room_points
        # will contain list of routes leading from the room to each of the exits
        self.routes = []
    
    # Retrieves the name and floor number of the room from database
    def fetch_data(self):
        where_clause = "RMNumber = '"+self.number+"'"
        with arcpy.da.SearchCursor(self.parent, where_clause, ['RoomName', 'Floor']) as cursor:
            for row in cursor:
                self.name = row[0]
                self.floor = row[1]
    
    # Creates Exit objects for all the exits in the building and returns them
    def create_exits(self):
        self.exits = []
        with arcpy.da.SearchCursor(self.building.exits, ['RMNumber']) as cursor:
            for row in cursor:
                self.exits.append(Exit(self.building, row[0]))
    

class Exit(EndPoint):
    def __init__(self, _bldg, num):
        super().__init__(_bldg, num)
        self.parent = self.building.exits
        self.name = "EXIT"
    

class Route:
    # all parameters are objects from above classes
    def __init__(self, _bldg, _room, _exit):
        self.building = _bldg
        self.room = _room
        self.exit = _exit
        # will store the length of the route
        self.length = 0.0
        # if the route is the best of all the routes for the room, self.best will be True
        self.best = False
        self.rank = 0
        self.dataset_shapefile = "room"+self.room.number+"_"+self.exit.number+"_dataset"
        self.stops_source = os.path.join(self.building.name, "room"+self.room.number+"_"+self.exit.number+"_stops")
    
    # Generates route between self.room and self.exit, and stores its length
    def create_layer(self):
        result = arcpy.na.MakeRouteAnalysisLayer(self.building.network, self.dataset_shapefile)
        
        self.layer_object = result.getOutput(0)
        self.sublayer_names = arcpy.na.GetNAClassNames(self.layer_object)
        self.stops_layer_name = self.sublayer_names["Stops"]
        
        arcpy.Merge_management([self.room.shapefile, self.exit.shapefile], self.stops_source)
        arcpy.na.AddLocations(self.layer_object, self.stops_layer_name, self.stops_source, "", "")
        arcpy.na.Solve(self.layer_object, "SKIP", "CONTINUE")
        
        self.route_layer = self.layer_object.listLayers("Routes")[0]
        
        cursor = arcpy.SearchCursor(self.route_layer)
        for row in cursor:
            self.length = float(row.getValue("Shape_Length"))
    
    # Defines the symbology for the layer depending on its rank and adds the
    # layer to the current map.
    def save_layer(self, group):
        aprx = arcpy.mp.ArcGISProject("current")
        aprxMap = aprx.listMaps()[0]
        
        if self.best == True:
            size = 14.0
            rgb_color = [0, 255, 0, 80]
            position = "TOP"
        else:
            size = 10.0
            rgb_color = [255, 0, 0, 80]
            position = "BOTTOM"
        
        self.sym = self.route_layer.symbology
        self.sym.renderer.symbol.applySymbolFromGallery("Tube", 0)
        self.sym.renderer.symbol.size = size
        self.sym.renderer.symbol.color = {'RGB': rgb_color}
        
        self.route_layer.symbology = self.sym
        aprxMap.addLayerToGroup(group, self.route_layer, position)