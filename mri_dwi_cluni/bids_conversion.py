# -*- coding: utf-8 -*-
"""
Convert to BIDS format:
- get_info_subject
- convert_to_bids
"""

import pydicom
import unidecode
from pydicom.tag import Tag
from useful import execute_command, find_dicom_tag_value, get_all_dicom_files


def get_info_subject(dicom_directory):
    """Get some info in DICOM tag"""

    info_subject = {}
    input_dicom_files = get_all_dicom_files(dicom_directory)
    # Use first DICOM to get patient information
    input_dicom_dataset = pydicom.read_file(input_dicom_files[0])
    patient_name = find_dicom_tag_value(input_dicom_dataset, Tag(0x10, 0x0010))
    info_subject["PatientName"] = "".join(
        filter(str.isalnum, unidecode.unidecode(patient_name))
    )
    info_subject["StudyDate"] = find_dicom_tag_value(
        input_dicom_dataset, Tag(0x08, 0x0020)
    )
    info_subject["PatientBirthDate"] = find_dicom_tag_value(
        input_dicom_dataset, Tag(0x10, 0x0030)
    )

    return info_subject


def convert_to_bids(dicom_directory, config_file, out_directory):
    """
    Convert to BIDS format (ie convert to NIfTI/json and do the BIDS hierarchy)
    """
    info = {}
    # Get subject name / session
    info_subject = get_info_subject(dicom_directory)
    sub_name = info_subject["PatientName"] + info_subject["PatientBirthDate"]
    print("\nSubject ", sub_name)
    sess_name = info_subject["StudyDate"]
    print("Session ", sess_name)
    info = {"sub_name": sub_name, "sess_name": sess_name}

    # Launch dcm2bids
    cmd = [
        "dcm2bids",
        "-d",
        dicom_directory,
        "-p",
        sub_name,
        "-s",
        sess_name,
        "-c",
        config_file,
        "-o",
        out_directory,
    ]
    result, stderrl, sdtoutl = execute_command(cmd)
    if result != 0:
        msg = f"Can not lunch dcm2bids (exit code {result})"
        return 0, msg, info
    msg = "Conversion BIDS done"
    return 1, msg, info
