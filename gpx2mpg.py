#!/usr/bin/python

import sys, re, math
import urllib2 as urllib
from PIL import Image, ImageDraw #The Python Imaging Library
from cStringIO import StringIO #Allows us to open URLs directly into memory
import subprocess #Allows up to pipe files directly to the command line

def GPX_to_Tiles(fn, zoomLevel, rate):
	
	#Define if we need to buffer to the tiles around the current tile
	#This is used for allowing us to move the center of the tile
	addBuffer = True
	
	#Open the GPX file
	inf = open(fn)
	
	#Default the size of the tiles
	Tile_X = 256
	Tile_Y = 256
	Tiles = []
	tilePoints = []
	
	#Extract the points from the GPX file
	#TODO: Use an XML Parser instead of a GREP
	#TODO include the times in here so we can make a better video using the actual times
	expr = re.compile("<trkpt ") 
	
	print "Analyzing %s" % (fn)
	#Loop through the File, and write out the values!
	for line in inf:
		match = expr.search(line)
		if match != None:
			line_items = line.split("\"")
			curLat = float(line_items[1])
			curLon = float(line_items[3])
			curTile = deg2num(curLat, curLon, zoomLevel)
			Tiles.append(curTile)
			
			if addBuffer:
				#Loop through the adjacent tiles
				orig_X = curTile[0]
				orig_Y = curTile[1]
				for X in range(orig_X-1,orig_X+2): 
					for Y in range(orig_Y-1,orig_Y+2):
						if ((X == orig_X and Y == orig_Y)==False):
							Tiles.append([X, Y])

			#Determine the Tile and the point on the tile
			tilePoints.append([curTile, [curLat, curLon]])
	
	#Download the Tiles
	imgTiles = downloadTiles(Tiles, zoomLevel)
	
	#Create the Video
	createVideo(tilePoints, imgTiles, zoomLevel, fn, rate)
	
def downloadTiles(Tiles, zoomLevel):
	cleanTiles = removeDups(Tiles)
	imgTiles = []
	print "Downloading %i Tiles" % (len(cleanTiles))
	tileCount = 0
	for Tile in cleanTiles:
		tileCount +=1
		print "Tile %i of %i" % (tileCount, len(cleanTiles))
		#Define a few URLs where to get the tiles
		#URL = "http://tile.stamen.com/terrain-background/%i/%i/%i.jpg" % (zoomLevel, Tile[0], Tile[1])
		#URL = "http://%s.tile.openstreetmap.org/%i/%i/%i.png" % ("c", zoomLevel, Tile[0], Tile[1])
		#URL = "http://ec2-50-19-205-250.compute-1.amazonaws.com/tiles/%i/%i/%i.png" % (zoomLevel, Tile[0], Tile[1])
		URL = "http://tile1.toposm.com/us/jpeg90/%i/%i/%i.jpg"  % (zoomLevel, Tile[0], Tile[1])

		img_tile_file = urllib.urlopen(URL)
		img_tile_temp = StringIO(img_tile_file.read())
		ImgTile = Image.open(img_tile_temp)
		#print Tile[0], Tile[1]
		#ImgTile = Image.open("test1.png")
		imgTiles.append([Tile, ImgTile])

	return imgTiles
	
def createVideo(tilePoints, imgTiles, zoomLevel, filename, rate):
	#Define some initial variables
	imgSize = (256, 256)
	markerPath = "./placemark_circle.png"
	tileIndex=0
	
	#Aspect Ratio will probably just become a parameter at some point
	videoSizeWide = (imgSize[0],int(imgSize[1]*(9.0/16.0))) #16:9 aspect ratio
	videoSizeStd  = (imgSize[0],int(imgSize[1]*(3.0/4.0))) # 4:3 aspect ratio
	videoSize = videoSizeWide
	
	#Create the Blank and the Video
	tile = Image.new("RGBA",(imgSize[0],imgSize[1])) #Create a space for a new Tile
	video = VideoSink((videoSize[0],videoSize[1]), rate, "rgba", "%s"%(filename)) #Define the Video
	
	#Create the Marker
	marker = Image.open(markerPath)
	marker = marker.convert("RGBA")
	
	for PointOnTiles in tilePoints:
		#Extract the variables
		curTile = PointOnTiles[0]
		curLat = PointOnTiles[1][0]
		curLon = PointOnTiles[1][1]
		
		#Determine the PastePoint
		PastePoint = pointToPixel(curLat, curLon, curTile, zoomLevel, 1, imgSize)
		
		#Search for the associated Image
		for ImgTile in imgTiles:
			if ImgTile[0] == curTile:
				#tile.paste(ImgTile[1]) #Create a New Tile Each Time
				tile = ImgTile[1] #Keep all points on the map (draw a line)
		
		#Add the marker to the map
		tile.paste(marker,PastePoint)
		tile = tile.convert("RGBA")
		
		#Centering and Tile Buffering (optional)
		processedTile = processPoints(curTile, imgTiles, tilePoints, tileIndex, imgSize, videoSize, zoomLevel)
		#tile = processedTile		
		tileIndex = tileIndex+1
		print "Processing Tile %i of %i (%i%%)" % (tileIndex,len(tilePoints), int((tileIndex*100)/(len(tilePoints))))
		
		#Add the license and author information
		# http://wiki.openstreetmap.org/wiki/License
		draw=ImageDraw.Draw(processedTile)
		draw.text((videoSize[0]-75,videoSize[1]-10), "CC-BY-SA 2.0", "BLACK")
		draw.text((2,videoSize[1]-10), "OpenStreetMap", "BLACK")
		
		#Append the tile to the Video
		video.AppendImage(processedTile)
		#break
	#Close the video
	processedTile.save("bigTile.png", "PNG")
	video.CloseVideo()
	

	
def pointToPixel(curLat, curLon, curTile, zoomLevel, tileCount, imgSize):
	#Determine extents of the current tile
	multiplier = tileCount/9
	#print "------==========------"
	#print tileCount
	#print curTile[0], curTile[1]
	#print multiplier
	#print [curTile[0]-(1*multiplier),curTile[1]-1-(1*multiplier)]
	#print [curTile[0]+1+(1*multiplier),curTile[1]+1+(1*multiplier)]
	#print "------==++++++==------"
	NW_Corner = num2deg([curTile[0]-(1*multiplier),curTile[1]-(1*multiplier)], zoomLevel) #Get the curTile NW Corner
	SW_Corner = num2deg([curTile[0]+1+(1*multiplier),curTile[1]+1+(1*multiplier)], zoomLevel) #Get the curTile SE Corner

	#Determine where on the tile to add the point
	lat_percent = (curLat-SW_Corner[0]) / (NW_Corner[0]-SW_Corner[0])
	lon_percent = (curLon-SW_Corner[1]) / (NW_Corner[1]-SW_Corner[1])
	lat_percent =  1-(lat_percent)
	lon_percent = 1-(lon_percent)
	
	return (int(lon_percent*imgSize[0]), int(lat_percent*imgSize[1]))
	
def processPoints(curTile, allTiles, allPoints, allPointsIndex, imgSize, videoSize, zoomLevel):
	#Builds more tiles around our single curTile
	#Create a huge image to fit all the tiles
	bigTile = Image.new("RGBA",(imgSize[0]*3,imgSize[1]*3)) #Create a space for a new big tile
	
	#Loop through the adjacent tiles
	orig_X = allPoints[allPointsIndex][0][0]
	orig_Y = allPoints[allPointsIndex][0][1]
	Xi = -1
	Yi = -1
	for X in range(orig_X-1,orig_X+2): 
		Xi = Xi + 1
		Yi = -1
		for Y in range(orig_Y-1,orig_Y+2):
			Yi = Yi + 1
			for ImgTile in allTiles:
				if ImgTile[0] == [X,Y]:
					PastePoint = (Xi*imgSize[0],Yi*imgSize[1])	
					bigTile.paste(ImgTile[1],PastePoint) #Create a New Tile Each Time
					
	#Determine the center point
		centerPoint = findCenter(50, 50, allPoints, allPointsIndex)
		centerPixel = pointToPixel(centerPoint[0], centerPoint[1], curTile, zoomLevel, 9, (imgSize[0]*3,imgSize[1]*3))
		cropBox = (centerPixel[0]-(videoSize[0]/2),centerPixel[1]-(videoSize[1]/2),centerPixel[0]+(videoSize[0]/2),centerPixel[1]+(videoSize[1]/2))
		
	#Crop the bigTile
	return bigTile.crop(cropBox)


def findCenter(lookAhead, lookBehind, allPoints, allPointsIndex):
	#Figure out the center point
	lowerLimit = allPointsIndex - lookBehind
	if lowerLimit < 0:
		lowerLimit = 0
	upperLimit = allPointsIndex + lookAhead
	if upperLimit > len(allPoints):
		upperLimit = len(allPoints)
		
	LatSum = 0
	LonSum = 0
	LatAvg = 0
	LonAvg = 0
	for centerIndex in range(lowerLimit,(upperLimit)):
		LatSum += allPoints[centerIndex][1][0]
		LonSum += allPoints[centerIndex][1][1]
		
	LatAvg = LatSum/float(upperLimit-lowerLimit)
	LonAvg = LonSum/float(upperLimit-lowerLimit)
	return (LatAvg, LonAvg)

#Video Creation Class
class VideoSink(object):
	def __init__(self, size, rate, format, filename):
	
		#Define some locations (may want to make this global)
		mencoder_path = '/usr/lib/video/mencoder'
		
		#Create the mencoder string
		cmdstring = ("%s"%(mencoder_path), '/dev/stdin', '-demuxer', 'rawvideo', 
					'-rawvideo', "w=%i:h=%i"%size[::1]+":fps=%i:format=%s"%(rate, format),
					'-ovc', 'lavc', '-lavcopts', 'vcodec=mpeg4:vbitrate=1000000', '-o', "%s.avi"%(filename[:-4]))
	
		#Start the pipe
		self.p = subprocess.Popen(cmdstring, stdin=subprocess.PIPE)
	
	def AppendImage(self, im):
		#Pipe the image to mencoder
		self.p.stdin.write(im.tostring())
		
	def CloseVideo(self):
		#Close the pipe
		self.p.stdin.close()
	

#OpenStreetMap / Tile Functions
#Convert a WGS84 point to a tile
def deg2num(lat_deg, lon_deg, zoom):
  lat_rad = math.radians(lat_deg)
  n = 2.0 ** zoom
  xtile = int((lon_deg + 180.0) / 360.0 * n)
  ytile = int((1.0 - math.log(math.tan(lat_rad) + (1 / math.cos(lat_rad))) / math.pi) / 2.0 * n)
  return [xtile, ytile]
  
#Convert a tile to a WGS84 Point (at the Northwest Corner)
def num2deg(tile, zoom):
  n = 2.0 ** zoom
  lon_deg = tile[0] / n * 360.0 - 180.0
  lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * tile[1] / n)))
  lat_deg = math.degrees(lat_rad)
  return [lat_deg, lon_deg]
  
#Remove duplicates from a python list
def removeDups(input):
  output = []
  for x in input:
    if x not in output:
      output.append(x)
  output.sort()
  return output

#Initial Function that runs everything
for fn in sys.argv[1:]:
	GPX_to_Tiles(fn, 11, 4)