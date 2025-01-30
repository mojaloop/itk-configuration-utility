##########################################################################
#  (C) Copyright Mojaloop Foundation. 2024 - All rights reserved.        #
#                                                                        #
#  This file is made available under the terms of the license agreement  #
#  specified in the corresponding source code repository.                #
#                                                                        #
#  ORIGINAL AUTHOR:                                                      #
#       James Bush - jbush@mojaloop.io                                   #
#                                                                        #
#  CONTRIBUTORS:                                                         #
#       James Bush - jbush@mojaloop.io                                   #
##########################################################################

import sys
import re
import yaml
import string
import secrets
from pathlib import Path

from itkconfigurator.customclasses import *


def find_item_in_dictionary_array(array, prop_name, value):
    return next((i for i in array if i.get(prop_name) == value), None)


class MojaloopITKConfigurator(npyscreen.NPSAppManaged):
    def __init__(self):
        self.schema_config = None
        super().__init__()

    def onStart(self):
        npyscreen.setTheme(ITKColorTheme)

        self.schema_config = ITKConfigurationScheme()

        self.registerForm("MAIN", BackgroundForm())
        self.registerForm("BASIC", MainForm(self.schema_config))
        self.registerForm("PKI", SecurityToolsForm())

        for f in self.schema_config.get_forms():
            self.registerForm(f[0], f[1])


class BackgroundForm(FilledBackgroundForm):
    def __init__(self):
        self.color = 'BACKGROUND'
        super().__init__(char=' ')

    def create(self):
        self.name = "Mojaloop Integration Toolkit Configuration Main Window"
        self.framed = False

    def while_editing(self, *args, **kwargs):
        # show the first form as soon as the main form is displayed
        self.parentApp.switchForm("BASIC")


class MainForm(ITKAppForm):
    OK_BUTTON_TEXT = "Exit"

    def __init__(self, schema_config, *args, **kwargs):
        self.schema_config = schema_config
        self.valueText = "Welcome to the Mojaloop Integration Toolkit Configuration Utility. This tool allows you to " \
                         "configure locally installed components in order to securely connect to a Mojaloop hub. " \
                         "Please select an option below to proceed. (use <TAB> or arrow keys to navigate)"
        super().__init__(*args, **kwargs)

    def create(self):
        self.name = "Mojaloop Integration Toolkit Configuration"

        width = self.columns - 10
        wrapped_text = textwrap.wrap(self.valueText, width)

        self.add(npyscreen.Pager, name="Intro", values=wrapped_text, autowrap=True, max_height=5,
                 editable=False)

        # add function buttons
        save_and_restart_text = "Save And Restart Services"

        my, mx = self.curses_pad.getmaxyx()

        funcbtn_y = my - self.__class__.OK_BUTTON_BR_OFFSET[0]
        funcbtn_x = mx - self.__class__.OK_BUTTON_BR_OFFSET[1] - len(self.OK_BUTTON_TEXT) - 2 - len(
            save_and_restart_text) - 1

        # add edit buttons for each form
        for button in self.schema_config.get_form_edit_buttons():
            self.add(TVButtonPress, name="Edit {}".format(button[1]), color="BUTTON", cursor_color="BUTTON_SELECTED",
                     when_pressed_function=self.get_edit_form_func(button[0]))
            self.nextrely += 1  # add a space between the buttons

        self.add_widget(TVButtonPress, name="Security Tools", use_max_space=True,
                        when_pressed_function=self.show_security_tools)

        self.save_restart_button = self.add_widget(TVButtonPress, name=save_and_restart_text, rely=funcbtn_y,
                                                   relx=funcbtn_x, use_max_space=True,
                                                   when_pressed_function=self.save_and_restart_services)

    def show_security_tools(self):
        self.parentApp.switchForm("PKI")

    def save_and_restart_services(self):
        self.schema_config.saveChanges()
        self.restart_services()

    def get_edit_form_func(self, form_id):
        """
        Returns a closure over the form_id to show the desired form when called
        """

        def edit_form_func(*args):
            self.parentApp.switchForm(form_id)

        return edit_form_func

    def restart_services(self):
        ret = itk_run_subprocess_form(self.parentApp, 'Please wait while services are restarted...',
                                      'Restarting Services', ['./venv/bin/python3', '-u', './servicemanager.py',
                                                              'restart_all'])

        if ret != 0:
            pass

    def afterEditing(self):
        # this gets called once the user clicks the exit button

        # exit if we dont have a next form
        if self.parentApp.NEXT_ACTIVE_FORM == "BASIC":
            if self.schema_config.has_unsaved_changes():
                # ask the user to save or exit
                ret = itk_notify_yes_no_cancel(self.parentApp, "You have unsaved changes, do you want to save them "
                                                               "before exiting?",
                                               title="Unsaved Changes")

                if ret is None:
                    # user pressed cancel, go back to main form
                    self.parentApp.setNextForm("BASIC")
                    self.parentApp.switchFormNow()
                    return

                elif ret == "yes":
                    # save changes then exit
                    self.schema_config.saveChanges()

            self.parentApp.setNextForm(None)
            self.parentApp.switchFormNow()


class ITKConfigurationScheme:
    def __init__(self, scheme_filename=Path(__file__).resolve().parent / 'itkschema.yaml', env_files=None):
        if env_files is None:
            # did we get passed an env file on the command line?
            if len(sys.argv) > 1 and sys.argv[1] is not None:
                schema_name, file_name = sys.argv[1].split('=')

                if schema_name is None or file_name is None:
                    raise Exception('First command line argument should be mc={filepath}')

                env_files = [
                    (schema_name, str(Path.cwd() / file_name)),
                ]

            else:
                env_files = [
                    ('mc', str(Path(__file__).resolve().parent / 'mojaloop-connector.env')),
                ]

        self.schema = None
        self.forms = []
        self.scheme_filename = scheme_filename
        self.env_files = env_files
        self.parse_schema_file()
        self.parse_env_files()
        self.create_forms()

    def parse_schema_file(self):
        """
        Parses the yaml schema file into a dictionary
        """
        with open(self.scheme_filename, "r") as file:
            self.schema = yaml.safe_load(file)

    def parse_env_files(self):
        """
        Parses environment files and updates env var values in the config scheme dictionary
        """
        line_number = 0

        for env_filename in self.env_files:
            with open(env_filename[1], "r") as file:
                for line in file:
                    # keep track of which line in the file we are looking at
                    line_number += 1
                    original_line = line

                    var_name, var_value = self.parse_env_file_line(line)

                    if var_name is None or var_value is None:
                        continue

                    self.update_env_var_value(env_filename[0], var_name, var_value, line_number, original_line)

    def parse_env_file_line(self, line):
        # remove any comments from the line
        l = re.sub("#.*", "", line)

        # remove whitespace from start and end of the line
        l = l.strip()

        # extract var name and value
        groups = re.search("(.*)=(.*)", l)

        # no match in this line, ignore
        if not groups:
            return None, None

        # we need two match groups (and the original string) to work with
        if len(groups.regs) != 3:
            return None, None

        # we need a var name to work with
        if len(groups[1]) <= 0:
            return None, None

        # return the var_name and var_value
        return groups[1], groups[2]

    def update_env_var_value(self, env_filename, env_var_name, value, line_number, original_line):
        for group in self.schema['itkconfigschema']['configuration']['groups']:
            for item in group['items']:
                if item['env_var']['file'] == env_filename and item['env_var']['name'] == env_var_name:
                    item['value'] = value

                    # remember which line number of the file this entry is on, its original text and the value
                    # we interpreted it as having; we will use this to check we are updating the file correctly
                    # when writing changes back.
                    item['original_value'] = value
                    item['line_number'] = line_number
                    item['original_line'] = original_line

    def has_unsaved_changes(self):
        for form in self.forms:
            for config_widget in form.config_widgets:
                if self.get_config_widget_value(config_widget[1]) != config_widget[0]['value']:
                    return True

        return False

    def get_config_widget_value(self, widget):
        widget_type = type(widget.__repr__.__self__).__name__

        if widget_type == "ITKTitleText":
            return widget.value

        elif widget_type == "ITKCheckBox":
            return str(widget.value).lower()

        else:
            raise ValueError("Unknown config widget type: {}".format(widget_type))

    def create_forms(self):
        self.forms = []

        for group in self.schema['itkconfigschema']['configuration']['groups']:
            form = ITKConfigurationGroupForm(group)
            self.forms.append(form)

    def get_form_edit_buttons(self):
        return [(f.config_group['id'], f.config_group['name']) for f in self.forms]

    def get_forms(self):
        """
        Returns a list of form objects as [(id, form), ...]
        """
        return [(f.config_group['id'], f) for f in self.forms]

    def saveChanges(self):
        for env_file in self.env_files:
            # read the entire file into a lines array
            with open(env_file[1], "r") as file:
                lines = file.readlines()

                # iterate our config widgets and update any values in the file that correspond
                for form in self.forms:
                    for widget in form.config_widgets:
                        var_name = widget[0]['env_var']['name']
                        new_value = self.get_config_widget_value(widget[1])

                        if new_value != widget[0]['value']:
                            # this value has changed.

                            if widget[0]['env_var']['file'] != env_file[0]:
                                # this value is not in this file; ignore.
                                continue

                            # check the line hasnt changed since we read it
                            line = lines[widget[0]['line_number'] - 1]

                            if line != widget[0]['original_line']:
                                raise ValueError("Original file '{}' has been modified since it was read. Please "
                                                 "restart the utility to re-read changes: {}"
                                                 .format(env_file[1], var_name))

                            lines[widget[0]['line_number'] - 1] = self.update_env_file_line(line, var_name, new_value)

                            print("writing config var {} new value {}".format(var_name, new_value))

            with open(env_file[1], "w") as file:
                file.writelines(lines)

    def update_env_file_line(self, line, var_name, new_value):
        sub_re = "(\\s*" + var_name + "=)(.*)"
        repl_re = "\\1" + new_value
        return re.sub(sub_re, repl_re, line)

    def get_config_item_value(self, group_id, item_name):
        group = find_item_in_dictionary_array(self.schema['itkconfigschema']['configuration']['groups'], 'id', group_id)
        item = find_item_in_dictionary_array(group['items'], 'name', item_name)
        return item['value']

    def write_single_env_var_value(self, env_var_name, new_value):
        # iterate all env files and update any lines that have our var in
        for env_file in self.env_files:
            changes = False
            # read the entire file into a lines array
            with open(env_file[1], "r") as file:
                lines = file.readlines()

                for idx, line in enumerate(lines):
                    var_name, var_value = self.parse_env_file_line(line)

                    if var_name == env_var_name:
                        # this line has our env var on so update it
                        lines[idx] = self.update_env_file_line(line, env_var_name, new_value)
                        changes = True

            if changes:
                with open(env_file[1], "w") as file:
                    file.writelines(lines)


class SecurityToolsForm(ITKAppForm):
    def __init__(self, *args, **kwargs):
        self.valueText = "Use the functions here to generate the digital keys and certificates required for securely " \
                         "interacting with the scheme hub"
        super().__init__(*args, **kwargs)

    def create(self):
        self.name = 'Security Tools'

        width = self.columns - 10
        wrapped_text = textwrap.wrap(self.valueText, width)

        self.add(npyscreen.Pager, name='Intro', values=wrapped_text, autowrap=True, max_height=5,
                 editable=False)

        # add function buttons
        self.add(TVButtonPress, name='Generate New Client Side Keys and Certificates', color="BUTTON",
                 cursor_color="BUTTON_SELECTED",
                 when_pressed_function=self.generate_client_side_mTLS_artefacts)
        self.nextrely += 1  # add a space between the buttons

        self.add(TVButtonPress, name='Generate New Message Signing Key-Pair', color="BUTTON",
                 cursor_color="BUTTON_SELECTED",
                 when_pressed_function=self.generate_jws_keypair)
        self.nextrely += 1  # add a space between the buttons

        self.add(TVButtonPress, name='Generate New ILP Secret', color="BUTTON",
                 cursor_color="BUTTON_SELECTED",
                 when_pressed_function=self.generate_ilp_secret)
        self.nextrely += 1  # add a space between the buttons

    def generate_client_side_mTLS_artefacts(self):
        # find where we are configured to store PKI artifacts
        dfsp_name = self.parentApp.schema_config.get_config_item_value('dfsp_details', 'DFSP ID')
        dns_names = self.parentApp.schema_config.get_config_item_value('mojaloop_connector_details', 'DFSP DNS Host Names')
        in_ca_cert_path = self.parentApp.schema_config.get_config_item_value('security', 'Inbound CA Certificate Path')
        in_server_key_path = self.parentApp.schema_config.get_config_item_value('security', 'Inbound Server Certificate Private Key Path')
        in_server_cert_path = self.parentApp.schema_config.get_config_item_value('security', 'Inbound Server Certificate Path')
        out_client_key_path = self.parentApp.schema_config.get_config_item_value('security', 'Outbound Client Certificate Private Key Path')
        out_client_cert_path = self.parentApp.schema_config.get_config_item_value('security', 'Outbound Client Certificate Path')

        # run a subprocess to generate the artifacts
        ret = itk_run_subprocess_form(self.parentApp, 'Please wait while PKI artifacts are generated...',
                                      'Generating PKI Artifacts',
                                      [
                                          'python3',
                                          '-u',
                                          str(Path(__file__).resolve().parent / './pkitools.py'),
                                          'generate_client_side_mtls',
                                           dfsp_name,
                                           in_ca_cert_path,
                                           in_server_cert_path,
                                           in_server_key_path,
                                           out_client_cert_path,
                                           out_client_key_path,
                                           dns_names
                                      ])

        if ret != 0:
            pass

    def generate_jws_keypair(self):
        jws_signing_path = self.parentApp.schema_config.get_config_item_value('non_repudiation', 'JWS Signing (private) key path')
        jws_verification_path = self.parentApp.schema_config.get_config_item_value('non_repudiation', 'JWS verification (public) key path')
        key_name = 'jwssigningkey.pem'

        # run a subprocess to generate the artifacts
        ret = itk_run_subprocess_form(self.parentApp, 'Please wait while a new JWS key pair is generated...',
                                      'Generating JWS Keypair',
                                      [
                                          'python3',
                                          '-u',
                                          str(Path(__file__).resolve().parent / 'pkitools.py'),
                                          'generate_jws_keypair',
                                          key_name,
                                          jws_signing_path,
                                          jws_verification_path,
                                      ])

    def generate_ilp_secret(self, length=32):
        # Use secrets.choice to generate a secure random string
        characters = string.ascii_letters + string.digits
        new_secret = ''.join(secrets.choice(characters) for _ in range(length))
        # note that we assume the env var for ILP secret is called "ILP_SECRET"
        # possibly factor this out to a constant if we use it in multiple places in future
        self.parentApp.schema_config.write_single_env_var_value('ILP_SECRET', new_secret)
        itk_notify_confirm('New ILP secret generated and written to disk', title='New ILP Secret')

    def afterEditing(self):
        self.parentApp.setNextFormPrevious()


def main():
    App = MojaloopITKConfigurator()
    App.run()


if __name__ == "__main__":
    input("hit a key after debugger attached")
    main()
