import json
import os
import subprocess

CLEAR_FN = 'cls' if os.name == 'nt' else 'clear'


class Settings:
    settings_file_name = 'ReleaseInfoCreator.json'
    settings_file_path = os.path.join( os.path.dirname(os.path.abspath(__file__)), settings_file_name )
    paths = {}
    preferred_host_name = ''
    image_hosts_skeleton = [
        {
            'name': 'ptpimg',
            'api_key': '',
            'default': False
        },
        {
            'name': 'imgbb',
            'api_key': '',
            'default': False
        },
        {
            'name': 'hdbimg',
            'username': '',
            'api_key': '',
            'default': False
        },
        {
            'name': 'ahdimg',
            'api_key': '',
            'default': False
        }
    ]
    image_hosts = image_hosts_skeleton

    @staticmethod
    def load_settings():
        try:
            with open(Settings.settings_file_path, 'r', encoding='utf8') as f:
                settings = json.load(f)
            Settings.paths = settings['paths']
            Settings.image_hosts = settings['image_hosts']
            Settings._append_missing_image_hosts()
        except FileNotFoundError:
            Settings._query_new_settings()

    @staticmethod
    def _query_new_settings():
        retry = True

        while retry:
            print(f'\nInput your settings to be saved into {Settings.settings_file_name}')
            Settings._query_image_host_info()
            Settings._query_paths()

            subprocess.run(CLEAR_FN, shell=True)
            print('\nYour Settings:\n' + json.dumps(Settings._get_settings_dict(), indent=4) + '\n')

            retry = False if input('Use these settings [Y/n]?').lower() == 'y' else True
            subprocess.run(CLEAR_FN, shell=True)

        with open(Settings.settings_file_path, 'w', encoding='utf8') as f:
            json.dump(Settings._get_settings_dict(), f, indent=4)

    @staticmethod
    def _query_image_host_info():
        Settings.image_hosts = Settings.image_hosts_skeleton
        # to check if user has chosen an image host as their default
        is_set_default = False

        for i, _ in enumerate(Settings.image_hosts_skeleton):
            host_name = Settings.image_hosts[i]['name']
            Settings.image_hosts[i]['api_key'] = input(f'\nInput the API key for {host_name} (to skip, leave blank): ')

            if host_name == 'hdbimg':
                Settings.image_hosts[i]['username'] = input(f'Input your username for {host_name} (to skip, leave blank): ')

            # Query for default if api key is is given a value
            if Settings.image_hosts[i]['api_key'].strip() != '' and not is_set_default:
                Settings.image_hosts[i]['default'] = True if input(
                    f'Set {host_name} as the default [Y/n]? ').lower() == 'y' else False
                if Settings.image_hosts[i]['default']:
                    is_set_default = True

    @staticmethod
    def _query_paths():
        Settings.paths = {}
        Settings.paths['image_save_location'] = input('\nInput the image save directory: ').strip()
        Settings.paths['ffmpeg_bin_path'] = input('Input the full path for the ffmpeg binary: ').strip()
        Settings.paths['mediainfo_bin_path'] = input('Input the full path for the mediainfo binary: ').strip()

    @staticmethod
    def _get_settings_dict():
        return { 'paths': Settings.paths, 'image_hosts': Settings.image_hosts }

    # Query preferred host from user. Returns index number of host in list
    @staticmethod
    def get_preferred_host():
        default_host_index = Settings._get_default_host()
        # If image host has 'default' flag set, skip query and use that
        if default_host_index != -1:
            return default_host_index

        bad_choice_msg = ''
        max_num = len(Settings.image_hosts)

        while True:
            print(f'\n{bad_choice_msg}Choose an image host to use: \n')

            for i, image_host in enumerate(Settings.image_hosts):
                host_name = image_host['name']

                # will be printed in the console-printed options menu to indicate if the image host key is not set
                set_str = '    (not set)' if image_host['api_key'].strip() == '' else ''
                print(f'  {i + 1}: {host_name}{set_str}')

            choice = input(f'\nYour choice (between {1} and {max_num}): ')
            if not choice.isnumeric() or not ( int(choice) >= 1 and int(choice) <= max_num ):
                bad_choice_msg = 'Bad choice. Try again.\n'
                subprocess.run(CLEAR_FN, shell=True)
                continue
            elif Settings.image_hosts[ int(choice) - 1 ]['api_key'].strip() == '':
                bad_choice_msg = f'Your chosen image host ({choice}) has not been set.\n'
                subprocess.run(CLEAR_FN, shell=True)
                continue
            else:
                return int(choice) - 1

    @staticmethod
    def _get_default_host():
        for i, image_host in enumerate(Settings.image_hosts):
            if image_host['default']:
                return i
        return -1

    @staticmethod
    def _append_missing_image_hosts():
        if len(Settings.image_hosts) == len(Settings.image_hosts_skeleton):
            return

        image_host_names_from_file = [d['name'] for d in Settings.image_hosts]

        for image_host in Settings.image_hosts_skeleton:
            if image_host['name'] not in image_host_names_from_file:
                Settings.image_hosts.append(image_host)

        with open(Settings.settings_file_path, 'w', encoding='utf8') as f:
            json.dump(Settings._get_settings_dict(), f, indent=4)

    @staticmethod
    def query_options():
        pass
