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

import curses
import npyscreen
import textwrap
import subprocess
import threading
from npyscreen.wgtextbox import TextfieldBase


def run_sub_process(command_args, output_line_callback):
    """
    Runs a subprocess and calls back with stdout lines as they are produced.
    command_args is a list: ["command", "arg1", "arg2", ...]
    Calls output_line_callback(line) whenever a stdout line is written by the subprocess
    """
    proc = subprocess.Popen(command_args,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            universal_newlines=True)

    for stdout_line in iter(proc.stdout.readline, ""):
        output_line_callback(stdout_line)

    for stderr_line in iter(proc.stderr.readline, ""):
        output_line_callback(stderr_line)

    proc.stdout.close()
    proc.stderr.close()
    proc.wait()
    return proc.returncode


class ITKColorTheme(npyscreen.ThemeManager):
    default_colors = {
        'DEFAULT': 'BLACK_WHITE',
        'FORMDEFAULT': 'BLACK_WHITE',
        'FORMTITLE': 'RED_WHITE',
        'FORMSHADOW': 'BLACK_BLACK',
        'NO_EDIT': 'BLUE_BLACK',
        'STANDOUT': 'CYAN_BLACK',
        'CURSOR': 'CYAN_BLACK',
        'CURSOR_INVERSE': 'BLACK_CYAN',
        'LABEL': 'RED_BLACK',
        'LABELBOLD': 'RED_WHITE',
        'CONTROL': 'BLACK_RED',
        'WARNING': 'RED_BLACK',
        'DANGER': 'BLACK_RED',  # Custom color definition for DANGER
        'GOOD': 'GREEN_BLACK',
        'IMPORTANT': 'CYAN_BLACK',
        'SAFE': 'GREEN_BLACK',
        'INPUT': 'WHITE_BLUE',
        'BUTTON': 'BLACK_WHITE',
        'BUTTON_SELECTED': 'WHITE_RED',
        'BACKGROUND': 'BLUE_BLUE',
    }

    _colors_to_define = (
        ('BLACK_WHITE', curses.COLOR_BLACK, curses.COLOR_WHITE),
        ('BLUE_BLACK', curses.COLOR_BLUE, curses.COLOR_BLACK),
        ('CYAN_BLACK', curses.COLOR_CYAN, curses.COLOR_BLACK),
        ('GREEN_BLACK', curses.COLOR_GREEN, curses.COLOR_BLACK),
        ('MAGENTA_BLACK', curses.COLOR_MAGENTA, curses.COLOR_BLACK),
        ('RED_BLACK', curses.COLOR_RED, curses.COLOR_BLACK),
        ('YELLOW_BLACK', curses.COLOR_YELLOW, curses.COLOR_BLACK),
        ('BLACK_RED', curses.COLOR_BLACK, curses.COLOR_RED),
        ('BLACK_GREEN', curses.COLOR_BLACK, curses.COLOR_GREEN),
        ('BLACK_YELLOW', curses.COLOR_BLACK, curses.COLOR_YELLOW),
        ('BLACK_CYAN', curses.COLOR_BLACK, curses.COLOR_CYAN),
        ('BLUE_WHITE', curses.COLOR_BLUE, curses.COLOR_WHITE),
        ('CYAN_WHITE', curses.COLOR_CYAN, curses.COLOR_WHITE),
        ('GREEN_WHITE', curses.COLOR_GREEN, curses.COLOR_WHITE),
        ('MAGENTA_WHITE', curses.COLOR_MAGENTA, curses.COLOR_WHITE),
        ('RED_WHITE', curses.COLOR_RED, curses.COLOR_WHITE),
        ('YELLOW_WHITE', curses.COLOR_YELLOW, curses.COLOR_WHITE),
        ('WHITE_GREEN', curses.COLOR_WHITE, curses.COLOR_GREEN),
        ('WHITE_BLUE', curses.COLOR_WHITE, curses.COLOR_BLUE),
        ('WHITE_RED', curses.COLOR_WHITE, curses.COLOR_RED),
        ('BLUE_BLUE', curses.COLOR_BLUE, curses.COLOR_BLUE),
    )


class FilledBackgroundForm(npyscreen.Form):
    def __init__(self, char=' '):
        self.backgroundchar = char
        super(FilledBackgroundForm, self).__init__(color=self.color)

    # we override this function from the base so we can set the background char. this is not normally configurable.
    def display(self, clear=False):
        super().display(clear)
        self.curses_pad.bkgdset(self.backgroundchar, self.theme_manager.findPair(self, self.color) | curses.A_NORMAL)

        self.curses_pad.erase()
        self.draw_form()
        for w in [wg for wg in self._widgets__ if wg.hidden]:
            w.clear()
        for w in [wg for wg in self._widgets__ if not wg.hidden]:
            w.update(clear=clear)

        self.refresh()


class TVButtonPress(npyscreen.ButtonPress):
    def __init__(self, screen, when_pressed_function=None, *args, **kwargs):
        super().__init__(screen, when_pressed_function, *args, **kwargs)
        self.color = "BUTTON"
        self.cursor_color = "BUTTON_SELECTED"

    def update(self, clear=True):
        if clear: self.clear()
        if self.hidden:
            self.clear()
            return False

        button_state = curses.A_NORMAL

        button_name = self.name

        if isinstance(button_name, bytes):
            button_name = button_name.decode(self.encoding, 'replace')

        button_name = "<{}>".format(self.name)

        if self.do_colors():
            if self.cursor_color:
                if self.editing:
                    button_attributes = self.parent.theme_manager.findPair(self, self.cursor_color)
                    button_attributes = button_attributes | curses.A_BOLD
                else:
                    button_attributes = self.parent.theme_manager.findPair(self, self.color)
            else:
                button_attributes = self.parent.theme_manager.findPair(self, self.color) | button_state
        else:
            button_attributes = button_state

        # print button
        self.add_line(self.rely, self.relx + 1,
                      button_name,
                      self.make_attributes_list(button_name, button_attributes),
                      len(button_name)
                      )


class TVButton(npyscreen.MiniButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.color = "BUTTON"
        self.cursor_color = "BUTTON_SELECTED"

    def update(self, clear=True):
        if clear: self.clear()
        if self.hidden:
            self.clear()
            return False

        button_state = curses.A_NORMAL

        button_name = self.name

        if isinstance(button_name, bytes):
            button_name = button_name.decode(self.encoding, 'replace')

        button_name = "<{}>".format(self.name)

        if self.do_colors():
            if self.cursor_color:
                if self.editing:
                    button_attributes = self.parent.theme_manager.findPair(self, self.cursor_color)
                    button_attributes = button_attributes | curses.A_BOLD
                else:
                    button_attributes = self.parent.theme_manager.findPair(self, self.color)
            else:
                button_attributes = self.parent.theme_manager.findPair(self, self.color) | button_state
        else:
            button_attributes = button_state

        self.add_line(self.rely, self.relx + 1, button_name, self.make_attributes_list(button_name, button_attributes),
                      len(button_name))


class ITKTextFieldBase():
    def _print(self):
        if not self.value:
            self.print_empty()
        else:
            # call the next base class implementation
            super()._print()

    def print_empty(self):
        string_to_print = ' ' * (self.maximum_string_length - self.left_margin + 1)
        width_of_char_to_print = self.find_width_of_char(string_to_print[0])

        column = 0
        place_in_string = 0

        if self.do_colors():
            if self.show_bold and self.color == 'DEFAULT':
                color = self.parent.theme_manager.findPair(self, 'BOLD') | curses.A_BOLD
            elif self.show_bold:
                color = self.parent.theme_manager.findPair(self, self.color) | curses.A_BOLD
            elif self.important:
                color = self.parent.theme_manager.findPair(self, 'IMPORTANT') | curses.A_BOLD
            else:
                color = self.parent.theme_manager.findPair(self)
        else:
            if self.important or self.show_bold:
                color = curses.A_BOLD
            else:
                color = curses.A_NORMAL

        if self.highlight_whole_widget:
            self.parent.curses_pad.addstr(self.rely, self.relx + self.left_margin,
                                          string_to_print,
                                          color
                                          )

    def update(self, clear=True, cursor=True):
        if not self.value:
            self.update_empty(clear, cursor)
        else:
            super().update(clear, cursor)

    def update_empty(self, clear=True, cursor=True):
        if clear: self.clear()

        if self.hidden:
            return True

        value_to_use_for_calculations = self.value

        if self.ENSURE_STRING_VALUE:
            if value_to_use_for_calculations in (None, False, True):
                value_to_use_for_calculations = ''
                self.value = ''

        if self.begin_at < 0: self.begin_at = 0

        if self.left_margin >= self.maximum_string_length:
            raise ValueError

        if self.editing:
            if isinstance(self.value, bytes):
                # use a unicode version of self.value to work out where the cursor is.
                # not always accurate, but better than the bytes
                value_to_use_for_calculations = self.display_value(self.value).decode(self.encoding, 'replace')
            if cursor:
                if self.cursor_position is False:
                    self.cursor_position = len(value_to_use_for_calculations)

                elif self.cursor_position > len(value_to_use_for_calculations):
                    self.cursor_position = len(value_to_use_for_calculations)

                elif self.cursor_position < 0:
                    self.cursor_position = 0

                if self.cursor_position < self.begin_at:
                    self.begin_at = self.cursor_position

                while self.cursor_position > self.begin_at + self.maximum_string_length - self.left_margin:  # -1:
                    self.begin_at += 1
            else:
                if self.do_colors():
                    self.parent.curses_pad.bkgdset(' ', self.parent.theme_manager.findPair(self,
                                                                                           self.highlight_color) | curses.A_STANDOUT)
                else:
                    self.parent.curses_pad.bkgdset(' ', curses.A_STANDOUT)

        self._print()

        # reset everything to normal
        self.parent.curses_pad.attroff(curses.A_BOLD)
        self.parent.curses_pad.attroff(curses.A_UNDERLINE)
        self.parent.curses_pad.bkgdset(' ', curses.A_NORMAL)
        self.parent.curses_pad.attrset(0)
        if self.editing and cursor:
            self.print_cursor()


class ITKTextfield(ITKTextFieldBase, TextfieldBase):
    def __init__(self, *args, **kwargs):
        TextfieldBase.__init__(self, *args, **kwargs)

    def show_brief_message(self, message):
        curses.beep()
        keep_for_a_moment = self.value
        self.value = message
        self.editing = False
        self.display()
        curses.napms(1200)
        self.editing = True
        self.value = keep_for_a_moment

    def edit(self):
        self.editing = 1
        if self.cursor_position is False:
            self.cursor_position = len(self.value or '')
        self.parent.curses_pad.keypad(1)

        self.old_value = self.value

        self.how_exited = False

        while self.editing:
            self.display()
            self.get_and_use_key_press()

        self.begin_at = 0
        self.display()
        self.cursor_position = False
        return self.how_exited, self.value

    def set_up_handlers(self):
        TextfieldBase.set_up_handlers(self)

        # For OS X
        del_key = curses.ascii.alt('~')

        self.handlers.update({curses.KEY_LEFT: self.h_cursor_left,
                              curses.KEY_RIGHT: self.h_cursor_right,
                              curses.KEY_DC: self.h_delete_right,
                              curses.ascii.DEL: self.h_delete_left,
                              curses.ascii.BS: self.h_delete_left,
                              curses.KEY_BACKSPACE: self.h_delete_left,
                              # mac os x curses reports DEL as escape oddly
                              # no solution yet
                              "^K": self.h_erase_right,
                              "^U": self.h_erase_left,
                              })

        self.complex_handlers.extend((
            (self.t_input_isprint, self.h_addch),
        ))

    def t_input_isprint(self, inp):
        if self._last_get_ch_was_unicode and inp not in '\n\t\r':
            return True
        if curses.ascii.isprint(inp) and \
                (chr(inp) not in '\n\t\r'):
            return True
        else:
            return False

    def h_addch(self, inp):
        if self.editable:
            # workaround for the metamode bug:
            if self._last_get_ch_was_unicode == True and isinstance(self.value, bytes):
                # probably dealing with python2.
                ch_adding = inp
                self.value = self.value.decode()
            elif self._last_get_ch_was_unicode == True:
                ch_adding = inp
            else:
                try:
                    ch_adding = chr(inp)
                except TypeError:
                    ch_adding = input
            self.value = self.value[:self.cursor_position] + ch_adding \
                         + self.value[self.cursor_position:]
            self.cursor_position += len(ch_adding)

    def h_cursor_left(self, input):
        self.cursor_position -= 1

    def h_cursor_right(self, input):
        self.cursor_position += 1

    def h_delete_left(self, input):
        if self.editable and self.cursor_position > 0:
            self.value = self.value[:self.cursor_position - 1] + self.value[self.cursor_position:]

        self.cursor_position -= 1
        self.begin_at -= 1

    def h_delete_right(self, input):
        if self.editable:
            self.value = self.value[:self.cursor_position] + self.value[self.cursor_position + 1:]

    def h_erase_left(self, input):
        if self.editable:
            self.value = self.value[self.cursor_position:]
            self.cursor_position = 0

    def h_erase_right(self, input):
        if self.editable:
            self.value = self.value[:self.cursor_position]
            self.cursor_position = len(self.value)
            self.begin_at = 0

    def handle_mouse_event(self, mouse_event):
        mouse_id, rel_x, rel_y, z, bstate = self.interpret_mouse_event(mouse_event)
        self.cursor_position = rel_x + self.begin_at
        self.display()


class ITKTitleText(npyscreen.TitleText):
    _entry_type = ITKTextfield

    def __init__(self, *args, **kwargs):
        super(ITKTitleText, self).__init__(*args, **kwargs)
        self.entry_widget.highlight_whole_widget = True


class ITKAppForm(npyscreen.FormMultiPage):
    OK_BUTTON_BR_OFFSET = (2, 7)
    OKBUTTON_TYPE = TVButton
    OK_BUTTON_TEXT = "Done"
    BLANK_COLUMNS_RIGHT = 5
    FIX_MINIMUM_SIZE_WHEN_CREATED = False

    def __init__(self, border_width=2, *args, **kwargs):
        self.shadow_pad = None
        self.border_width = border_width
        self.framed = True

        self.color = "FORMDEFAULT"

        my, mx = self._max_physical()
        self.lines = my - (self.border_width * 1)
        kwargs['lines'] = self.lines

        self.columns = mx - (self.border_width * 2)
        kwargs['columns'] = self.columns

        kwargs['relx'] = 2  # X offset from the left
        kwargs['rely'] = 2  # Y offset from the top

        super().__init__(*args, **kwargs)

        self.center_on_display()
        self.make_ok_button()

    def make_ok_button(self):
        my, mx = self.curses_pad.getmaxyx()
        ok_button_text = self.__class__.OK_BUTTON_TEXT
        my -= self.__class__.OK_BUTTON_BR_OFFSET[0]
        mx -= len(ok_button_text) + self.__class__.OK_BUTTON_BR_OFFSET[1]
        self.ok_button = self.add_widget(TVButtonPress, name=ok_button_text, rely=my, relx=mx, use_max_space=True,
                                         when_pressed_function=self.ok_button_click)
        self.ok_button.update()

    def ok_button_click(self):
        self.editing = False

    def refresh(self):
        if self.shadow_pad is None:
            self.shadow_pad = curses.newpad(self.lines, self.columns)
            self.shadow_pad.bkgdset(' ', self.theme_manager.findPair(self, 'FORMSHADOW'))

        _my, _mx = self._max_physical()
        self.shadow_pad.move(1, 1)

        try:
            self.shadow_pad.refresh(self.show_from_y, self.show_from_x, self.show_aty + 1, self.show_atx + 1, _my, _mx)
        except curses.error:
            pass

        super().refresh()

    def draw_title_and_help(self):
        try:
            if self.name:
                _title = self.name
                _title = ' ' + str(_title) + ' '

                if isinstance(_title, bytes):
                    _title = _title.decode('utf-8', 'replace')

                startx = int((self.columns / 2) - (len(_title) / 2) - 1)

                self.curses_pad.addch(0, startx, curses.ACS_RTEE)
                self.curses_pad.addstr(0, startx + 1, _title,
                                       self.theme_manager.findPair(self, 'FORMTITLE') | curses.A_BOLD)
                self.curses_pad.addch(0, startx + 1 + len(_title), curses.ACS_LTEE)

        except:
            pass

        if self.help and self.editing:
            try:
                help_advert = " Help: F1 or ^O "
                if isinstance(help_advert, bytes):
                    help_advert = help_advert.decode('utf-8', 'replace')
                self.add_line(
                    0, self.curses_pad.getmaxyx()[1] - len(help_advert) - 2,
                    help_advert,
                    self.make_attributes_list(help_advert, curses.A_NORMAL),
                    len(help_advert)
                )
            except:
                pass


class ITKCheckBox(npyscreen.Checkbox):
    def __init__(self, *args, **kwargs):
        lc = kwargs.get('labelColor')
        if lc:
            self.labelColor = lc
        else:
            self.labelColor = 'FORMDEFAULT'

        super().__init__(*args, **kwargs)

    def update(self, clear=True):
        if clear: self.clear()
        if self.hidden:
            self.clear()
            return False
        if self.hide: return True

        if self.value:
            cb_display = self.__class__.True_box
        else:
            cb_display = self.__class__.False_box

        if self.do_colors():
            self.parent.curses_pad.addstr(self.rely, self.relx, cb_display,
                                          self.parent.theme_manager.findPair(self, self.color))
        else:
            self.parent.curses_pad.addstr(self.rely, self.relx, cb_display)

        self._update_label_area()

    def _create_label_area(self, screen):
        l_a_width = self.width - 5

        if l_a_width < 1:
            raise ValueError("Width of checkbox + label must be at least 6")

        self.label_area = npyscreen.Textfield(screen, rely=self.rely, relx=self.relx + 5,
                                              width=self.width - 5, value=self.name, color=self.labelColor)

    def _update_label_area(self, clear=True):
        self.label_area.value = self.name
        self._update_label_row_attributes(self.label_area, clear=clear)

    def _update_label_row_attributes(self, row, clear=True):
        if self.editing:
            row.show_bold = True
            row.color = 'LABELBOLD'
        else:
            row.show_bold = False
            row.color = self.labelColor

        row.update(clear=clear)


def itk_notify_yes_no_cancel(parentApp, message, title="Confirm", editw=0):
    F = ITKConfirmForm(parentApp=parentApp, title=title, message=message)
    F.preserve_selected_widget = True

    F.editw = editw
    F.edit()
    return F.value


def itk_run_subprocess_form(parentApp, message, title="Confirm", proc_args=None, editw=0):
    if proc_args is None:
        proc_args = []

    F = ITKRunSubprocessForm(parentApp=parentApp, title=title, message=message, sub_process_args=proc_args)
    F.edit()
    ret = F.value
    return F.value


class ItkNotifyForm(npyscreen.Form):
    DEFAULT_LINES = 8
    DEFAULT_COLUMNS = 60
    SHOW_ATX = 10
    SHOW_ATY = 2
    OK_BUTTON_BR_OFFSET = (2, 7)
    OKBUTTON_TYPE = TVButton

    def __init__(self, *args, **kwargs):
        self.shadow_pad = None
        super().__init__(*args, **kwargs)

    def refresh(self):
        if self.shadow_pad is None:
            self.shadow_pad = curses.newpad(self.lines, self.columns)
            self.shadow_pad.bkgdset(' ', self.theme_manager.findPair(self, 'FORMSHADOW'))

        _my, _mx = self._max_physical()
        self.shadow_pad.move(1, 1)

        try:
            self.shadow_pad.refresh(self.show_from_y, self.show_from_x, self.show_aty + 1, self.show_atx + 1, _my, _mx)
        except curses.error:
            pass

        super().refresh()

    def draw_title_and_help(self):
        try:
            if self.name:
                _title = self.name
                _title = ' ' + str(_title) + ' '

                if isinstance(_title, bytes):
                    _title = _title.decode('utf-8', 'replace')

                startx = int((self.columns / 2) - (len(_title) / 2) - 1)

                self.curses_pad.addch(0, startx, curses.ACS_RTEE)
                self.curses_pad.addstr(0, startx + 1, _title,
                                       self.theme_manager.findPair(self, 'FORMTITLE') | curses.A_BOLD)
                self.curses_pad.addch(0, startx + 1 + len(_title), curses.ACS_LTEE)

        except:
            pass

def itk_notify_confirm(message, title="Message", editw=0):
    F = ItkNotifyForm(name=title)
    #F.preserve_selected_widget = True
    mlw = F.add(npyscreen.Pager, editable=False)
    #mlw.editable = False
    mlw_width = mlw.width - 1
    message = textwrap.wrap(message, mlw_width)
    mlw.values = message
    F.editw = editw
    F.center_on_display()
    F.edit()


class ITKRunSubprocessForm(ITKAppForm):
    OK_BUTTON_TEXT = "Close"

    def __init__(self, parentApp, title, message, sub_process_args, *args, **kwargs):
        self.intro = None
        self.background_thread = None
        self.sub_process_output_widget = None
        self.sub_process_args = sub_process_args
        self.parentApp = parentApp
        self.title = title
        self.message = message
        self.value = None

        super().__init__(name=title, *args, **kwargs)

        # after we have inited, we leave a mess on the screen so we have to redraw the background form.
        # note that calling edit on this form will show it in the correct place
        self.parentApp._Forms["MAIN"].display()

    def pre_edit_loop(self):
        self.ok_button.hidden = True
        self.display()
        self.background_thread = threading.Thread(target=self.run_sub_process)
        self.background_thread.start()
        self.background_thread.join()
        self.sub_process_done()

    def run_sub_process(self):
        self.value = run_sub_process(self.sub_process_args, self.add_subprocess_output_line)

    def add_subprocess_output_line(self, line):
        self.sub_process_output_widget.values.append(line)
        self.sub_process_output_widget.display()

    def sub_process_done(self):
        self.ok_button.hidden = False
        self.editw = 2
        self.display()

    def afterEditing(self):
        self.intro.destroy()
        del self.intro

        self.sub_process_output_widget.destroy()
        del self.sub_process_output_widget

    def create(self):
        width = self.columns - 10
        wrapped_text = textwrap.wrap(self.message, width)

        self.intro = self.add(npyscreen.Pager, name="Intro", values=wrapped_text, autowrap=True, max_height=5,
                              editable=False)

        self.sub_process_output_widget = self.add(npyscreen.Pager, name="Output", autowrap=True, editable=True)


class ITKConfirmForm(ITKAppForm):
    OK_BUTTON_TEXT = "Cancel"

    def __init__(self, parentApp, title, message, *args, **kwargs):
        self.parentApp = parentApp
        self.title = title
        self.message = message
        self.value = None
        self.no_button = None
        self.yes_button = None
        super().__init__(name=title, *args, **kwargs)

        # after we have inited, we leave a mess on the screen so we have to redraw the background form.
        # note that calling edit on this form will show it in the correct place
        self.parentApp._Forms["MAIN"].display()

    def no_pressed(self):
        self.value = "no"
        self.editing = False

    def yes_pressed(self):
        self.value = "yes"
        self.editing = False

    def afterEditing(self):
        self.no_button.destroy()
        del self.no_button
        self.yes_button.destroy()
        del self.yes_button

    def create(self):
        width = self.columns - 10
        wrapped_text = textwrap.wrap(self.message, width)

        self.add(npyscreen.Pager, name="Intro", values=wrapped_text, autowrap=True, max_height=5,
                 editable=False)

        yes_text = "Yes"
        no_text = "No"

        my, mx = self.curses_pad.getmaxyx()

        no_y = my - self.__class__.OK_BUTTON_BR_OFFSET[0]
        no_x = mx - self.__class__.OK_BUTTON_BR_OFFSET[1] - len(self.OK_BUTTON_TEXT) - 2 - len(no_text) - 1
        yes_x = no_x - len(yes_text) - 3

        self.yes_button = self.add_widget(TVButtonPress, name=yes_text, rely=no_y, relx=yes_x, use_max_space=True,
                                          when_pressed_function=self.yes_pressed)
        self.no_button = self.add_widget(TVButtonPress, name=no_text, rely=no_y, relx=no_x, use_max_space=True,
                                         when_pressed_function=self.no_pressed)


class ITKConfigurationGroupForm(ITKAppForm):
    def __init__(self, config_group, *args, **kwargs):
        self.config_group = config_group
        self.config_widgets = []
        super().__init__(name=self.config_group['name'], *args, **kwargs)

    def afterEditing(self):
        self.parentApp.setNextFormPrevious()

    def create(self):
        self.add(npyscreen.Pager, name="Intro", values=[self.config_group['description']], autowrap=True, height=3,
                 editable=False)

        # note that the value is interpretted in the context of the input "type" e.g. string, bool etc...
        for item in self.config_group['items']:
            value = ""
            w = None

            if item['type'] == 'string':
                if 'value' in item:
                    value = item['value']

                w = self.add_widget_intelligent(ITKTitleText, name=item['name'], value=value, labelColor="FORMDEFAULT",
                                                color="INPUT", highlight_whole_widget=True)

            elif item['type'] == 'bool':
                if 'value' in item:
                    if item['value'].lower() == 'true':
                        value = True
                    else:
                        value = False

                w = self.add_widget_intelligent(ITKCheckBox, name=item['name'], value=value, labelColor="FORMDEFAULT",
                                                color="FORMDEFAULT")

            self.config_widgets.append((item, w))

            self.nextrely += 1  # add a space between the widgets

        super().create()
