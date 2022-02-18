#!/usr/bin/python
#
#       mbd - Moodle Bulk downloader
#
#       quickly written script, use at own risk!
#
#       uses the REST API of moodle to download
#       - all the resources (mod_resource) in a moodle course
#       - all the files attached to assignments (mod_assign introattachments)
#       - all the files in folders (mod_folder)
#
#       Christian Strauch 2021
#


import requests
import json
import getpass
import urllib
import re
import os
import argparse
import colorama

server = ""
courseid = 0

def get_token(server, user, password):
    req = requests.post("https://" + server + "/login/token.php",
                        data = {
                            "username": user,
                            "password": password,
                            "service": "moodle_mobile_app" }
                        )
    if(req.status_code != 200):
        return "", ""
    
    d = req.json()
    token = ""
    privatetoken = ""
    if "token" in d:
        token = d["token"]
    if "privatetoken" in d:
        privatetoken = d["privatetoken"]
    return token, privatetoken

def get_course_folder_file_infos(server, token, courseid):
    req = requests.post("https://"+ server + "/webservice/rest/server.php",
                    data = {
                            "moodlewsrestformat": "json",
                            "wsfunction": "core_course_get_contents",
                            "wstoken": token,
                            "courseid": courseid,
                        }
                    )
    req.raise_for_status()
    j = req.json()
    file_infos = []
    for d in j:
        if isinstance(d, dict):
            if "modules" in d:
                mods = d["modules"]
                
                for md in mods:
                    if "modname" in md:
                        if md["modname"] == "folder":
                            folderid = 0
                            if "id" in md and "name" in md:
                                folderid = md["id"]
                                foldername = md["name"]
                                if "contents" in md:
                                    
                                    for content in md["contents"]:
                                        if "type" in content:
                                            if content["type"] == "file":
                                                if "fileurl" in content and "filename" in content:
                                                    info = {
                                                                "url": content["fileurl"],
                                                                "filename": content["filename"],
                                                                "folder_id": folderid,
                                                                "folder_name": foldername
                                                            }
                                                    file_infos.append(info)
    return file_infos

def get_course_resource_infos(server, token, courseid):
    req = requests.post("https://"+ server + "/webservice/rest/server.php",
                        data = {
                                "moodlewsrestformat": "json",
                                "wsfunction": "mod_resource_get_resources_by_courses",
                                "wstoken": token,
                                "courseids[0]": courseid
                            }
                        )
    req.raise_for_status()
    
#     file = open("get_course_resources.json", "w")
#     file.write(json.dumps(json.loads(req.text), indent=4))
#     file.close()
    
    j = req.json()
    resource_infos = []
    if "resources" in j:
        resarr = j["resources"]
        if isinstance(resarr, list):
            
            for res in resarr:
                if isinstance(res, dict):
                    if "contentfiles" in res:
                        c = res["contentfiles"]
                        if isinstance(c, list):
                            
                            for filedict in c:
                                if isinstance(filedict, dict):
                                    if "fileurl" in filedict and "filename" in filedict:
                                        if "id" in res:
                                            info = {
                                                "url": filedict["fileurl"],
                                                "filename": filedict["filename"].strip(),
                                                "resource_id": res["id"]
                                                }
                                            resource_infos.append(info)
                                            #print("Add file " + filedict["fileurl"])
    return resource_infos

def get_assignment_infos(server, token, courseid):
    req = requests.post("https://" + server + "/webservice/rest/server.php",
                    data = {
                            "moodlewsrestformat": "json",
                            "wsfunction": "mod_assign_get_assignments",
                            "wstoken": token,
                            "courseids[0]": courseid,
                            "capabilities[0]": "mod/assign:view"
                        }
                    )
    req.raise_for_status()
    j = req.json()
    assignment_infos = []
    if isinstance(j, dict):
        if "courses" in j:
            if isinstance(j["courses"], list):
                
                for d in j["courses"]:
                    if isinstance(d, dict):
                        if "id" in d:
                            if str(d["id"]) == str(courseid):
                                if "assignments" in d:
                                    assigns = d["assignments"]
                                    if isinstance(assigns, list):
                                        
                                        for assign in assigns:
                                            if isinstance(assign, dict):
                                                if "introattachments" in assign:
                                                    introfiles = assign["introattachments"]
                                                    if isinstance(introfiles, list):
                                                        
                                                        for fd in introfiles:
                                                            if isinstance(fd, dict):
                                                                if "fileurl" in fd and "filename" in fd:
                                                                    if "name" in assign and "id" in assign:
                                                                        info = {
                                                                            "assign_name": assign["name"].strip(),
                                                                            "assign_id": assign["id"],
                                                                            "url": fd["fileurl"],
                                                                            "filename": fd["filename"].strip()
                                                                            }
                                                                        assignment_infos.append(info)
                                                                        #print("Add file " + fd["fileurl"])
    return assignment_infos

def download_resource(url, token, filename="", overwrite=True, verbose=False):
    https = url[0:8]
    if https != "https://":
        raise ValueError("download_resource: url must start with https://")
    
    if not filename or filename == "":
        filename = urllib.parse.unquote(url[url.rfind("/")+1 :])
    filename = re.sub("[\\/:*?\"<>|]", "_", filename)
    exists = False
    if os.path.exists(filename):
        exists = True
        if not overwrite:
            if verbose:
                print("SKIP ", filename)
            return
    
    #if verbose:
        #print("Downloading " + filename + "...")
    
    req = requests.post(url,
                            data = {
                                "token": token
                            }
                        )
    
    req.raise_for_status()
    #if verbose:
    prefix = (colorama.Fore.YELLOW + "OVWR ") if exists else (colorama.Fore.GREEN + "ADD  ")
    print(prefix + filename + colorama.Style.RESET_ALL)
    
    file=open(filename, "wb")
    file.write(req.content)
    file.close()

def retrieve_all_resources(server, token, courseid, overwrite=True, verbose=False):
    try:
        if verbose:
            print("\n\n-----------------------------")
            print("Retrieving resources...")
        course_resource_infos = get_course_resource_infos(server, token, courseid)
        if verbose:
            print("Downloading resources...\n")
        
        for info in course_resource_infos:
            try:
                download_resource(info["url"], token, str(info["resource_id"]) + "_" + info["filename"], overwrite, verbose)
            except requests.exceptions.RequestException as e:
                print("ERROR: ", str(e), "(file " + info["url"] + ")")
            except Exception as e:
                print("EXCEPTION:", str(e), "(file " + info["url"] + ")")
                
    except requests.exceptions.RequestException as e:
        print("ERROR: ", str(e))
    except Exception as e:
        print("EXCEPTION:", str(e)) 

def retrieve_all_assignments(server, token, courseid, overwrite=True, verbose=False):
    try:
        if verbose:
            print("\n\n-----------------------------")
            print("Retrieving all assignments...")
        course_assignments = get_assignment_infos(server, token, courseid)
        if verbose:
            print("Downloading attachments of assignments...\n")

        for info in course_assignments:
            try:
                download_resource(info["url"], token, "assignment_" + info["assign_name"] + "_" + str(info["assign_id"]) + "_" + info["filename"], overwrite, verbose)
            except requests.exceptions.RequestException as e:
                print("ERROR: ", str(e), "(file " + info["url"] + ")")
            except Exception as e:
                print("EXCEPTION:", str(e), "(file " + info["url"] + ")")
                
    except requests.exceptions.RequestException as e:
        print("ERROR: ", str(e))
    except Exception as e:
        print("EXCEPTION:", str(e))

def retrieve_all_folder_contents(server, token, courseid, overwrite=True, verbose=False):
    try:
        if verbose:
            print("\n\n-----------------------------")
            print("Retrieving files in folder...")
        folder_files_infos = get_course_folder_file_infos(server, token, courseid)
        if verbose:
            print("Downloading files in folders...\n")
        
        cwd = os.getcwd()
        for info in folder_files_infos:
            try:
                folder = str(info["folder_id"]) + "_" + info["folder_name"]
                folder = re.sub("[\\/:*?\"<>|\.]", "_", folder)
                os.makedirs(folder, exist_ok=True)
                os.chdir(folder)
                download_resource(info["url"], token, info["filename"], overwrite, verbose)
                os.chdir(cwd)
            except requests.exceptions.RequestException as e:
                print("ERROR: ", str(e), "(file " + info["url"] + ")")
            except Exception as e:
                print("EXCEPTION:", str(e), "(file " + info["url"] + ")")
                
    except requests.exceptions.RequestException as e:
        print("ERROR: ", str(e))
    except Exception as e:
        print("EXCEPTION:", str(e))

def interpret_url(url):
    url = url.strip("http://")
    url = url.strip("https://")
    url = url.strip("/")
    findstr = "view.php?id="
    courseid_pos = url.find(findstr)
    courseid = 0
    if courseid_pos != -1:
        courseid = str(int(url[courseid_pos+len(findstr) :]))

    return url.split("/", 1)[0], courseid



###############        PROGRAM START        ###############

if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description="Bulk download resources and assignments from a moodle course.")
    argparser.add_argument("-o", "--overwrite", action='store_true', help="Overwrite existing files")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Be verbose.")
    args = argparser.parse_args()


    server = input("Enter moodle url: ")

    server, courseid = interpret_url(server)

    print("moodle server: '" + server + "'")
    if courseid != 0:
        print("course: " + str(courseid))
    else:
        courseid = input("course id: ")

    user = input("User: ")
    password = getpass.getpass("Password: ")
    token, privatetoken = get_token(server, user, password)
    user = ""
    password = ""

    if token == "":
        print("Could not login to server " + server)
        exit(1)

    retrieve_all_assignments(server, token, courseid, args.overwrite, args.verbose)
    retrieve_all_resources(server, token, courseid, args.overwrite, args.verbose)
    retrieve_all_folder_contents(server, token, courseid, args.overwrite, args.verbose)



