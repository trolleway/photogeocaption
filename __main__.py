#!/usr/bin/python
# -*- coding: utf-8 -*-
import sys
reload(sys)
sys.setdefaultencoding('utf-8')

print(sys.stdout.encoding)

import sys
import os
import datetime
import pyexiv2
import re
from dateutil.tz import tzlocal
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
import urllib2
import json

from transliterate import translit, get_available_language_codes

def _find_getch():
    try:
        import termios
    except ImportError:
        # Non-POSIX. Return msvcrt's (Windows') getch.
        import msvcrt
        return msvcrt.getch

    # POSIX system. Create and return a getch that manipulates the tty.
    import sys, tty
    def _getch():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    return _getch




def get_args():
    import argparse
    p = argparse.ArgumentParser(description='Geotag one or more photos with location and orientation from GPX file.')
    p.add_argument('path', help='Path containing JPG files, or location of one JPG file.')
    return p.parse_args()

    
def get_exif_data(image):
    """Returns a dictionary from the exif data of an PIL Image item. Also converts the GPS Tags"""
    exif_data = {}
    info = image._getexif()
    if info:
        for tag, value in info.items():
            decoded = TAGS.get(tag, tag)
            if decoded == "GPSInfo":
                gps_data = {}
                for t in value:
                    sub_decoded = GPSTAGS.get(t, t)
                    gps_data[sub_decoded] = value[t]

                exif_data[decoded] = gps_data
            else:
                exif_data[decoded] = value

    return exif_data

def _get_if_exist(data, key):
    if key in data:
        return data[key]
		
    return None
	
def _convert_to_degress(value):
    """Helper function to convert the GPS coordinates stored in the EXIF to degress in float format"""
    d0 = value[0][0]
    d1 = value[0][1]
    d = float(d0) / float(d1)

    m0 = value[1][0]
    m1 = value[1][1]
    m = float(m0) / float(m1)

    s0 = value[2][0]
    s1 = value[2][1]
    s = float(s0) / float(s1)

    return d + (m / 60.0) + (s / 3600.0)

def get_lat_lon(exif_data):
    """Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)"""
    lat = None
    lon = None

    if "GPSInfo" in exif_data:		
        gps_info = exif_data["GPSInfo"]
        


        gps_latitude = _get_if_exist(gps_info, "GPSDestLatitude")
        gps_latitude_ref = _get_if_exist(gps_info, 'GPSDestLatitudeRef')
        gps_longitude = _get_if_exist(gps_info, 'GPSDestLongitude')
        gps_longitude_ref = _get_if_exist(gps_info, 'GPSDestLongitudeRef')
        
        if gps_latitude is None:  
            gps_latitude = _get_if_exist(gps_info, "GPSLatitude")
            gps_latitude_ref = _get_if_exist(gps_info, 'GPSLatitudeRef')
            gps_longitude = _get_if_exist(gps_info, 'GPSLongitude')
            gps_longitude_ref = _get_if_exist(gps_info, 'GPSLongitudeRef')
        
        
        
      
        if gps_latitude and gps_latitude_ref and gps_longitude and gps_longitude_ref:
            lat = _convert_to_degress(gps_latitude)
            if gps_latitude_ref != "N":                     
                lat = 0 - lat

            lon = _convert_to_degress(gps_longitude)
            if gps_longitude_ref != "E":
                lon = 0 - lon

    return lat, lon

def get_iptc_caption(exif_data):
    """Returns the latitude and longitude, if available, from the provided exif_data (obtained through get_exif_data above)"""
    caption = ""
    #print exif_data
    caption=_get_if_exist(exif_data, "ImageSescription")
    
    return caption
   
def save_exif_value(filepath,tagname,new_value):
    metadata = pyexiv2.ImageMetadata(filepath)
    metadata.read()
    metadata[tagname]=[new_value]
    metadata.iptc_charset = 'utf-8'
    metadata.write()
    
    return 0
    
text_combinations = {}    
text_combinations[1] = u'{filename}_{road_ru}{extension}'    
text_combinations[2] = u'{filename}_{road_en}{extension}'    
text_combinations[3] = u'{filename} {road_en_translit}{extension}'    
    
def ask_mode(filepath):
    with open(str(filepath), 'rb') as f:
        image = Image.open(f)
        exif_data = get_exif_data(image)
        del image
        
    gc = {}
    gc['en']={}
    gc['ru']={}
    lat,lon=get_lat_lon(exif_data)
    iptc_caption=get_iptc_caption(exif_data)
    
    if lat is None or lon is None:
        return None
      
    
    geocoding_lang='en'
    overpass_query='http://nominatim.openstreetmap.org/reverse?format=json&lat='+str(lat)+'&lon='+str(lon)+'&zoom=18&addressdetails=1&accept-language='+geocoding_lang+'&email=trolleway@yandex.ru' #55.761513669974704,37.65164165999822
    print overpass_query
    while True:
        try:
            overpass_http_result=urllib2.urlopen(overpass_query, timeout=15).read()
            overpass_data = json.loads(overpass_http_result)
            gc['en']['state']=_get_if_exist(overpass_data['address'],'state') or ''  
            gc['en']['town']=_get_if_exist(overpass_data['address'],'city') or _get_if_exist(overpass_data['address'],'town') or _get_if_exist(overpass_data['address'],'suburb') or _get_if_exist(overpass_data['address'],'village') or ''
            gc['en']['house_number']=_get_if_exist(overpass_data['address'],'house_number') or _get_if_exist(overpass_data['address'],'building') or '' 
            gc['en']['road']=_get_if_exist(overpass_data['address'],'road') or _get_if_exist(overpass_data['address'],'address27') or ''  
            break
        except:
            print 'error'
            continue
        
    geocoding_lang='ru'
    overpass_query='http://nominatim.openstreetmap.org/reverse?format=json&lat='+str(lat)+'&lon='+str(lon)+'&zoom=18&addressdetails=1&accept-language='+geocoding_lang+'&email=trolleway@yandex.ru' #55.761513669974704,37.65164165999822
    overpass_http_result=urllib2.urlopen(overpass_query, timeout=10).read()
    overpass_data = json.loads(overpass_http_result)
    
    gc['ru']['state'] = _get_if_exist(overpass_data['address'],'state') or ''
    gc['ru']['town'] = _get_if_exist(overpass_data['address'],'city') or _get_if_exist(overpass_data['address'],'town') or _get_if_exist(overpass_data['address'],'suburb') or _get_if_exist(overpass_data['address'],'village') or ''
    gc['ru']['house_number'] = _get_if_exist(overpass_data['address'],'house_number') or _get_if_exist(overpass_data['address'],'building') or '' 
    gc['ru']['road'] = _get_if_exist(overpass_data['address'],'road') or _get_if_exist(overpass_data['address'],'address27') or '' 
    address_string='#'+gc['ru']['state'].replace(' ','_')+' '+'#'+gc['ru']['town'].replace(' ','_')+' '+gc['ru']['road'] + ' ' + gc['ru']['house_number']
    #print address_string
    address_string=translit(address_string,'ru', reversed=False)
    #print address_string
    address_string=re.sub(r'\s+', ' ', address_string) #remove double spaces
    #print address_string
    gc['ru']['address_string_ru'] = address_string
    
    texts = dict()
    for index,template in text_combinations.iteritems():
        full_text = template.format(
            filename=(os.path.splitext(filepath)[0]),
            road_en=gc['en']['road'],
            road_en_translit=translit(gc['en']['road'],'ru',reversed=True),
            road_ru=gc['ru']['road'],
            extension=os.path.splitext(filepath)[1]
        )
        texts[index] = full_text
        print(str(index).zfill(5)+'   '+full_text)
        
    choise = input("Please enter a number or 0 to skip: ")
    
    if choise == '0':
        return None
    
    rename_file(filepath,texts[choise])
    
    
        
    
def rename_file(filepath,text):
    newname=text
    print 'rename {filepath} to {newname}'.format(filepath=filepath,newname=newname)
    os.rename(filepath, text)
    
def rename_using_dest(filepath):
    '''
    
    '''
    with open(str(filepath), 'rb') as f:
        image = Image.open(f)
        exif_data = get_exif_data(image)
        del image
    #print 'Photo coords founded'
    print "*"
    lat,lon=get_lat_lon(exif_data)
    iptc_caption=get_iptc_caption(exif_data)
    
    # -=-=-=-=-=-=-
    geocoding_lang='en'
    overpass_query='http://nominatim.openstreetmap.org/reverse?format=json&lat='+str(lat)+'&lon='+str(lon)+'&zoom=18&addressdetails=1&accept-language='+geocoding_lang+'&email=trolleway@yandex.ru' #55.761513669974704,37.65164165999822
    print overpass_query
    overpass_http_result=urllib2.urlopen(overpass_query, timeout=5).read()
    overpass_data = json.loads(overpass_http_result)
    district=_get_if_exist(overpass_data['address'],'state') or ''
    town=_get_if_exist(overpass_data['address'],'city') or _get_if_exist(overpass_data['address'],'town') or _get_if_exist(overpass_data['address'],'suburb') or _get_if_exist(overpass_data['address'],'village') or ''
    housenumber=_get_if_exist(overpass_data['address'],'house_number') or _get_if_exist(overpass_data['address'],'building') or '' 
    road=_get_if_exist(overpass_data['address'],'road') or _get_if_exist(overpass_data['address'],'address27') or '' 
    address_string='#'+district.replace(' ','_')+' '+'#'+town.replace(' ','_')+' '+road+' '+housenumber
    address_string=translit(address_string,'ru', reversed=True)
    address_string=re.sub(r'\s+', ' ', address_string) #remove double spaces
    address_string_en=address_string
    # -=-=-=-=-=-=-
     
    # -=-=-=-=-=-=-
    geocoding_lang='ru'
    overpass_query='http://nominatim.openstreetmap.org/reverse?format=json&lat='+str(lat)+'&lon='+str(lon)+'&zoom=18&addressdetails=1&accept-language='+geocoding_lang+'&email=trolleway@yandex.ru' #55.761513669974704,37.65164165999822
    print overpass_query
    overpass_http_result=urllib2.urlopen(overpass_query, timeout=10).read()
    overpass_data = json.loads(overpass_http_result)
    district=_get_if_exist(overpass_data['address'],'state') or ''
    town=_get_if_exist(overpass_data['address'],'city') or _get_if_exist(overpass_data['address'],'town') or _get_if_exist(overpass_data['address'],'suburb') or _get_if_exist(overpass_data['address'],'village') or ''
    housenumber=_get_if_exist(overpass_data['address'],'house_number') or _get_if_exist(overpass_data['address'],'building') or '' 
    road=_get_if_exist(overpass_data['address'],'road') or _get_if_exist(overpass_data['address'],'address27') or '' 
    address_string='#'+district.replace(' ','_')+' '+'#'+town.replace(' ','_')+' '+road+' '+housenumber
    print address_string
    address_string=translit(address_string,'ru', reversed=False)
    print address_string
    address_string=re.sub(r'\s+', ' ', address_string) #remove double spaces
    print address_string
    address_string_ru=address_string
    # -=-=-=-=-=-=-   
    
    

    

    
    path=os.path.dirname(filepath)
    old_filename=os.path.basename(filepath)
    
    new_filename = address_string_en.replace('#','')+' '+old_filename
    new_filepath=os.path.join(path,new_filename)
    new_filepath=new_filename.replace('/','_drob_')
    
    

    
    iptc_caption=u""
    address_string_long=address_string_en+"\n"+address_string_ru
    
    metadata = pyexiv2.ImageMetadata(filepath)
    metadata.read()
    tag=_get_if_exist(metadata,'Iptc.Application2.Caption')
    if tag: 
        #iptc_caption = tag.value[0]
        iptc_caption=tag.value[0]+"\n"+address_string_long
    else:
        iptc_caption=address_string_long
        
    print address_string_long
    
    save_exif_value(filepath,'Iptc.Application2.Caption',iptc_caption)
    save_exif_value(filepath,'Iptc.Application2.ObjectName',address_string_en.replace('#',''))


    
    print "rename {0} to {1}".format(filepath,new_filepath)
    os.rename(filepath,new_filepath)

if __name__ == '__main__':
    args = get_args()

    #now = datetime.datetime.now(tzlocal())
    #print("Your local timezone is {0}, if this is not correct, your geotags will be wrong.".format(now.strftime('%Y-%m-%d %H:%M:%S %Z')))

    if args.path.lower().endswith(".jpg"):
        # single file
        file_list = [args.path]
    else:
        # folder(s)
        file_list = []
        for root, sub_folders, files in os.walk(args.path):
            file_list += [os.path.join(root, filename) for filename in files if filename.lower().endswith(".jpg")]



    print("===\nStarting renaming of {0} images using .\n===".format(len(file_list)))

    for filepath in file_list:
        mode = ask_mode(filepath)
       


