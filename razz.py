#Razzberry for RACF v4r1
#Dependencies: Python >=3.12.x and >=ZOAU 1.3.x
#Utility to sort through output from IRRUT100 and create reports in various formats

from zoautil_py import datasets
from datetime import datetime
import os
import json
import tomllib
import re
import argparse

parser = argparse.ArgumentParser(
    prog='Razzberry for RACF',
    description='Utility to sort through output from IRRUT100 and create reports in various formats',
)

#Flags and arguments to specify in the command line
parser.add_argument('-o', '--obfuscate', action='store_true')
parser.add_argument('-m', '--minimalist', action='store_true')
parser.add_argument("-n", '--noheader', action='store_false')
parser.add_argument('-i', '--input')
parser.add_argument('-d', '--destination')

args = parser.parse_args()

now = datetime.now() # current date and time
date_time = now.strftime("d-%m-%d-%Y-t-%H-%M-%S")
log_name = f"razzberry_{date_time}_"

#Regex for extracting dataset and profile information 
dataset_regex = r"^(?:(?:(?:[a-zA-Z#\$@][a-zA-Z0-9#\$@{\-]{0,7}|\*\*?)(?:\.(?:[a-zA-Z#\$@][a-zA-Z0-9#\$@{\-]{0,7}|\*\*?)){0,21}\s*|)(?<=^.{0,44}))$"
#Regex for extracting classes
class_regex = r""

#load settings from razz.toml
with open("razz.toml", "rb") as f:
    settings = tomllib.load(f)

data_settings = settings["data"]
formats_settings = settings["formats"]
reports_settings = settings["reports"]
sorting_settings = settings["sorting"]

#Stores whether the various formats are enabled or not
csv_enabled = formats_settings["csv"]
txt_enabled = formats_settings["txt"]
json_enabled = formats_settings["json"]

#Dataset that is to be sorted
input_dataset = args.input or data_settings["input_dataset"]

#Path to export the reports to
destination = args.destination or data_settings["destination"]

#This determines if a header should be used in the CSV file
use_header = args.noheader or reports_settings["use_header"]

#This determines if a header should be used in the CSV file
sort_alphabetically = sorting_settings["sort_alphabetically"]

#Removes installation specific data from the file name
obfuscate_file_names = args.obfuscate or data_settings["obfuscate_file_names"]

#This mode removes as much as information as possible
#Minimalist mode is useful if you are feeding the output to another uitlity
minimalist_mode = args.minimalist or reports_settings["minimalist_mode"]

minimalist_mode_garbage = []
def add_garbage(identifier: str):
    minimalist_mode_garbage.append(identifier)

add_garbage("Owner of group")
add_garbage("Owner of")
add_garbage("In access list of group")
add_garbage("Standard access list for")
add_garbage("In standard access list of dataset profile")
add_garbage("In standard access list of general resource profile")
add_garbage("Create group of profile")
add_garbage("(G)")

def cleanup(value: str):
    cleaned_value = value
    for garbage in minimalist_mode_garbage:
        if garbage in cleaned_value:
            cleaned_value = cleaned_value.replace(garbage,"").strip()
    return cleaned_value
        
occurrence_sentence = "Occurrences of"

report_types = []

class Report:
    def __init__(self,name: str,identifier: str,header: str):
        self.name = name
        self.identifier = identifier
        self.header = header
        self.report_list = []
        report_types.append(self)
    def reset_reports(self):
        self.report_list.clear()

Report("_AL_report","In access list of","Access list for <header>")
Report("_SAL_report","In standard access list of","Standard access list for <header>")
Report("_owner_report","Owner of","<header> is owner of")
Report("_create_report","Create group of","<header> is creator of")

def write_success(file_name: str,extension: str):
    print(f"Created {extension} report: {file_name}.{extension}")

#Internal function to export reports
def create_report(file_name: str,header: str,unsorted_list: list):
    if sort_alphabetically:
        print("Sorting alphabetically")
        sorted_list = sorted(unsorted_list)
    else:
        sorted_list = unsorted_list
    if len(sorted_list) > 0:
        #Write CSV report
        if csv_enabled:
            csv_output = open(file_name + ".csv", "w")
            if use_header:
                csv_output.write(f"{header};\n")
            for line in sorted_list:
                if minimalist_mode:
                    write_line = cleanup(line)
                else:
                    write_line = line
                csv_output.write(f"{write_line};\n")
            csv_output.close()
            write_success(file_name,"csv")
        #Write txt report
        if txt_enabled:
            txt_output = open(file_name + ".txt", "w")
            if use_header:
                txt_output.write(f"{header}\n")
            for line in sorted_list:
                if minimalist_mode:
                    write_line = cleanup(line)
                else:
                    write_line = line
                txt_output.write(f"{write_line}\n")
            txt_output.close()
            write_success(file_name,"txt")
        #Write json output
    else:
        print("Skipped report " + file_name + ", because there was nothing to report on")

if input_dataset != "":
    if datasets.exists(input_dataset):
        print("Target dataset exists, beginning sort...")
        dataset_contents = datasets.read(input_dataset)

        input_path = destination + "input.txt"

        #remove input data in case the utility has been ran before
        if os.path.exists(input_path):
            os.remove(input_path)

        rInput = open(input_path, "a")
        rInput.write(dataset_contents)
        rInput.close()
        #Create unsorted list
        unsorted_list = [line.strip('\n') for line in open(input_path, 'r').readlines()]

        print("Sorting " + str(dataset_contents.count("Occurrences")) + " instace(s)")

        #This section is a bit crazy, but it works
        #Parses through the dataset and collects the output in lists
        #Once it encounters a new section it will create reports from the section it just went through
        for i in range(len(unsorted_list)):   
            if "Occurrences" in unsorted_list[i] and i < 3:
                section_name = unsorted_list[i].replace(occurrence_sentence,"").strip()
            for type in report_types:
                if type.identifier in unsorted_list[i]:
                    type.report_list.append(unsorted_list[i].strip())
            if ("Occurrences" in unsorted_list[i] and i > 2) or (i >= len(unsorted_list) -1):
                print("Writing for " + section_name)
                for type in report_types:
                    if obfuscate_file_names:
                        write_section_name = "redacted"
                    else: 
                        write_section_name = section_name
                    create_report(destination + log_name + write_section_name + type.name,type.header.replace("<header>",section_name),type.report_list)
                    type.reset_reports
                section_name = unsorted_list[i].replace(occurrence_sentence,"").strip()
    else:
        print("Target dataset doesn't exist, sort cancelled")
else:
    print("No dataset was supplied, sort cancelled")
