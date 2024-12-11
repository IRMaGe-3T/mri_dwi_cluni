# -*- coding: utf-8 -*-
"""
Launch DWI preprocessing and TractSeg processing

mrtrix: https://mrtrix.readthedocs.io
TracSeg: https://github.com/MIC-DKFZ/TractSeg
"""

import glob
import json
import logging
import os
import shutil
import sys
import time
from datetime import datetime

from bids_conversion import convert_to_bids
from main_white_matter_bundle import run_white_matter_bundle
from PyQt5 import QtWidgets
from PyQt5.QtCore import QDir
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow, QMessageBox
from PyQt5.uic import loadUi
from useful import check_file_ext, execute_command


class App(QMainWindow):
    """
    Main windows Qt
    """

    def __init__(self):
        super(App, self).__init__()

        # Get ui
        self.dir_code_path = os.path.realpath(os.path.dirname(__file__))
        ui_file = os.path.join(self.dir_code_path, "interface.ui")
        loadUi(ui_file, self)

        # Connect sigans and slots
        self.pushButton_browser.clicked.connect(self.browse_directory)
        self.pushButton_run.clicked.connect(self.launch_processing)
        self.pushButton_mrview.clicked.connect(self.launch_mrview)

        # Init variable
        self.dicom_directory = ""
        self.partial_brain = False
        self.reset_progress_bar()

    def reset_progress_bar(self):
        """Reset progress bar"""
        self.progressBar_run.setRange(0, 100)
        self.progressBar_run.setValue(0)
        self.progressBar_run.setStyleSheet(
            "QProgressBar::chunk { background-color: blue; }"
        )

    def browse_directory(self):
        """Browse DICOM directory"""
        # directory = QFileDialog.getExistingDirectory(
        #     self, "Select a directory", QDir.homePath()
        # )
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setViewMode(QFileDialog.List)
        file_dialog.setDirectory(QDir.homePath())
        file_dialog.setNameFilter("ZIP files (*.zip)")

        if file_dialog.exec_():
            if file_dialog.selectedFiles():
                self.dicom_directory = file_dialog.selectedFiles()[0]
                self.textEdit_output_browser.setText(self.dicom_directory)
                self.pushButton_run.setEnabled(True)
                self.reset_progress_bar()

    def launch_processing(self):
        """Launch processing"""
        if self.checkBox_partial.isChecked():
            self.partial_brain = True
        if self.dicom_directory:
            self.reset_progress_bar()
            try:
                # Configuration
                config_file = os.path.join(
                    os.path.dirname(self.dir_code_path),
                    "config",
                    "config.json",
                )
                with open(config_file, encoding="utf-8") as my_json:
                    data = json.load(my_json)
                    bids_config_file = data["BidsConfigFile"]
                    out_directory = data["OutputDirectory"]
                    working_directory = data["WorkingDirectory"]
                self.progressBar_run.setValue(5)

                # Unzip dicom directory in temporary folder
                valid_bool, in_ext, file_name = check_file_ext(
                    self.dicom_directory, {"ZIP": "zip"}
                )
                if not valid_bool:
                    msg = "DICOM directory is not a zip folder"
                    self.error(msg)
                    raise Exception(msg)

                working_directory_tmp = os.path.join(working_directory, "tmp")
                if not os.path.exists(working_directory_tmp):
                    os.makedirs(working_directory_tmp)
                cmd = [
                    "unzip",
                    self.dicom_directory,
                    "-d",
                    working_directory_tmp,
                ]
                dicom_directory = os.path.join(
                    working_directory_tmp, file_name
                )
                result, stderrl, sdtoutl = execute_command(cmd)
                while not os.path.exists(dicom_directory):
                    time.sleep(2)

                # BIDS conversion
                print("\n----------CONVERSION----------")
                result, msg, info = convert_to_bids(
                    dicom_directory, bids_config_file, out_directory
                )
                if result == 0:
                    self.error(msg)
                    raise Exception(msg)
                patient_name = info["sub_name"]
                sess_name = info["sess_name"]
                # Copy DICOM directory in sourcedata
                sourcedata_directory = os.path.join(
                    out_directory,
                    "sourcedata",
                    "sub-" + patient_name + "_ses-" + sess_name,
                )
                if not os.path.exists(sourcedata_directory):
                    os.makedirs(sourcedata_directory)
                    shutil.copytree(
                        dicom_directory,
                        os.path.join(sourcedata_directory, "DICOM"),
                    )
                    os.chdir(sourcedata_directory)
                    cmd = ["tar", "czvf", "DICOM.tar.gz", "DICOM"]
                    result, stderrl, sdtoutl = execute_command(cmd)
                    while not os.path.exists(
                        os.path.join(sourcedata_directory, "DICOM.tar.gz")
                    ):
                        time.sleep(2)

                    cmd = ["rm", "-rf", "DICOM"]
                    result, stderrl, sdtoutl = execute_command(cmd)

                # Remove tpm folder
                shutil.rmtree(working_directory_tmp)

                self.progressBar_run.setValue(15)

                # Create analysis directories
                analysis_directory = os.path.join(
                    out_directory,
                    "derivatives",
                    "sub-" + patient_name,
                    "ses-" + sess_name,
                )
                preproc_directory = os.path.join(
                    analysis_directory, "preprocessing"
                )

                if os.path.exists(preproc_directory):
                    # Check if subject / session already processed
                    if len(os.listdir(preproc_directory)) > 1:
                        msg = (
                            "Data already processed for this subject/session,"
                            "would you like to repeat the analysis"
                        )
                        response = self.show_confirmation_box(msg)
                        if response == QMessageBox.Cancel:
                            print("Processing cancelled")
                            self.reset_progress_bar()
                            return
                        else:
                            # Remove old data
                            shutil.rmtree(analysis_directory)

                if not os.path.exists(analysis_directory):
                    os.makedirs(analysis_directory)
                if not os.path.exists(preproc_directory):
                    os.mkdir(preproc_directory)

                self.progressBar_run.setValue(10)

                # Change working directory
                # (mrtriw will create temp directory in it)
                os.chdir(working_directory)

                # Add log
                now = datetime.now()
                log_file = os.path.join(
                    analysis_directory,
                    now.strftime("%Y%m%d") + "_processing.log",
                )
                mylog = logging.getLogger("custom_logger")
                mylog.setLevel(logging.INFO)
                handler = logging.FileHandler(log_file)
                handler.setLevel(logging.INFO)
                handler.setFormatter(
                    logging.Formatter(
                        "%(asctime)s:%(levelname)s:%(message)s",
                        datefmt="%H:%M:%S",
                    )
                )
                mylog.addHandler(handler)
                # Print also into terminal
                handler_print = logging.StreamHandler()
                handler_print.setLevel(logging.INFO)
                handler_print.setFormatter(
                    logging.Formatter(
                        "%(asctime)s:%(levelname)s:%(message)s",
                        datefmt="%H:%M:%S",
                    )
                )
                mylog.addHandler(handler_print)

                start = time.time()
                mylog.info("Started at %s", now.strftime("%d/%m/%Y %H:%M:%S"))

                # Launch processing
                result, msg = run_white_matter_bundle(
                    out_directory, patient_name, sess_name,
                    self.partial_brain
                )
                if result == 0:
                    mylog.error(msg)
                    self.error(msg)
                    raise Exception(msg)

                # Clean tmp folder
                shutil.rmtree(os.path.join(out_directory, "tmp_dcm2bids"))
                self.progressBar_run.setValue(100)
                self.progressBar_run.setStyleSheet(
                    "QProgressBar::chunk { background-color: green; }"
                )
                end = time.time()
                mylog.info(
                    "Processing finished at %s",
                    now.strftime("%d/%m/%Y %H:%M:%S"),
                )
                total_time = (end - start) / 60
                mylog.info("Processing done in %f minutes", total_time)

                # Launch mrview
                image = glob.glob(
                    os.path.join(
                        analysis_directory, "sub-*_ses-*_dwi_*unbias.mif"
                    )
                )[0]
                tck_cst_left = os.path.join(
                    analysis_directory,
                    "tractseg_output",
                    "TOM_trackings",
                    "CST_left.tck",
                )
                tck_cst_right = os.path.join(
                    analysis_directory,
                    "tractseg_output",
                    "TOM_trackings",
                    "CST_right.tck",
                )
                tracks = [tck_cst_left, tck_cst_right]
                if image and tracks:
                    self.launch_mrview(image=image, tracks=tracks)
            except Exception as e:
                mylog.error(e)
                self.error(e)

        else:
            msg = "No dicom directory selected"
            self.progressBar_run.setStyleSheet(
                "QProgressBar::chunk { background-color: red; }"
            )
            self.show_error_message_box(msg)

    def launch_mrview(self, image=None, tracks=None):
        """Launch mrview"""
        cmd = "mrview -mode 2"
        if image:
            cmd += " -load " + image
        if tracks:
            for track in tracks:
                cmd += " -tractography.load " + track
        os.system(cmd)

    def error(self, message):
        """Error function"""
        print(f"Error during processing: {message}")
        self.progressBar_run.setStyleSheet(
            "QProgressBar::chunk { background-color: red; }"
        )
        self.show_error_message_box(str(message))

    def show_error_message_box(self, error_message):
        """Box with error message"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Critical)
        msg_box.setWindowTitle("Error")
        msg_box.setText("Error during processing:")
        msg_box.setDetailedText(error_message)
        msg_box.exec_()

    def show_confirmation_box(self, message):
        """Box to confirm an action"""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Question)
        msg_box.setWindowTitle("Confirmation")
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        return msg_box.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    mainwindow = App()
    widget = QtWidgets.QStackedWidget()
    widget.addWidget(mainwindow)
    widget.setFixedWidth(400)
    widget.setFixedHeight(300)
    widget.show()
    sys.exit(app.exec_())
