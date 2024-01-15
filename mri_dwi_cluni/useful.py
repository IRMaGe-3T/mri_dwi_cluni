# -*- coding: utf-8 -*-
"""
Useful functions :

- check_file_ext
- execute_command
- convert_mif_to_nifti
- convert_nifti_to_mif
- get_shell
- find_dicom_tag_value
- get_all_dicom_files
"""

import os
import subprocess

import pydicom
from pydicom.tag import Tag

EXT_NIFTI = {"NIFTI_GZ": "nii.gz", "NIFTI": "nii"}
EXT_MIF = {"MIF": "mif"}


def check_file_ext(in_file, ext_dic):
    """Check file extension

    :param in_file: file name (a string)
    :param ext_dic: dictionary of the valid extensions for the file
                    (dictionary, ex:
                    EXT = {"NIFTI_GZ": "nii.gz", "NIFTI": "nii"})
    :returns:
        - valid_bool: True if extension is valid (a boolean)
        - in_ext: file extension (a string)
        - file_name: file name without extension (a string)
    """

    # Get file extension
    valid_bool = False
    ifile = os.path.split(in_file)[-1]
    file_name, in_ext = ifile.rsplit(".", 1)
    if in_ext == "gz":
        (file_name_2, in_ext_2) = file_name.rsplit(".", 1)
        in_ext = in_ext_2 + "." + in_ext
        file_name = file_name_2

    valid_ext = list(ext_dic.values())

    if in_ext in valid_ext:
        valid_bool = True

    return valid_bool, in_ext, file_name


def execute_command(command):
    """Execute command"""
    print("\n", command)
    p = subprocess.Popen(
        command,
        shell=False,
        bufsize=-1,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        close_fds=True,
    )

    print("--------->PID:", p.pid)

    (sdtoutl, stderrl) = p.communicate()
    if str(sdtoutl) != "":
        print("sdtoutl: ", sdtoutl.decode())
    if str(stderrl) != "":
        print("stderrl: ", stderrl.decode())

    result = p.wait()

    return result, stderrl, sdtoutl


def convert_mif_to_nifti(in_file, out_directory, diff=True):
    """Convert NIfTI into MIF format"""
    in_file_nifti = None
    # Check inputs files and get files name
    valid_bool, ext, file_name = check_file_ext(in_file, EXT_MIF)
    if not valid_bool:
        msg = "\nInput image format is not " "recognized (mif needed)...!"
        return 0, msg, in_file_nifti

    # Convert diffusions into ".mif" format (mrtrix format)
    in_file_nifti = os.path.join(out_directory, file_name + ".nii.gz")
    if diff:
        bvec = in_file.replace(ext, "bvec")
        bval = in_file.replace(ext, "bval")
        cmd = [
            "mrconvert",
            in_file,
            in_file_nifti,
            "-export_grad_fsl",
            bvec,
            bval,
        ]
    else:
        cmd = ["mrconvert", in_file, in_file_nifti]

    result, stderrl, sdtoutl = execute_command(cmd)

    if result != 0:
        msg = f"Issue during conversion of {in_file} to MIF format"
        return 0, msg, in_file_nifti

    msg = f"Conversion of {in_file} to MIF format done"

    return 1, msg, in_file_nifti


def convert_nifti_to_mif(in_file, out_directory, diff=True):
    """Convert NIfTI into MIF format"""
    in_file_mif = None
    # Check inputs files and get files name
    valid_bool, ext, file_name = check_file_ext(in_file, EXT_NIFTI)
    if not valid_bool:
        msg = (
            "\nInput image format is not "
            "recognized (nii or nii.gz needed)...!"
        )
        return 0, msg, in_file_mif

    # Convert diffusions into ".mif" format (mrtrix format)
    in_file_mif = os.path.join(out_directory, file_name + ".mif")
    if diff:
        bvec = in_file.replace(ext, "bvec")
        bval = in_file.replace(ext, "bval")
        cmd = ["mrconvert", in_file, in_file_mif, "-fslgrad", bvec, bval]
    else:
        cmd = ["mrconvert", in_file, in_file_mif]

    result, stderrl, sdtoutl = execute_command(cmd)

    if result != 0:
        msg = f"Issue during conversion of {in_file} to MIF format"
        return 0, msg, in_file_mif

    msg = f"Conversion of {in_file} to MIF format done"

    return 1, msg, in_file_mif


def get_shell(in_file):
    """Convert NIfTI into MIF format"""
    shell = []
    # Check inputs files and get files name
    valid_bool, ext, file_name = check_file_ext(in_file, EXT_MIF)
    if not valid_bool:
        msg = "\nInput image format is not " "recognized (mif needed)...!"
        return 0, msg, shell

    cmd = ["mrinfo", in_file, "-shell_bvalues"]
    result, stderrl, sdtoutl = execute_command(cmd)

    if result != 0:
        msg = f"Can not get info for {in_file}"
        return 0, msg, shell
    shell = sdtoutl.decode("utf-8").replace("\n", "").split(" ")
    msg = f"Shell found for {in_file}"

    return 1, msg, shell


def find_dicom_tag_value(input_dicom_dataset, tag):
    """
    Find DICOM tag value
    """
    try:
        value = input_dicom_dataset[tag].value
    except ValueError:
        value = "tagNotFound"
    return value


def get_all_dicom_files(dicom_directory):
    """
    Get all DICOM files from a dirctory
    """
    if len(dicom_directory) == 0:
        message = "Input directory is empty."
        raise RuntimeError(message)

    raw_storage_methods_not_taken = [
        "1.2.840.10008.5.1.4.1.1.11.1",
        "1.2.840.10008.5.1.4.1.1.66",
        "Secondary Capture Image Storage",
        "1.2.840.10008.5.1.4.1.1.7",
    ]

    raw_input_files = os.listdir(dicom_directory)
    input_files = []

    # Test each file to check if it is DICOM
    for file_name in raw_input_files:
        file_start = file_name.split("/")[-1].split("_")[0].lower()
        file_ext = file_name.split(".")[-1]
        not_taken_start = ["xx", "ps", "dicomdir"]
        not_taken_ext = [
            "bvecs",
            "bvals",
            "txt",
        ]

        if file_start in not_taken_start or file_ext in not_taken_ext:
            print(f"File {file_name} not taken (not a DICOM).")
            continue
        elif os.path.isdir(os.path.join(dicom_directory, file_name)):
            # Add all files from subdirectory to file list
            sub_directory = os.path.join(dicom_directory, file_name)
            for file_in_directory in os.listdir(sub_directory):
                file_path = os.path.join(file_name, file_in_directory)
                raw_input_files.append(file_path)
            continue

        try:
            input_dicom = pydicom.read_file(
                os.path.join(dicom_directory, file_name)
            )
        except Exception:
            print(f"File {file_name} not taken (coul not read DICOM).")
            continue
        storage_method = find_dicom_tag_value(input_dicom, Tag(0x08, 0x16))[0]
        if storage_method in raw_storage_methods_not_taken:
            print(f"File {file_name} not taken (bad storage method).")
            continue
        input_files.append(os.path.join(dicom_directory, file_name))
    return input_files
