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

import docker
from docker.errors import NotFound


class ServiceManager:
    container_names = [
        'itk-mojaloop-connector',
        'itk-core-connector',
        'itk-redis',
    ]

    def __init__(self):
        self.dockerClient = docker.from_env()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def restart_all(self):
        print('Restarting all services...')

        for container_name in self.container_names:
            try:
                container = self.dockerClient.containers.get(container_name)
                print('Restarting container {}'.format(container_name))
                container.restart()
                print('Container {} restarted.'.format(container_name))

            except NotFound:
                print('Container {} not found. Not restarting'.format(container_name))

            except Exception as e:
                print('Error restarting container: {}'.format(e))

        print('Restart complete.')


if __name__ == "__main__":
    with ServiceManager() as serviceManager:

        match sys.argv[1]:
            case 'restart_all':
                serviceManager.restart_all()